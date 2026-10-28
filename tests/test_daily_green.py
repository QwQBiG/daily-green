"""Exercise the local commit engine in disposable Git repositories, without a network."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import daily_green as daily

START = date(2001, 2, 3)
SAMPLE = {
    "version": 1, "timezone": "UTC", "start_date": START.isoformat(),
    "author_name": "sample-user", "author_email": "1000+sample-user@users.noreply.github.com",
    "repository": "sample-user/calendar-playground", "reviewer": "sample-user", "review_enabled": False,
}


def isolated_env(config=SAMPLE):
    env = os.environ.copy()
    for key in ("GREENHOUSE_CONFIG_JSON", "GREENHOUSE_CONFIG_FILE", "GITHUB_REPOSITORY",
                "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE", "GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME",
                "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        env.pop(key, None)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "PYTHONDONTWRITEBYTECODE": "1"})
    if config is not None:
        env["GREENHOUSE_CONFIG_JSON"] = json.dumps(config)
    return env


def git(repo, *args, check=True, env=None):
    return subprocess.run(["git", "-c", "gc.auto=0", *args], cwd=repo, env=env or isolated_env(),
                          text=True, capture_output=True, check=check)


def seed(repo, config=SAMPLE, ledger=True):
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "user.name", "local-default")
    git(repo, "config", "user.email", "local-default@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    git(repo, "config", "core.hooksPath", os.devnull)
    (repo / "scripts").mkdir()
    for filename in ("daily_green.py", "greenhouse_config.py", "report_status.py"):
        shutil.copyfile(ROOT / "scripts" / filename, repo / "scripts" / filename)
    (repo / "README.md").write_text("Disposable template fixture.\n")
    (repo / ".gitignore").write_text("__pycache__/\n*.py[cod]\ndata/.daily-green-*.tmp\n")
    if ledger:
        write_ledger(repo, {}, config)
    git(repo, "add", "--all")
    git(repo, "-c", "user.name=sample-user", "-c", "user.email=1000+sample-user@users.noreply.github.com",
        "commit", "--no-gpg-sign", "-m", "Initialize sample template")


def write_ledger(repo, days, config=SAMPLE):
    path = repo / "data/activity.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"timezone": config["timezone"], "start_date": config["start_date"], "days": days}) + "\n")


def commit_ledger(repo, message="Update test fixture"):
    git(repo, "add", "--", "data/activity.json")
    git(repo, "-c", "user.name=sample-user", "-c", "user.email=1000+sample-user@users.noreply.github.com",
        "commit", "--no-gpg-sign", "-m", message)


def run_daily(repo, *arguments, config=SAMPLE, cwd=None):
    return subprocess.run([sys.executable, "-B", str(repo / "scripts/daily_green.py"), *arguments],
                          cwd=cwd or repo, env=isolated_env(config), text=True, capture_output=True)


class CommitEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_empty_committed_ledger_bootstraps_in_shallow_checkout_then_repeats_without_commits(self):
        original, clone = self.base / "source", self.base / "shallow"
        seed(original)
        git(self.base, "clone", "--depth=1", original.as_uri(), str(clone))
        self.assertEqual(git(clone, "rev-parse", "--is-shallow-repository").stdout.strip(), "true")
        first = run_daily(clone, "--fast", "--through", START.isoformat())
        self.assertEqual(first.returncode, 0, first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual(report["created_commits"], daily.planned_count(START))
        self.assertEqual(report["missing_commits"], 0)
        head = git(clone, "rev-parse", "HEAD").stdout
        repeated = run_daily(clone, "--fast", "--through", START.isoformat())
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["created_commits"], 0)
        self.assertEqual(git(clone, "rev-parse", "HEAD").stdout, head)
        self.assertEqual(git(clone, "status", "--porcelain").stdout, "")

    def test_no_configuration_and_real_email_fail_before_any_ledger_or_commit_write(self):
        repo = self.base / "sample"
        seed(repo, ledger=False)
        before = git(repo, "rev-parse", "HEAD").stdout
        for config in (None, {**SAMPLE, "author_email": "someone@example.invalid"}):
            with self.subTest(configured=config is not None):
                result = run_daily(repo, "--fast", "--through", START.isoformat(), config=config)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(git(repo, "rev-parse", "HEAD").stdout, before)
                self.assertFalse((repo / "data/activity.json").exists())
                self.assertNotIn("someone@example.invalid", result.stderr)

    def test_full_initial_template_without_ledger_can_start_but_shallow_missing_ledger_refuses(self):
        repo, clone = self.base / "source", self.base / "shallow"
        seed(repo, ledger=False)
        git(self.base, "clone", "--depth=1", repo.as_uri(), str(clone))
        refused = run_daily(clone, "--fast", "--through", START.isoformat())
        self.assertNotEqual(refused.returncode, 0)
        self.assertFalse((clone / "data/activity.json").exists())
        result = run_daily(repo, "--fast", "--through", START.isoformat())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["created_commits"], daily.planned_count(START))

    def test_configured_timezone_and_both_commit_identities_replace_local_defaults(self):
        repo = self.base / "sample"
        config = {**SAMPLE, "timezone": "Pacific/Honolulu"}
        seed(repo, config)
        result = run_daily(repo, "--fast", "--through", START.isoformat(), config=config)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = git(repo, "log", "-1", "--format=%an%x00%ae%x00%cn%x00%ce%x00%aI%x00%cI").stdout.strip().split("\x00")
        self.assertEqual(row[:4], ["sample-user", SAMPLE["author_email"], "sample-user", SAMPLE["author_email"]])
        expected = datetime(START.year, START.month, START.day, 9, 10 + daily.planned_count(START),
                            tzinfo=ZoneInfo(config["timezone"])).isoformat()
        self.assertEqual(row[4:], [expected, expected])
        self.assertEqual(json.loads((repo / "data/activity.json").read_text())["timezone"], config["timezone"])
        self.assertEqual(git(repo, "show", "--format=", "--name-only", "HEAD").stdout.strip(), "data/activity.json")

    def test_partial_final_day_recovers_from_committed_head_instead_of_uncommitted_worktree(self):
        repo = self.base / "sample"
        seed(repo)
        completed = run_daily(repo, "--fast", "--through", START.isoformat())
        self.assertEqual(completed.returncode, 0, completed.stderr)
        total = daily.planned_count(START)
        git(repo, "reset", "--hard", "HEAD~" + str(total - 1))
        self.assertEqual(json.loads((repo / "data/activity.json").read_text())["days"][START.isoformat()]["commits"], 1)
        write_ledger(repo, {START.isoformat(): {"commits": total, "planned": total}})
        result = run_daily(repo, "--fast", "--through", START.isoformat())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["created_commits"], total - 1)
        self.assertEqual(git(repo, "status", "--porcelain").stdout, "")

    def test_missing_or_empty_ledger_with_existing_marker_never_restarts_the_day(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                repo = self.base / ("missing" if missing else "empty")
                seed(repo)
                result = run_daily(repo, "--fast", "--through", START.isoformat())
                self.assertEqual(result.returncode, 0, result.stderr)
                if missing:
                    (repo / "data/activity.json").unlink()
                else:
                    write_ledger(repo, {})
                commit_ledger(repo)
                head = git(repo, "rev-parse", "HEAD").stdout
                refused = run_daily(repo, "--fast", "--through", START.isoformat())
                self.assertNotEqual(refused.returncode, 0)
                self.assertEqual(git(repo, "rev-parse", "HEAD").stdout, head)

    def test_corrupt_or_incomplete_earlier_ledger_is_refused_without_writes(self):
        repo = self.base / "sample"
        seed(repo)
        day2 = START + timedelta(days=1)
        total = daily.planned_count(START)
        cases = [
            {START.isoformat(): {"commits": True, "planned": total}},
            {START.isoformat(): {"commits": 1, "planned": total}, day2.isoformat(): {"commits": 1, "planned": daily.planned_count(day2)}},
            {day2.isoformat(): {"commits": 1, "planned": daily.planned_count(day2)}},
            {START.isoformat(): {"commits": total, "planned": total + 1}},
        ]
        for index, days in enumerate(cases):
            write_ledger(repo, days)
            commit_ledger(repo, f"Corrupt fixture {index}")
            head = git(repo, "rev-parse", "HEAD").stdout
            result = run_daily(repo, "--fast", "--through", day2.isoformat())
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(git(repo, "rev-parse", "HEAD").stdout, head)

    def test_unrelated_staged_or_untracked_files_are_never_included_even_on_first_run(self):
        for staged in (False, True):
            with self.subTest(staged=staged):
                repo = self.base / ("staged" if staged else "untracked")
                seed(repo)
                (repo / "notes.txt").write_text("This file must not enter an automated commit.\n")
                if staged:
                    git(repo, "add", "notes.txt")
                before = git(repo, "rev-parse", "HEAD").stdout
                result = run_daily(repo, "--fast", "--through", START.isoformat())
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(git(repo, "rev-parse", "HEAD").stdout, before)
                self.assertEqual(json.loads((repo / "data/activity.json").read_text())["days"], {})

    def test_audit_and_dry_run_are_read_only_and_future_or_changed_start_are_refused(self):
        repo = self.base / "sample"
        seed(repo)
        before = git(repo, "rev-parse", "HEAD").stdout
        dry = run_daily(repo, "--fast", "--dry-run", "--through", START.isoformat())
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(json.loads(dry.stdout)["missing_commits"], daily.planned_count(START))
        audit = run_daily(repo, "--audit", "--through", START.isoformat())
        self.assertEqual(audit.returncode, 1)
        for arguments in (("--through", "2999-01-01"), ("--start", "2001-02-02", "--through", START.isoformat())):
            result = run_daily(repo, "--fast", *arguments)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(repo, "rev-parse", "HEAD").stdout, before)
        self.assertEqual(git(repo, "status", "--porcelain").stdout, "")

    def test_script_cannot_write_another_checkout_when_invoked_by_absolute_path(self):
        source, other = self.base / "source", self.base / "other"
        seed(source)
        seed(other)
        before = git(other, "rev-parse", "HEAD").stdout
        result = run_daily(source, "--fast", "--through", START.isoformat(), cwd=other)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(git(other, "rev-parse", "HEAD").stdout, before)


if __name__ == "__main__":
    unittest.main()
