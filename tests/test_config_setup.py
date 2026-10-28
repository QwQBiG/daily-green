"""Configuration and setup guards, using fake CLI responses only."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import greenhouse_config as config
import setup


def settings(**changes):
    values=dict(version=1,repository='sample-user/sample-garden',author_name='sample-user',
        author_email='1000+sample-user@users.noreply.github.com',reviewer='sample-user',
        timezone='UTC',start_date='2000-01-01',review_enabled=True)
    values.update(changes)
    return config.parse_config(json.dumps(values))


class ConfigTests(unittest.TestCase):
    def test_missing_configuration_never_infers_system_git_identity(self):
        with patch.dict(os.environ,{},clear=True), patch.object(Path,'is_file',return_value=False):
            value=config.load_config()
        self.assertFalse(value.configured)
        with self.assertRaises(ValueError):config.require_automation(value)

    def test_valid_noreply_roundtrip_and_no_real_email(self):
        value=settings()
        with patch.dict(os.environ,{},clear=True):config.require_automation(value)
        self.assertEqual(config.parse_config(json.dumps(value.to_dict())),value)
        for email in ['person@example.com','1000+other-user@users.noreply.github.com','bad\nmail']:
            with self.assertRaises(ValueError):config.require_automation(settings(author_email=email))

    def test_wrong_repo_or_future_date_refused(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'other-user/other-garden'}):
            with self.assertRaises(ValueError):config.require_automation(settings())
        with self.assertRaises(ValueError):config.require_automation(settings(start_date='2999-01-01'))

    def test_unknown_duplicate_secret_and_bad_scalar_values_refused(self):
        cases=['{"review_enabled":true,"review_enabled":false}', '{"token":"example-not-a-key"}',
               '{"timezone":"Missing/Zone"}','{"start_date":"today"}', '{"start_date":"2025-02-30"}',
               '{"version":true}','{"review_enabled":"true"}','{"author_name":4}', '[1,2]']
        for raw in cases:
            with self.subTest(raw=raw),self.assertRaises(ValueError):config.parse_config(raw)

    def test_env_configuration_precedes_local_file(self):
        value=settings()
        with patch.dict(os.environ,{'GREENHOUSE_CONFIG_JSON':json.dumps(value.to_dict())}),patch.object(Path,'is_file',side_effect=AssertionError('must not read file')):
            self.assertEqual(config.load_config(),value)


class SetupTests(unittest.TestCase):
    def test_dry_run_has_no_mutating_operations(self):
        with patch.object(setup,'make_plan',return_value=(settings(),None)),patch.object(setup,'apply_plan') as apply,patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(setup.main(['--repository','sample-user/sample-garden']),0)
            apply.assert_not_called()

    def test_apply_requires_flag_and_enables_last_without_reading_tokens(self):
        events=[]
        with patch.object(setup,'variable',side_effect=lambda *a:events.append(('variable',a))),patch.object(setup,'save_local',side_effect=lambda *a:events.append(('save',))),patch.object(setup,'api',side_effect=lambda *a,**k:events.append(('api',a,k))),patch.object(setup,'command',side_effect=AssertionError('no git when ledger exists')):
            setup.apply_plan(settings(),{'days':{}})
        self.assertEqual(events[0],('variable',('sample-user/sample-garden','GREENHOUSE_ENABLED','false')))
        self.assertEqual(events[-1],('variable',('sample-user/sample-garden','GREENHOUSE_ENABLED','true')))
        self.assertFalse(any('secret' in str(event).lower() for event in events))

    def test_partial_apply_failure_never_enables_scheduler(self):
        events=[]
        with patch.object(setup,'variable',side_effect=lambda *a:events.append(a)),patch.object(setup,'save_local',side_effect=setup.SetupError('failure')):
            with self.assertRaises(setup.SetupError):setup.apply_plan(settings(),None)
        self.assertEqual(events,[('sample-user/sample-garden','GREENHOUSE_ENABLED','false')])

    def test_first_initialization_stages_only_ledger_and_both_noreply_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            commands=[]
            with patch.object(setup,'ROOT',Path(directory)),patch.object(setup,'variable'),patch.object(setup,'save_local'),patch.object(setup,'api'),patch.object(setup,'command',side_effect=lambda args,**kw:commands.append((args,kw))):
                setup.apply_plan(settings(),None)
            data=json.loads((Path(directory)/'data/activity.json').read_text())
        self.assertEqual(data,{'timezone':'UTC','start_date':'2000-01-01','days':{}})
        self.assertEqual(commands[0][0],['git','add','--','data/activity.json'])
        env=commands[1][1]['env']
        self.assertEqual(env['GIT_AUTHOR_EMAIL'],'1000+sample-user@users.noreply.github.com')
        self.assertEqual(env['GIT_COMMITTER_EMAIL'],env['GIT_AUTHOR_EMAIL'])
        self.assertEqual(commands[-1][0],['git','push','origin','HEAD:main'])

    def test_private_local_settings_are_atomic_ignored_name_and_restricted_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'.greenhouse.local.json'
            with patch.object(setup,'ROOT',Path(directory)),patch.object(setup,'LOCAL_CONFIG',target):setup.save_local(settings())
            self.assertEqual(target.stat().st_mode&0o777,0o600)
            self.assertEqual(json.loads(target.read_text())['author_name'],'sample-user')
            self.assertEqual(list(Path(directory).iterdir()),[target])

    def test_target_origin_parsing_refuses_embedded_credentials(self):
        for remote in ['https://github.com/sample-user/sample-garden.git','git@github.com:sample-user/sample-garden.git']:
            self.assertEqual(setup.remote_repository(remote),'sample-user/sample-garden')
        for remote in ['https://name:password@github.com/sample-user/sample-garden.git','https://elsewhere.invalid/sample-user/sample-garden','file:///tmp/sample','https://github.com/../sample']:
            with self.assertRaises(setup.SetupError):setup.remote_repository(remote)

    def test_existing_ledger_rejects_bad_counts_and_gaps_before_enabling(self):
        from daily_green import planned_count
        value=settings()
        ledger={'timezone':'UTC','start_date':'2000-01-01','days':{}}
        setup.validate_ledger(ledger,value)
        count=planned_count(date(2000,1,1))
        ledger['days']={'2000-01-01':{'commits':count,'planned':count}}
        setup.validate_ledger(ledger,value)
        for days in ({'2000-01-02':{'commits':count,'planned':count}},
                     {'2000-01-01':{'commits':True,'planned':count}},
                     {'2000-01-01':{'commits':count,'planned':count+1}}):
            with self.assertRaises(setup.SetupError):setup.validate_ledger({**ledger,'days':days},value)

    def test_setup_error_is_actionable_without_replaying_cli_output(self):
        with patch.object(setup,'make_plan',side_effect=setup.SetupError('Private instance required')),patch('sys.stderr',new=io.StringIO()) as out:
            self.assertEqual(setup.main(['--repository','sample-user/sample-garden']),1)
        self.assertIn('Private instance required',out.getvalue())

    def test_public_or_template_repository_is_refused_before_git_writes(self):
        identity={'login':'sample-user','id':1000,'type':'User'}
        for changed in ({'private':False},{'is_template':True}):
            metadata={'full_name':'sample-user/sample-garden','private':True,'is_template':False,'permissions':{'admin':True},'default_branch':'main',**changed}
            with patch.object(setup,'api',side_effect=[identity,metadata]),patch.object(setup,'command',side_effect=AssertionError('no git should be run')):
                with self.assertRaises(setup.SetupError):setup.make_plan(SimpleNamespace(repository='sample-user/sample-garden'))


if __name__=='__main__':unittest.main()
