#!/usr/bin/env python3
"""Generate explicitly automated decorative activity, not records of real work."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, time, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from greenhouse_config import load_config, require_automation


try:
    CONFIG = load_config()
except (ValueError, OSError):
    # Also protects imports from the review/summary entry points.
    if __name__ == '__main__' or (sys.argv and Path(sys.argv[0]).name in {'daily_review.py', 'report_status.py'}):
        print('Invalid instance configuration; run setup or check GREENHOUSE_CONFIG.', file=sys.stderr)
        raise SystemExit(1) from None
    raise
ZONE = CONFIG.zone
# The fallback supports pure local card helpers; automation requires a configured start.
DEFAULT_START = CONFIG.start_date or date(2000, 1, 1)
SOURCE_ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("data/activity.json")
PREFIX = "chore: daily green "
MARKER = re.compile(r"^chore: daily green (\d{4}-\d{2}-\d{2}) ([1-6])/([2-6])$")


def git(*args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # Batch backfills write many objects quickly. Avoid competing automatic
    # garbage collection / background maintenance during these Git commands.
    return subprocess.run(
        ["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
        check=check, text=True, capture_output=True, env=env,
    )


def planned_count(day: date) -> int:
    digest = hashlib.sha256(f"daily-green-v1:{day.isoformat()}".encode()).digest()
    return 2 + int.from_bytes(digest[:8], "big") % 5


def days_between(start: date, through: date):
    day = start
    while day <= through:
        yield day
        if day == through:
            break
        day += timedelta(days=1)


def commit_timestamp(day: date, sequence: int) -> str:
    return datetime.combine(day, time(9, 10 + sequence), ZONE).isoformat()


def has_head() -> bool:
    return git("rev-parse", "--verify", "HEAD", check=False).returncode == 0


def read_history(author_email: str) -> dict[date, set[int]]:
    """Validate markers and return sequences from successful commits only."""
    if not has_head():
        return {}
    log = git("log", "--format=%H%x00%s%x00%aI%x00%cI%x00%ae%x00%ce%x1e").stdout
    history: dict[date, set[int]] = {}
    for record in log.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, author_date, committer_date, email, committer_email = record.split("\x00")
        if not subject.startswith(PREFIX):
            continue
        match = MARKER.fullmatch(subject)
        if not match:
            raise ValueError(f"Invalid daily marker in {sha[:12]}: {subject}")
        day = date.fromisoformat(match[1])
        sequence, count = int(match[2]), int(match[3])
        if count != planned_count(day) or sequence > count:
            raise ValueError(f"Invalid daily sequence/count in {sha[:12]}")
        expected_time = commit_timestamp(day, sequence)
        if author_date != expected_time or committer_date != expected_time:
            raise ValueError(f"Wrong author/committer date in {sha[:12]}")
        if email.lower() != author_email.lower() or committer_email.lower() != author_email.lower():
            raise ValueError(f"Wrong contributor email in {sha[:12]}")
        sequences = history.setdefault(day, set())
        if sequence in sequences:
            raise ValueError(f"Duplicate marker for {day}, sequence {sequence}")
        sequences.add(sequence)
    for day, sequences in history.items():
        if sequences != set(range(1, len(sequences) + 1)):
            raise ValueError(f"Non-contiguous committed sequences for {day}")
    return history


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate ledger key")
        result[key] = value
    return result


def has_daily_markers() -> bool:
    return has_head() and any(
        subject.startswith(PREFIX) for subject in git("log", "--format=%s").stdout.splitlines()
    )


def read_committed_ledger(start: date) -> dict[date, set[int]]:
    """Read only HEAD's validated snapshot, allowing a shallow daily checkout."""
    if not has_head():
        return {}
    present = git("ls-tree", "--name-only", "HEAD", "--", LEDGER.as_posix()).stdout.strip()
    if not present:
        # A shallow checkout cannot prove a marker absent from omitted history.
        if git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
            raise ValueError("A shallow first run needs the configured empty ledger from setup")
        if has_daily_markers():
            raise ValueError("Committed ledger is missing despite existing daily markers")
        return {}
    raw = git("show", f"HEAD:{LEDGER.as_posix()}").stdout
    ledger = json.loads(raw, object_pairs_hook=unique_json_object)
    if not isinstance(ledger, dict) or set(ledger) != {"timezone", "start_date", "days"}:
        raise ValueError("Invalid committed ledger schema")
    if ledger["timezone"] != CONFIG.timezone or ledger["start_date"] != start.isoformat():
        raise ValueError("Committed ledger timezone/start date does not match")
    if not isinstance(ledger["days"], dict):
        raise ValueError("Committed ledger days must be an object")
    if not ledger["days"] and has_daily_markers():
        raise ValueError("Empty committed ledger conflicts with existing daily markers")
    today = datetime.now(ZONE).date()
    expected_day = start
    history: dict[date, set[int]] = {}
    entries = sorted(ledger["days"].items())
    for index, (day_text, entry) in enumerate(entries):
        day = date.fromisoformat(day_text)
        if day.isoformat() != day_text or day != expected_day or day > today:
            raise ValueError(f"Invalid or non-contiguous ledger date: {day_text}")
        if not isinstance(entry, dict) or set(entry) != {"commits", "planned"}:
            raise ValueError(f"Invalid ledger entry for {day}")
        count, planned = entry["commits"], entry["planned"]
        if type(count) is not int or type(planned) is not int:
            raise ValueError(f"Ledger counts must be integers for {day}")
        if planned != planned_count(day) or not 1 <= count <= planned:
            raise ValueError(f"Invalid ledger counts for {day}")
        if index < len(entries) - 1 and count != planned:
            raise ValueError(f"Only the final ledger day may be incomplete: {day}")
        history[day] = set(range(1, count + 1))
        expected_day += timedelta(days=1)
    return history


