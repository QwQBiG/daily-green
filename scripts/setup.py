#!/usr/bin/env python3
"""Plan or configure an owned private instance; never handle credential values."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from greenhouse_config import (LOCAL_CONFIG, REPO, ROOT, Settings, load_config,
                               require_automation, unique_object)


class SetupError(Exception):
    pass


def command(args, *, input=None, env=None, check=True):
    try:
        result=subprocess.run(args,cwd=ROOT,text=True,input=input,capture_output=True,env=env)
    except (OSError,subprocess.SubprocessError):
        raise SetupError('Required command unavailable; install Git and GitHub CLI and sign in first') from None
    if check and result.returncode:
        # Never replay CLI responses that might include private paths or credentials.
        raise SetupError('A GitHub CLI or Git operation failed; no credentials were logged')
    return result


def api(path, *, payload=None, method='GET'):
    args=['gh','api',path,'--method',method]
    if payload is not None:args+=['--input','-']
    result=command(args,input=json.dumps(payload) if payload is not None else None)
    try:return json.loads(result.stdout) if result.stdout.strip() else None
    except ValueError:raise SetupError('GitHub CLI returned invalid JSON') from None


def remote_repository(remote):
    remote=remote.strip()
    if remote.startswith('git@github.com:'):
        target=remote[len('git@github.com:'):]
    else:
        parsed=urlsplit(remote)
        if parsed.scheme!='https' or parsed.hostname!='github.com' or parsed.username or parsed.password:
            raise SetupError('Use a GitHub SSH or HTTPS origin without credentials in its URL')
        target=parsed.path.lstrip('/')
    if target.endswith('.git'):target=target[:-4]
    if not REPO.fullmatch(target):raise SetupError('Invalid GitHub origin')
    return target


def validate_ledger(ledger, settings):
    from daily_green import planned_count
    if ledger['timezone']!=settings.timezone or ledger['start_date']!=settings.start_date.isoformat():
        raise SetupError('Existing ledger timezone/start date is immutable; use a new empty instance to change it')
    expected=settings.start_date
    today=datetime.now(settings.zone).date()
    entries=sorted(ledger['days'].items())
    for index,(text,entry) in enumerate(entries):
        try:day=date.fromisoformat(text)
        except (ValueError,TypeError):raise SetupError('Existing ledger dates are invalid') from None
        if day.isoformat()!=text or day!=expected or day>today:
            raise SetupError('Existing ledger dates are not continuous or contain future days')
        if (not isinstance(entry,dict) or set(entry)!={'commits','planned'}
                or type(entry['commits']) is not int or type(entry['planned']) is not int
                or entry['planned']!=planned_count(day) or not 1<=entry['commits']<=entry['planned']
                or (index<len(entries)-1 and entry['commits']!=entry['planned'])):
            raise SetupError('Existing ledger counts are invalid; refusing to enable the scheduler')
        if index<len(entries)-1:expected+=timedelta(days=1)


def make_plan(args):
    if not REPO.fullmatch(args.repository):raise SetupError('Use OWNER/REPOSITORY')
    identity=api('user')
    if (not isinstance(identity,dict) or identity.get('type')!='User'
            or not isinstance(identity.get('login'),str) or type(identity.get('id')) is not int):
        raise SetupError('Sign in to GitHub CLI with your own GitHub user account')
    metadata=api('repos/'+args.repository)
    if not isinstance(metadata,dict) or metadata.get('full_name','').lower()!=args.repository.lower():
        raise SetupError('Unexpected target repository')
    if metadata.get('is_template') or metadata.get('private') is not True:
        raise SetupError('Configure a private instance, not the public template or another public repository')
    if not metadata.get('permissions',{}).get('admin'):
        raise SetupError('Repository admin permission is needed to configure your instance')
    if metadata.get('default_branch')!='main':raise SetupError('The instance default branch must be main')
    if command(['git','branch','--show-current']).stdout.strip()!='main':
        raise SetupError('Check out the instance main branch first')
    if remote_repository(command(['git','remote','get-url','origin']).stdout).lower()!=args.repository.lower():
        raise SetupError('Current checkout origin does not match the target instance')
    if command(['git','status','--porcelain','--untracked-files=all']).stdout:
        raise SetupError('Commit or remove unrelated working changes before setup')
    if command(['git','rev-list','--left-right','--count','HEAD...origin/main']).stdout.split()!=['0','0']:
        raise SetupError('Local main must match origin/main; fetch and synchronize first')
    previous=load_config()
    ledger_path=ROOT/'data/activity.json'
    ledger=None
    if ledger_path.exists():
        try:ledger=json.loads(ledger_path.read_text(),object_pairs_hook=unique_object)
        except (ValueError,OSError):raise SetupError('Existing ledger is invalid; refusing to overwrite it') from None
        if not isinstance(ledger,dict) or set(ledger)!={'timezone','start_date','days'} or not isinstance(ledger['days'],dict):
            raise SetupError('Existing ledger schema is invalid; refusing to overwrite it')
    zone=args.timezone or (previous.timezone if previous.configured else ledger['timezone'] if ledger else 'UTC')
    # Parse through Settings/config validator before using a user-provided timezone.
    from greenhouse_config import parse_config
    checked=parse_config(json.dumps({'timezone':zone}))
    today=datetime.now(checked.zone).date()
    start=args.start or (previous.start_date if previous.configured else date.fromisoformat(ledger['start_date']) if ledger else today)
    if start>today:raise SetupError('Start date cannot be in the future')
    if not ledger and (today-start).days>366:
        raise SetupError('Initial cosmetic backfill is limited to 366 days; use a recent explicit start date')
    login=identity['login']
    settings=Settings(timezone=zone,start_date=start,author_name=login,
        author_email=f"{identity['id']}+{login}@users.noreply.github.com",
        repository=metadata['full_name'],reviewer=login,review_enabled=not args.no_review,configured=True)
    require_automation(settings)
    if ledger is not None:validate_ledger(ledger,settings)
    if previous.configured and any(getattr(previous,key)!=getattr(settings,key)
            for key in ('repository','timezone','start_date','author_name','author_email')):
        raise SetupError('Existing local identity or date settings differ; refusing an automatic migration')
    return settings, ledger


def save_local(settings):
    temp=None
    try:
        with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=ROOT,prefix='.greenhouse.local.json.',delete=False) as handle:
            temp=handle.name;os.fchmod(handle.fileno(),0o600)
            json.dump(settings.to_dict(),handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.replace(temp,LOCAL_CONFIG);temp=None
    finally:
        if temp:Path(temp).unlink(missing_ok=True)


def variable(repository,name,value):
    command(['gh','variable','set',name,'--repo',repository],input=value)


def apply_plan(settings, ledger):
    repository=settings.repository
    # Enabling is the last step, so partial setup never starts scheduled work.
    variable(repository,'GREENHOUSE_ENABLED','false')
    save_local(settings)
    if ledger is None:
        path=ROOT/'data/activity.json';path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({'timezone':settings.timezone,'start_date':settings.start_date.isoformat(),'days':{}},indent=2)+'\n')
        command(['git','add','--','data/activity.json'])
        env=os.environ.copy()
        env.update({'GIT_AUTHOR_NAME':settings.author_name,'GIT_COMMITTER_NAME':settings.author_name,
                    'GIT_AUTHOR_EMAIL':settings.author_email,'GIT_COMMITTER_EMAIL':settings.author_email})
        env.pop('GIT_AUTHOR_DATE',None);env.pop('GIT_COMMITTER_DATE',None)
        command(['git','-c','commit.gpgsign=false','commit','-m','chore: initialize private daily instance'],env=env)
        command(['git','push','origin','HEAD:main'])
    api('repos/'+repository+'/actions/permissions',method='PUT',payload={'enabled':True})
    if settings.review_enabled:
        api('repos/'+repository+'/actions/permissions/workflow',method='PUT',
            payload={'default_workflow_permissions':'read','can_approve_pull_request_reviews':True})
    variable(repository,'GREENHOUSE_CONFIG',json.dumps(settings.to_dict(),separators=(',',':')))
    variable(repository,'GREENHOUSE_ENABLED','true')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True,help='Your own private OWNER/REPOSITORY instance')
    parser.add_argument('--timezone',help='IANA date timezone; default UTC (daily cron remains UTC)')
    parser.add_argument('--start',type=date.fromisoformat,help='Optional cosmetic history start; default today')
    parser.add_argument('--no-review',action='store_true',help='Disable optional personal consistency review')
    parser.add_argument('--apply',action='store_true',help='Apply the reviewed plan; otherwise read-only')
    args=parser.parse_args(argv)
    try:
        settings,ledger=make_plan(args)
        print('Target: '+settings.repository)
        print('Plan: configure your private instance, use GitHub noreply identity, and start '+settings.start_date.isoformat()+'.')
        print('One daily job at 10:17 UTC. No push-triggered checks, extra monitor, or automatic test run.')
        print('Personal review: '+('enabled after you manually store GREENHOUSE_REVIEW_TOKEN in GitHub Secrets.' if settings.review_enabled else 'disabled.'))
        if not args.apply:
            print('Read-only plan; use --apply to configure this instance. No files, commits, settings, or workflows changed.')
            return 0
        apply_plan(settings,ledger)
        print('Instance configured. No workflow was dispatched. Never paste a personal token into an agent chat.')
        return 0
    except SetupError as error:
        print('Setup stopped: '+str(error),file=sys.stderr)
        return 1
    except (ValueError,OSError,TypeError,KeyError):
        # Do not leak raw JSON, credential-bearing subprocess failures, or local paths.
        print('Setup stopped safely. Check private target/admin access, clean synchronized main, valid timezone/start, and matching origin/config. Existing credentials were not read or uploaded.',file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
