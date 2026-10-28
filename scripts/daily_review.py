#!/usr/bin/env python3
"""Optionally submit an explicitly automated daily consistency review."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta
from http.client import HTTPException
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler, Request

from daily_green import CONFIG, DEFAULT_START, ZONE, planned_count, unique_json_object
from greenhouse_config import require_automation


REPOSITORY = CONFIG.repository
OWNER = REPOSITORY.split("/", 1)[0] if "/" in REPOSITORY else ""
REVIEWER = CONFIG.reviewer
BOT = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
ROOT = f"/repos/{REPOSITORY}"


class ReviewError(Exception):
    def __init__(self, message, status=None, uncertain=False, rate_limited=False):
        super().__init__(message)
        self.status = status
        self.uncertain = uncertain
        self.rate_limited = rate_limited


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class API:
    def __init__(self, token):
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None, missing_ok=False):
        body = None if payload is None else json.dumps(payload).encode()
        request = Request("https://api.github.com" + path, data=body, method=method, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        # A write may have succeeded even when its response is lost. Retry
        # reads only; callers may confirm uncertain writes with a bounded GET.
        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(request, timeout=10) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except HTTPError as error:
                if missing_ok and error.code == 404:
                    error.close()
                    return None
                headers = error.headers or {}
                limited = (headers.get("Retry-After") is not None
                           or headers.get("X-RateLimit-Remaining") == "0")
                retry = error.code in {500, 502, 503, 504} and not limited
                # Never print response bodies, headers, or authentication values.
                failure = ReviewError(f"GitHub {method} request failed: HTTP {error.code}",
                                      status=error.code, uncertain=method != "GET" and retry,
                                      rate_limited=limited)
                error.close()
            except (URLError, TimeoutError, OSError, HTTPException):
                retry = True
                failure = ReviewError("GitHub request failed: network error", uncertain=method != "GET")
            except ValueError:
                raise ReviewError("GitHub returned invalid JSON", uncertain=method != "GET") from None
            if not retry or attempt == attempts - 1:
                raise failure from None
            time.sleep(attempt + 1)


def report(message, failed=False):
    """Expose optional review failures without masking completed daily commits."""
    print(message, file=sys.stderr if failed else sys.stdout)
    if failed and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{message}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as output:
                output.write(f"### Daily consistency review\n\n{message}\n")
        except OSError:
            print("Could not write the Actions review summary", file=sys.stderr)


def delete_branch(bot, branch, head):
    # Also used when recovering a successful merge with a lost response or
    # failed cleanup. Never delete a branch moved to another commit.
    ref_path = f"{ROOT}/git/ref/heads/{branch}"
    current = bot.request("GET", ref_path, missing_ok=True)
    if current and current["object"]["sha"] == head:
        try:
            bot.request("DELETE", f"{ROOT}/git/refs/heads/{branch}", missing_ok=True)
        except ReviewError as error:
            if not error.uncertain:
                raise
            if bot.request("GET", ref_path, missing_ok=True) is not None:
                raise error from None


def find_pr(bot, branch):
    query = urlencode({"state": "all", "head": f"{OWNER}:{branch}", "base": "main", "per_page": 100})
    existing = bot.request("GET", f"{ROOT}/pulls?{query}")
    if len(existing) > 1:
        raise ReviewError("Multiple PRs found for this date; refusing to duplicate the check")
    return bot.request("GET", f"{ROOT}/pulls/{existing[0]['number']}") if existing else None


def read_reviews(bot, number):
    reviews = bot.request("GET", f"{ROOT}/pulls/{number}/reviews?per_page=100")
    if not isinstance(reviews, list):
        raise ReviewError("Invalid GitHub reviews list; refusing another review")
    if len(reviews) >= 100:
        raise ReviewError("Too many reviews to prove daily idempotency; refusing another review")
    for item in reviews:
        if (not isinstance(item, dict) or not isinstance(item.get("user"), dict)
                or not isinstance(item["user"].get("login"), str) or not item["user"]["login"]
                or not isinstance(item.get("state"), str) or not item["state"]
                or "body" not in item or (item["body"] is not None and not isinstance(item["body"], str))
                or "submitted_at" not in item
                or (item["submitted_at"] is not None and not isinstance(item["submitted_at"], str))
                or not isinstance(item.get("commit_id"), str) or not item["commit_id"]):
            raise ReviewError("Invalid GitHub review metadata; refusing another review")
    return reviews


def content_at(api, path, commit, missing_ok=False):
    file = api.request("GET", f"{ROOT}/contents/{path}?" + urlencode({"ref": commit}), missing_ok=missing_ok)
    if file is None and missing_ok:
        return None
    if file.get("type") != "file" or file.get("encoding") != "base64":
        raise ReviewError("Expected a small committed file")
    raw = base64.b64decode("".join(file["content"].split()), validate=True).decode("utf-8")
    return raw, file["sha"]


def validate_ledger(raw, today):
    ledger = json.loads(raw, object_pairs_hook=unique_json_object)
    if not isinstance(ledger, dict) or set(ledger) != {"timezone", "start_date", "days"}:
        raise ReviewError("Invalid ledger schema")
    if ledger["timezone"] != CONFIG.timezone or ledger["start_date"] != DEFAULT_START.isoformat():
        raise ReviewError("Wrong ledger timezone or start date")
    if not isinstance(ledger["days"], dict) or not ledger["days"]:
        raise ReviewError("Missing completed ledger days")
    expected = DEFAULT_START
    for text, entry in sorted(ledger["days"].items()):
        day = date.fromisoformat(text)
        if text != day.isoformat() or day != expected or day > today:
            raise ReviewError("Invalid or non-contiguous ledger dates")
        if not isinstance(entry, dict) or set(entry) != {"commits", "planned"}:
            raise ReviewError("Invalid daily ledger entry")
        count, planned = entry["commits"], entry["planned"]
        if type(count) is not int or type(planned) is not int or count != planned or planned != planned_count(day):
            raise ReviewError("Ledger daily counts are incomplete or inconsistent")
        expected += timedelta(days=1)
    if expected != today + timedelta(days=1):
        raise ReviewError("Today's ledger must be complete before reviewing")
    return ledger["days"][today.isoformat()]


def validate_pr(pr, branch, title):
    if (pr["user"]["login"] != BOT or pr["title"] != title
            or pr["base"]["ref"] != "main" or pr["base"]["repo"]["full_name"] != REPOSITORY
            or pr["head"]["ref"] != branch or pr["head"]["repo"]["full_name"] != REPOSITORY
            or pr["head"]["repo"]["owner"]["login"] != OWNER):
        raise ReviewError("PR author, repository, branch, or title does not match this check")


def matching_review(review, marker, commit=None):
    return (isinstance(review, dict) and isinstance(review.get("user"), dict)
            and review["user"].get("login") == REVIEWER and review.get("state") == "COMMENTED"
            and bool(review.get("submitted_at")) and isinstance(review.get("body"), str)
            and marker in review["body"]
            and (commit is None or review.get("commit_id") == commit))


def run():
    if not CONFIG.review_enabled:
        report("Optional review is disabled; no GitHub requests were made.")
        return 0
    require_automation(CONFIG)
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ReviewError("This script only runs in its configured repository")
    token = os.environ.get("REVIEW_TOKEN", "")
    if not token:
        report("Optional review skipped: configure the GREENHOUSE_REVIEW_TOKEN repository secret to enable it.")
        return 0
    bot_token = os.environ.get("GH_TOKEN", "")
    if not bot_token or token == bot_token:
        raise ReviewError("A separate repository bot token and personal review token are required")
    bot, reviewer = API(bot_token), API(token)
    identity = reviewer.request("GET", "/user")
    if identity.get("login") != REVIEWER or identity.get("type") != "User":
        raise ReviewError("The review token must belong to the configured individual reviewer")
    today = datetime.now(ZONE).date()
    text = today.isoformat()
    branch = f"daily-review-{text}"
    path = f"data/reviews/{text}.md"
    title = f"Automated daily consistency check ({text})"
    marker = f"<!-- daily-green-review:{text} -->"
    pr = find_pr(bot, branch)
    if pr:
        validate_pr(pr, branch, title)
        if pr.get("merged"):
            delete_branch(bot, branch, pr["head"]["sha"])
            report(f"Optional review already completed for {text}; no duplicate PR or review.")
            return 0
        if pr.get("state") != "open":
            raise ReviewError("Today's PR is closed without merge; refusing to create a duplicate")
    main = bot.request("GET", f"{ROOT}/git/ref/heads/main")["object"]["sha"]
    raw, ledger_sha = content_at(bot, "data/activity.json", main)
    entry = validate_ledger(raw, today)
    snapshot = (f"# Automated daily consistency check\n\nDate: {text}\nTimezone: {CONFIG.timezone}\n"
                f"Planned daily commits: {entry['planned']}\nRecorded daily commits: {entry['commits']}\n"
                f"Ledger blob SHA: {ledger_sha}\n\nThis is an automated consistency check, not a human code review.\n")
    if not pr:
        # A merged PR's deleted head branch may disappear from head-filtered
        # search. Its main-branch snapshot still prevents a second daily PR.
        completed = content_at(bot, path, main, missing_ok=True)
        if completed is not None:
            if completed[0] != snapshot:
                raise ReviewError("Today's main snapshot does not match the committed ledger")
            report(f"Optional daily snapshot already exists for {text}; no duplicate PR or review.")
            return 0
    ref_path = f"{ROOT}/git/ref/heads/{branch}"
    ref = bot.request("GET", ref_path, missing_ok=True)
    if not ref:
        if pr:
            raise ReviewError("The existing PR branch is missing")
        base = bot.request("GET", f"{ROOT}/git/commits/{main}")
        tree = bot.request("POST", f"{ROOT}/git/trees", {"base_tree": base["tree"]["sha"], "tree": [
            {"path": path, "mode": "100644", "type": "blob", "content": snapshot}
        ]})
        author = {"name": BOT, "email": BOT_EMAIL}
        commit = bot.request("POST", f"{ROOT}/git/commits", {
            "message": title, "tree": tree["sha"], "parents": [main], "author": author, "committer": author,
        })
        head = commit["sha"]
        try:
            created_ref = bot.request("POST", f"{ROOT}/git/refs", {"ref": f"refs/heads/{branch}", "sha": head})
            if (not isinstance(created_ref, dict) or created_ref.get("ref") != f"refs/heads/{branch}"
                    or not isinstance(created_ref.get("object"), dict)
                    or created_ref["object"].get("sha") != head):
                raise ReviewError("GitHub returned invalid branch creation metadata", uncertain=True)
        except ReviewError as error:
            if not error.uncertain:
                raise
            confirmed = bot.request("GET", ref_path, missing_ok=True)
            if (not isinstance(confirmed, dict) or not isinstance(confirmed.get("object"), dict)
                    or confirmed["object"].get("sha") != head):
                raise error from None
    else:
        head = ref["object"]["sha"]
    if not pr:
        try:
            created = bot.request("POST", f"{ROOT}/pulls", {
                "title": title, "head": branch, "base": "main",
                "body": "Automated consistency check of the completed daily ledger. This is not a human code review.",
            })
            if not isinstance(created, dict) or type(created.get("number")) is not int or created["number"] <= 0:
                raise ReviewError("GitHub returned invalid PR creation metadata", uncertain=True)
        except ReviewError as error:
            if not error.uncertain:
                raise
            pr = find_pr(bot, branch)
            if pr is None:
                raise error from None
        else:
            pr = bot.request("GET", f"{ROOT}/pulls/{created['number']}")
    validate_pr(pr, branch, title)
    if pr.get("state") != "open" or pr.get("draft") or pr["head"]["sha"] != head or pr.get("commits") != 1:
        raise ReviewError("The PR is not the expected open, single-commit snapshot")
    number = pr["number"]
    files = bot.request("GET", f"{ROOT}/pulls/{number}/files?per_page=100")
    if len(files) != 1 or files[0]["filename"] != path or files[0].get("status") != "added":
        raise ReviewError("The PR must add only today's consistency snapshot")
    committed_snapshot, _ = content_at(bot, path, head)
    if committed_snapshot != snapshot:
        raise ReviewError("The PR snapshot does not match today's committed ledger")
    reviews = read_reviews(bot, number)
    daily_reviews = [item for item in reviews if matching_review(item, marker)]
    if daily_reviews and not any(matching_review(item, marker, head) for item in daily_reviews):
        raise ReviewError("Today's review refers to another head; refusing a duplicate review")
    if not daily_reviews:
        if datetime.now(ZONE).date() != today:
            raise ReviewError("Configured local date changed during the check; rerun before submitting a review")
        try:
            review = reviewer.request("POST", f"{ROOT}/pulls/{number}/reviews", {
                "event": "COMMENT", "commit_id": head,
                "body": (f"{marker}\nAutomated consistency check / 自动一致性检查（非人工审核）。\n"
                         f"Verified date {text}, {entry['commits']}/{entry['planned']} recorded commits, "
                         f"ledger blob `{ledger_sha}`, and the single expected snapshot file."),
            })
            if not matching_review(review, marker, head):
                raise ReviewError("The expected personal COMMENTED review was not submitted", uncertain=True)
        except ReviewError as error:
            if not error.uncertain:
                raise
            if not any(matching_review(item, marker, head) for item in read_reviews(bot, number)):
                raise error from None
    for attempt in range(2):
        try:
            merged = bot.request("PUT", f"{ROOT}/pulls/{number}/merge", {"sha": head, "merge_method": "merge"})
            if not isinstance(merged, dict) or type(merged.get("merged")) is not bool:
                raise ReviewError("GitHub returned invalid merge metadata", uncertain=True)
            break
        except ReviewError as error:
            if error.uncertain:
                confirmed = bot.request("GET", f"{ROOT}/pulls/{number}")
                validate_pr(confirmed, branch, title)
                if (confirmed.get("merged") is not True or confirmed.get("state") != "closed"
                        or confirmed["head"]["sha"] != head or confirmed.get("commits") != 1):
                    raise error from None
                merged = {"merged": True}
                break
            if attempt or error.status != 405 or error.rate_limited:
                raise
            time.sleep(1)  # GitHub may still be calculating a new PR's mergeability.
    if not merged.get("merged"):
        raise ReviewError("The reviewed PR was not merged")
    delete_branch(bot, branch, head)
    report(f"Optional automated review completed: https://github.com/{REPOSITORY}/pull/{number}")
    return 0


def main():
    try:
        return run()
    except ReviewError as error:
        report(f"Optional review failed: {error}", failed=True)
        return 1
    except (KeyError, TypeError, ValueError, AttributeError):
        report("Optional review failed: invalid GitHub or ledger metadata", failed=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
