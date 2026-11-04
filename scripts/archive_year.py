#!/usr/bin/env python3
"""Add selected dates to your own private Daily Green year archive."""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory, TemporaryFile

from activity_dates import days_between, planned_count

FIRST_YEAR = 1970
MANIFEST = "data/activity.json"
LOCAL_REF = "refs/heads/archive"
LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
SHA = re.compile(r"[0-9a-f]{40}")
GIT_LOCAL_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR",
}


class ArchiveError(Exception):
    pass


def selected_days(year, specifications, today):
    if not FIRST_YEAR <= year <= today.year:
        raise ArchiveError(f"Choose a year from {FIRST_YEAR} through {today.year} (UTC).")
    days = set()
    for specification in specifications:
        if not re.fullmatch(r"[0-9]{2}-[0-9]{2}(?:\.\.[0-9]{2}-[0-9]{2})?", specification):
            raise ArchiveError("Use MM-DD or MM-DD..MM-DD for each date selection.")
        endpoints = specification.split("..")
        try:
            start = date.fromisoformat(f"{year}-{endpoints[0]}")
            end = date.fromisoformat(f"{year}-{endpoints[-1]}")
        except ValueError:
            raise ArchiveError(f"Invalid calendar date in {specification} for {year}.") from None
        if end < start or end > today:
            raise ArchiveError("Date ranges must be in order and end on or before today (UTC).")
        days.update(days_between(start, end))
    if not days:
        raise ArchiveError("Select at least one date with --days.")
    return tuple(sorted(days))