def check_worktree() -> None:
    # A process killed during an atomic ledger write may leave its ignored
    # scratch file behind. Only this script's scratch files are removed.
    for scratch in LEDGER.parent.glob(".daily-green-*.tmp"):
        scratch.unlink()
    changed: set[str] = set()
    for args in (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        changed.update(filter(None, git(*args).stdout.split("\x00")))
    unrelated = changed - {LEDGER.as_posix()}
    if unrelated:
        raise ValueError("Commit or remove unrelated local changes first: " + ", ".join(sorted(unrelated)))


def save_ledger(history: dict[date, set[int]], start: date) -> None:
    contents = {
        "timezone": CONFIG.timezone,
        "start_date": start.isoformat(),
        "days": {
            day.isoformat(): {"commits": len(history[day]), "planned": planned_count(day)}
            for day in sorted(history)
        },
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=LEDGER.parent,
            prefix=".daily-green-", suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(contents, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, LEDGER)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def summary(start: date, through: date, history: dict[date, set[int]]) -> dict:
    days = list(days_between(start, through))
    missing = {
        day.isoformat(): planned_count(day) - len(history.get(day, set()))
        for day in days
        if len(history.get(day, set())) != planned_count(day)
    }
    return {
        "start": start.isoformat(),
        "through": through.isoformat(),
        "days": len(days),
        "planned_commits": sum(planned_count(day) for day in days),
        "existing_commits": sum(len(history.get(day, set())) for day in days),
        "missing_commits": sum(missing.values()),
        "daily_distribution": dict(sorted(Counter(planned_count(day) for day in days).items())),
        "incomplete_days": missing,
    }


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--through", type=date.fromisoformat, default=datetime.now(ZONE).date())
    parser.add_argument("--fast", action="store_true", help="Use HEAD's committed ledger for shallow daily runs")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--audit", action="store_true", help="Verify the requested range without writing")
    modes.add_argument("--dry-run", action="store_true", help="Report outstanding commits without writing")
    args = parser.parse_args()
    require_automation(CONFIG)
    if args.start != CONFIG.start_date:
        raise ValueError("--start must match the configured start date")
    if args.audit and args.fast:
        parser.error("--audit cannot be combined with --fast; an audit requires full Git history")
    if args.start > args.through:
        raise ValueError("--start must be on or before --through")
    if args.through > datetime.now(ZONE).date():
        raise ValueError("--through cannot be later than today in the configured timezone")
    root = git("rev-parse", "--show-toplevel").stdout.strip()
    if Path(root).resolve() != SOURCE_ROOT:
        raise ValueError("Run this repository's own script from its checkout")
    os.chdir(root)
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    if branch.returncode or branch.stdout.strip() != "main":
        raise ValueError("Run on the main branch")
    if not args.fast and git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        raise ValueError("Full history mode needs an unshallow clone; use --fast for daily runs")
    history = read_committed_ledger(args.start) if args.fast else read_history(CONFIG.author_email)
    if any(day < args.start for day in history):
        raise ValueError("Existing daily history starts before the configured start date")
    if args.audit or args.dry_run:
        report = summary(args.start, args.through, history)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if args.audit and report["missing_commits"] else 0
    check_worktree()
    created = 0
    for day in days_between(args.start, args.through):
        count = planned_count(day)
        committed = history.setdefault(day, set())
        for sequence in range(len(committed) + 1, count + 1):
            # Write the next snapshot, but only advance the history after Git's
            # atomic commit succeeds. A retry rebuilds this snapshot from Git.
            next_history = {key: set(value) for key, value in history.items()}
            next_history[day].add(sequence)
            save_ledger(next_history, args.start)
            git("add", "--", LEDGER.as_posix())
            timestamp = commit_timestamp(day, sequence)
            env = os.environ.copy()
            env.update({
                "GIT_AUTHOR_NAME": CONFIG.author_name,
                "GIT_AUTHOR_EMAIL": CONFIG.author_email,
                "GIT_COMMITTER_NAME": CONFIG.author_name,
                "GIT_COMMITTER_EMAIL": CONFIG.author_email,
                "GIT_AUTHOR_DATE": timestamp,
                "GIT_COMMITTER_DATE": timestamp,
            })
            git("commit", "--no-gpg-sign", "--message", f"{PREFIX}{day.isoformat()} {sequence}/{count}", env=env)
            committed.add(sequence)
            created += 1
    if args.fast:
        if read_committed_ledger(args.start) != history:
            raise ValueError("Committed ledger does not match the generated sequences")
        verified_history = history
    else:
        verified_history = read_history(CONFIG.author_email)
    report = summary(args.start, args.through, verified_history)
    report["created_commits"] = created
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["missing_commits"] else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or str(error), file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
