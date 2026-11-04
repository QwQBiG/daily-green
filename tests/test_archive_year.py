"""Exercise year archives with disposable Git repositories and no network."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import archive_year as archive


LOGIN = "sample-user"
EMAIL = f"1000+{LOGIN}@users.noreply.github.com"


def git(directory, *arguments):
    return subprocess.run(
        ["git", *arguments], cwd=directory, check=True, text=True, capture_output=True
    ).stdout.strip()


class SelectedDaysTests(unittest.TestCase):
    def test_sparse_dates_and_overlapping_leap_ranges_are_sorted_and_deduplicated(self):
        today = date(2026, 5, 19)
        selected = archive.selected_days(
            2024, ["12-31", "02-29", "02-28..03-01", "01-10"], today
        )
        self.assertEqual(
            selected,
            (date(2024, 1, 10), date(2024, 2, 28), date(2024, 2, 29),
             date(2024, 3, 1), date(2024, 12, 31)),
        )

    def test_epoch_and_current_day_are_supported(self):
        today = date(2026, 5, 19)
        self.assertEqual(archive.selected_days(1970, ["01-01"], today), (date(1970, 1, 1),))
        self.assertEqual(archive.selected_days(2026, ["05-19"], today), (today,))

    def test_invalid_dates_reversed_ranges_and_unsupported_years_are_refused(self):
        today = date(2026, 5, 19)
        for year, spec in (
            (2026, "05-20"), (2026, "05-19..05-20"), (2024, "03-01..02-29"),
            (2023, "02-29"), (2024, "02-30"), (2024, "12-31..01-01"),
            (2024, "today"), (1969, "12-31"), (2027, "01-01"),
        ):
            with self.subTest(year=year, spec=spec), self.assertRaises(archive.ArchiveError):
                archive.selected_days(year, [spec], today)


class ArchiveCommandTests(unittest.TestCase):
    identity = {"type": "User", "login": LOGIN, "id": 1000}
    target = f"{LOGIN}/garden-1970"
    arguments = ["1970", "--days", "01-01", "01-03", "--name", "garden-1970"]

    def run_command(self, *extra, commits_per_day=3):
        arguments = list(self.arguments)
        if commits_per_day is not None:
            arguments.extend(["--commits-per-day", str(commits_per_day)])
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            result = archive.main([*arguments, *extra])
        return result, output.getvalue(), errors.getvalue()

    def test_preview_uses_only_reads_and_reports_selected_count(self):
        with patch.object(archive, "github", side_effect=[self.identity, None]) as github, \
                patch.object(archive, "build_history") as build, patch.object(archive, "publish_history") as publish:
            result, output, errors = self.run_command()
        self.assertEqual(result, 0, errors)
        self.assertIn("2 distinct day(s), 6 new commit(s)", output)
        self.assertIn("Preview only", output)
        self.assertEqual(github.call_args_list, [call("user"), call(f"repos/{self.target}", allow_missing=True)])
        build.assert_not_called()
        publish.assert_not_called()

    def test_preview_accepts_large_custom_counts_and_keeps_the_default_cadence(self):
        for count, expected in ((233, 466), (None, 7)):
            with self.subTest(commits_per_day=count), \
                    patch.object(archive, "github", side_effect=[self.identity, None]):
                result, output, errors = self.run_command(commits_per_day=count)
                self.assertEqual(result, 0, errors)
                self.assertIn(f"2 distinct day(s), {expected} new commit(s)", output)

    def test_nonpositive_counts_fail_before_github_access(self):
        for count in (0, -1):
            with self.subTest(commits_per_day=count), patch.object(archive, "github") as github:
                result, _, errors = self.run_command(commits_per_day=count)
                self.assertEqual(result, 1)
                self.assertIn("--commits-per-day", errors)
                github.assert_not_called()

    def test_apply_creates_a_private_repository_then_uses_its_default_branch(self):
        metadata = {
            "full_name": self.target,
            "private": True,
            "fork": False,
            "description": archive.description(1970),
            "permissions": {"push": True},
            "default_branch": "trunk",
        }
        expected_payload = {
            "name": "garden-1970",
            "private": True,
            "auto_init": False,
            "description": archive.description(1970),
        }

        def inspect_publish(directory, url, branch, base, head):
            self.assertEqual((url, branch, base), (f"https://github.com/{self.target}.git", "trunk", None))
            self.assertEqual(git(directory, "rev-list", "--count", head), "6")
            self.assertEqual(git(directory, "log", "-1", "--format=%ae", head), EMAIL)
            return True

        with patch.object(archive, "github", side_effect=[self.identity, None, metadata, metadata]) as github, \
                patch.object(archive, "publish_history", side_effect=inspect_publish) as publish:
            result, output, errors = self.run_command("--apply")
        self.assertEqual(result, 0, errors)
        self.assertIn(f"https://github.com/{self.target}", output)
        self.assertEqual(
            github.call_args_list,
            [call("user"), call(f"repos/{self.target}", allow_missing=True),
             call("user/repos", payload=expected_payload), call(f"repos/{self.target}")],
        )
        publish.assert_called_once()

    def test_same_name_public_repository_is_never_a_write_target(self):
        metadata = {
            "full_name": self.target,
            "private": False,
            "fork": False,
            "description": archive.description(1970),
            "permissions": {"push": True},
            "default_branch": "trunk",
        }
        with patch.object(archive, "github", side_effect=[self.identity, metadata]) as github, \
                patch.object(archive, "publish_history") as publish:
            result, _, errors = self.run_command("--apply")
        self.assertEqual(result, 1)
        self.assertIn("different repository", errors)
        self.assertEqual(github.call_args_list, [call("user"), call(f"repos/{self.target}", allow_missing=True)])
        publish.assert_not_called()


class ArchiveGitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        git_environment = patch.dict(
            os.environ,
            {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        )
        git_environment.start()
        self.addCleanup(git_environment.stop)

    def directory(self, name):
        directory = self.root / name
        directory.mkdir()
        return directory

    def build(self, name, year, targets):
        directory = self.directory(name)
        archive.initialize(directory)
        head = archive.build_history(directory, year, targets, LOGIN, EMAIL)
        self.assertEqual(git(directory, "rev-parse", "--is-bare-repository"), "true")
        git(directory, "cat-file", "-e", f"{head}^{{commit}}")
        return directory, head

    def remote(self, name, branch="trunk"):
        directory = self.directory(name)
        git(directory, "init", "--bare", f"--initial-branch={branch}")
        return directory

    def manifest(self, directory, revision):
        return json.loads(git(directory, "show", f"{revision}:data/activity.json"))

    def test_epoch_history_is_deterministic_and_has_only_selected_utc_noreply_commits(self):
        targets = {date(1970, 1, 1): 2, date(1970, 1, 3): 1}
        directory, head = self.build("first", 1970, targets)
        _, repeated_head = self.build("repeat", 1970, dict(reversed(tuple(targets.items()))))
        self.assertEqual(head, repeated_head)
        rows = git(
            directory, "log", "--reverse", "--format=%H%x00%aI%x00%cI%x00%an%x00%cn%x00%ae%x00%ce%x00%s", head
        )
        expected_markers = [(date(1970, 1, 1), 1), (date(1970, 1, 1), 2), (date(1970, 1, 3), 1)]
        expected_days = {}
        self.assertEqual(len(rows.splitlines()), len(expected_markers))
        for row, (day, sequence) in zip(rows.splitlines(), expected_markers):
            sha, author_date, committer_date, author, committer, email, committer_email, subject = row.split("\x00")
            self.assertEqual((author, committer, email, committer_email), (LOGIN, LOGIN, EMAIL, EMAIL))
            self.assertEqual(author_date, committer_date)
            timestamp = datetime.fromisoformat(author_date.replace("Z", "+00:00"))
            self.assertEqual((timestamp.date(), timestamp.utcoffset()), (day, timedelta(0)))
            self.assertEqual(subject, f"chore: archive daily green {day} #{sequence}")
            expected_days[day.isoformat()] = sequence
            self.assertEqual(
                self.manifest(directory, sha),
                {"version": 1, "year": 1970, "timezone": "UTC", "days": expected_days},
            )
        self.assertEqual(
            git(directory, "ls-tree", "-r", "--name-only", head).splitlines(),
            ["README.md", "data/activity.json"],
        )

    def test_existing_archive_can_add_older_dates_or_increase_counts_without_rewriting(self):
        old, leap, later = date(2024, 1, 10), date(2024, 2, 29), date(2024, 12, 31)
        directory, head = self.build("leap", 2024, {leap: 2, later: 2})
        self.assertEqual(
            archive.build_history(directory, 2024, {leap: 1, later: 2}, LOGIN, EMAIL, base=head),
            head,
        )
        updated = archive.build_history(directory, 2024, {old: 1, leap: 3}, LOGIN, EMAIL, base=head)
        self.assertEqual(
            git(directory, "log", "--reverse", "--format=%s", f"{head}..{updated}").splitlines(),
            [f"chore: archive daily green {old} #1", f"chore: archive daily green {leap} #3"],
        )
        self.assertEqual(git(directory, "rev-parse", f"{updated}~2"), head)
        self.assertEqual(
            self.manifest(directory, updated)["days"],
            {old.isoformat(): 1, leap.isoformat(): 3, later.isoformat(): 2},
        )

    def test_large_backfill_preserves_existing_commits_and_stays_on_the_selected_utc_day(self):
        day = date(2001, 12, 31)
        original_count, target_count = 20, 721
        directory, base = self.build("large", day.year, {day: original_count})
        head = archive.build_history(directory, day.year, {day: target_count}, LOGIN, EMAIL, base=base)
        self.assertEqual(git(directory, "rev-parse", f"{head}~{target_count - original_count}"), base)

        rows = git(directory, "log", "--reverse", "--format=%aI%x00%cI", head).splitlines()
        self.assertEqual(len(rows), target_count)
        timestamps = []
        for row in rows:
            author, committer = row.split("\x00")
            self.assertEqual(author, committer)
            timestamp = datetime.fromisoformat(author.replace("Z", "+00:00"))
            self.assertEqual((timestamp.date(), timestamp.utcoffset()), (day, timedelta(0)))
            timestamps.append(timestamp.time().isoformat())
        self.assertEqual(timestamps[:original_count], [f"12:{index:02d}:00" for index in range(1, 21)])
        self.assertEqual(timestamps[-2:], ["23:59:59", "23:59:59"])
        self.assertEqual(self.manifest(directory, head)["days"], {day.isoformat(): target_count})
        self.assertEqual(
            archive.build_history(directory, day.year, {day: target_count}, LOGIN, EMAIL, base=head),
            head,
        )

    def test_publish_respects_default_branch_and_can_retry_same_head(self):
        day = date(1970, 1, 2)
        directory, head = self.build("archive", 1970, {day: 1})
        remote = self.remote("remote")
        for expected in (True, False):
            self.assertIs(archive.publish_history(directory, remote.as_uri(), "trunk", None, head), expected)
            self.assertEqual(git(remote, "rev-parse", "refs/heads/trunk"), head)
            self.assertEqual(git(remote, "for-each-ref", "--format=%(refname)"), "refs/heads/trunk")
        updated = archive.build_history(directory, 1970, {day: 2}, LOGIN, EMAIL, base=head)
        self.assertIs(archive.publish_history(directory, remote.as_uri(), "trunk", head, updated), True)
        self.assertEqual(git(remote, "rev-parse", "refs/heads/trunk"), updated)

    def test_publish_refuses_divergent_and_unexpected_remote_refs(self):
        day = date(1970, 1, 2)
        directory, head = self.build("archive", 1970, {day: 1})
        other, other_head = self.build("other", 1971, {date(1971, 1, 2): 1})
        for branch in ("trunk", "unrelated"):
            with self.subTest(branch=branch):
                remote = self.remote("remote-" + branch)
                git(other, "push", remote.as_uri(), f"{other_head}:refs/heads/{branch}")
                with self.assertRaises(archive.ArchiveError):
                    archive.publish_history(directory, remote.as_uri(), "trunk", None, head)
                self.assertEqual(
                    git(remote, "for-each-ref", "--format=%(objectname) %(refname)"),
                    f"{other_head} refs/heads/{branch}",
                )

    def test_publish_rejects_stale_base_after_another_append(self):
        day = date(1970, 1, 2)
        directory, head = self.build("archive", 1970, {day: 1})
        remote = self.remote("remote")
        archive.publish_history(directory, remote.as_uri(), "trunk", None, head)
        other = self.directory("concurrent")
        archive.initialize(other)
        git(other, "fetch", remote.as_uri(), "refs/heads/trunk")
        first = archive.build_history(directory, 1970, {day: 2}, LOGIN, EMAIL, base=head)
        second = archive.build_history(other, 1970, {date(1970, 2, 2): 1}, LOGIN, EMAIL, base=head)
        archive.publish_history(directory, remote.as_uri(), "trunk", head, first)
        with self.assertRaises(archive.ArchiveError):
            archive.publish_history(other, remote.as_uri(), "trunk", head, second)
        self.assertEqual(git(remote, "rev-parse", "refs/heads/trunk"), first)


if __name__ == "__main__":
    unittest.main()