def github(endpoint, *, payload=None, allow_missing=False):
    args = ["gh", "api", "--hostname", "github.com", endpoint]
    if payload is not None:
        args += ["--method", "POST", "--input", "-"]
    try:
        result = subprocess.run(args, input=json.dumps(payload) if payload is not None else None,
                                text=True, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise ArchiveError("GitHub CLI timed out. Check your connection and try again.") from None
    if result.returncode:
        if allow_missing and result.stderr.rstrip().endswith("(HTTP 404)"):
            return None
        raise ArchiveError("GitHub request failed. Check GitHub CLI sign-in and repository access.")
    return json.loads(result.stdout)


def git(directory, *args, check=True, stdin=None, network=False):
    env = {key: value for key, value in os.environ.items() if key not in GIT_LOCAL_ENV}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    command = ["git", "-c", f"core.hooksPath={os.devnull}"]
    if network:
        command += ["-c", "credential.https://github.com.helper=!gh auth git-credential"]
    try:
        result = subprocess.run([*command, *args], cwd=directory, env=env, stdin=stdin,
                                text=True, capture_output=True, timeout=90 if network else None)
    except subprocess.TimeoutExpired:
        raise ArchiveError(f"Git {args[0]} timed out. Check your connection and try again.") from None
    if check and result.returncode:
        raise ArchiveError(f"Git {args[0]} failed. Check Git, GitHub CLI sign-in, and repository access.")
    return result


def initialize(directory):
    git(directory, "init", "--bare", "--template=", "--initial-branch=main", "--object-format=sha1")


def description(year):
    return f"Daily Green {year} · decorative activity archive"


def archive_readme(year):
    return (f"# Daily Green {year}\n\n"
            "This archive contains automatically generated decorative activity for selected dates (UTC). "
            "The commits do not represent past work or code reviews.\n")


def manifest_text(manifest):
    return json.dumps(manifest, sort_keys=True, indent=2) + "\n"


def read_manifest(directory, year, base):
    if base is None:
        return {}
    files = git(directory, "ls-tree", "-r", "--name-only", base).stdout.splitlines()
    if files != ["README.md", MANIFEST] or git(directory, "show", f"{base}:README.md").stdout != archive_readme(year):
        raise ArchiveError("The existing branch is not a Daily Green archive for this year.")
    raw = git(directory, "show", f"{base}:{MANIFEST}").stdout
    data = json.loads(raw)
    if (not isinstance(data, dict) or set(data) != {"version", "year", "timezone", "days"}
            or type(data["version"]) is not int or data["version"] != 1
            or type(data["year"]) is not int or data["year"] != year
            or data["timezone"] != "UTC" or not isinstance(data["days"], dict) or not data["days"]
            or raw != manifest_text(data)):
        raise ArchiveError("The existing archive manifest is invalid.")
    for key, count in data["days"].items():
        day = date.fromisoformat(key)
        if (day.isoformat() != key or day.year != year or day > datetime.now(timezone.utc).date()
                or type(count) is not int or count < 1):
            raise ArchiveError("The existing archive manifest contains invalid dates or counts.")
    return data["days"]


def write_data(stream, content):
    payload = content.encode("utf-8")
    stream.write(f"data {len(payload)}\n".encode())
    stream.write(payload + b"\n")


def build_history(directory, year, targets, login, email, base=None):
    days = read_manifest(directory, year, base)
    if all(days.get(day.isoformat(), 0) >= count for day, count in targets.items()):
        return base

    # Each commit updates the manifest. A single import builds the whole batch locally.
    with TemporaryFile() as stream:
        first = True
        for day, target in sorted(targets.items()):
            key = day.isoformat()
            noon = int(datetime.combine(day, time(12), timezone.utc).timestamp())
            day_end = int(datetime.combine(day, time(23, 59, 59), timezone.utc).timestamp())
            for sequence in range(days.get(key, 0) + 1, target + 1):
                # Preserve the original minute spacing without spilling into the next day.
                timestamp = min(noon + sequence * 60, day_end)
                identity = f"{login} <{email}> {timestamp} +0000"
                stream.write(f"commit {LOCAL_REF}\nauthor {identity}\ncommitter {identity}\n".encode())
                write_data(stream, f"chore: archive daily green {key} #{sequence}\n")
                if first and base:
                    stream.write(f"from {base}\n".encode())
                if first and base is None:
                    stream.write(b"M 100644 inline README.md\n")
                    write_data(stream, archive_readme(year))
                first = False
                days[key] = sequence
                manifest = {"version": 1, "year": year, "timezone": "UTC", "days": days}
                stream.write(f"M 100644 inline {MANIFEST}\n".encode())
                write_data(stream, manifest_text(manifest))
                stream.write(b"\n")
        stream.write(b"done\n")
        stream.seek(0)
        git(directory, "fast-import", "--quiet", "--done", stdin=stream)
    return git(directory, "rev-parse", LOCAL_REF).stdout.strip()


def verify_repository(metadata, target, year):
    if (not isinstance(metadata, dict) or metadata.get("full_name", "").lower() != target.lower()
            or metadata.get("private") is not True or metadata.get("fork") is not False
            or metadata.get("archived") or metadata.get("is_template")
            or metadata.get("description") != description(year)
            or not metadata.get("permissions", {}).get("push")):
        raise ArchiveError("That name belongs to a different repository. Choose another --name.")
    branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise ArchiveError("GitHub did not return a default branch.")
    return branch


def remote_head(directory, url, branch):
    ref = f"refs/heads/{branch}"
    git(directory, "check-ref-format", ref)
    refs = git(directory, "ls-remote", "--refs", url, network=True).stdout.splitlines()
    if not refs:
        return None
    if len(refs) == 1:
        sha, separator, name = refs[0].partition("\t")
        if separator and name == ref and SHA.fullmatch(sha):
            return sha
    raise ArchiveError("The target contains unexpected branches or tags. No push was made.")


def publish_history(directory, url, branch, base, head):
    current = remote_head(directory, url, branch)
    if current == head:
        return False
    if current != base:
        raise ArchiveError("The archive changed during preparation. Run the same command again.")
    if base and git(directory, "merge-base", "--is-ancestor", base, head, check=False).returncode:
        raise ArchiveError("The generated history does not extend the archive. No push was made.")
    try:
        git(directory, "push", url, f"{head}:refs/heads/{branch}", network=True, check=False)
    except ArchiveError:
        # A timed-out push may have reached the server.
        if remote_head(directory, url, branch) == head:
            return True
        raise
    if remote_head(directory, url, branch) != head:
        raise ArchiveError("Push could not be confirmed. Check access and run the same command again.")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, help="Calendar year (1970 through the current UTC year)")
    parser.add_argument("--days", nargs="+", required=True, metavar="MM-DD",
                        help="Selected dates or inclusive MM-DD..MM-DD ranges")
    parser.add_argument("--commits-per-day", type=int, metavar="N",
                        help="Positive commit target for each selected day; default is 2–6 by date")
    parser.add_argument("--name", help="Private repository name; default daily-green-YEAR")
    parser.add_argument("--apply", action="store_true", help="Create or update the archive; otherwise preview")
    args = parser.parse_args(argv)
    try:
        days = selected_days(args.year, args.days, datetime.now(timezone.utc).date())
        count = args.commits_per_day
        if count is not None and count < 1:
            raise ArchiveError("--commits-per-day must be a positive integer.")
        name = args.name or f"daily-green-{args.year}"
        if not NAME.fullmatch(name) or name.lower().endswith(".git"):
            raise ArchiveError("Use a GitHub repository name, without an owner or .git suffix.")
        identity = github("user")
        login, user_id = identity.get("login"), identity.get("id")
        if (identity.get("type") != "User" or not isinstance(login, str) or not LOGIN.fullmatch(login)
                or type(user_id) is not int or user_id <= 0):
            raise ArchiveError("Sign in to GitHub CLI with your own user account.")
        target = f"{login}/{name}"
        endpoint = f"repos/{target}"
        url = f"https://github.com/{target}.git"
        metadata = github(endpoint, allow_missing=True)
        targets = {day: count if count is not None else planned_count(day) for day in days}
        with TemporaryDirectory(prefix="daily-green-archive-") as scratch:
            directory = Path(scratch)
            initialize(directory)
            base = None
            if metadata is not None:
                branch = verify_repository(metadata, target, args.year)
                base = remote_head(directory, url, branch)
                if base:
                    git(directory, "fetch", "--no-tags", url, f"refs/heads/{branch}", network=True)
                    if git(directory, "rev-parse", "FETCH_HEAD").stdout.strip() != base:
                        raise ArchiveError("The archive changed during preparation. Run the same command again.")
            recorded = read_manifest(directory, args.year, base)
            added = sum(max(0, goal - recorded.get(day.isoformat(), 0)) for day, goal in targets.items())
            print(f"Private archive: {target}")
            print(f"Selected (UTC): {', '.join(args.days)} · {len(days)} distinct day(s), {added} new commit(s).")
            if not args.apply:
                print("Preview only. Add --apply to publish.")
                return 0
            if not added:
                print(f"Already up to date: https://github.com/{target}")
                return 0
            email = f"{user_id}+{login}@users.noreply.github.com"
            head = build_history(directory, args.year, targets, login, email, base)
            if metadata is None:
                try:
                    github("user/repos", payload={"name": name, "private": True, "auto_init": False,
                                                 "description": description(args.year)})
                except ArchiveError:
                    # The write may have succeeded even if the response was lost.
                    metadata = github(endpoint, allow_missing=True)
                    if metadata is None:
                        raise
                else:
                    metadata = github(endpoint)
                branch = verify_repository(metadata, target, args.year)
            publish_history(directory, url, branch, base, head)
        print(f"Archive ready: https://github.com/{target}")
        return 0
    except ArchiveError as error:
        print(f"Archive stopped: {error}", file=sys.stderr)
    except (OSError, ValueError, AttributeError):
        print("Archive stopped. Check Git, GitHub CLI, and the archive manifest.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
