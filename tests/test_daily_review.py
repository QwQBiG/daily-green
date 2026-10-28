"""Exercise recovery and duplicate prevention without contacting GitHub."""

import base64
import copy
from datetime import date, datetime, timedelta
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_review as review


def http_error(status, headers=None):
    return HTTPError("https://api.github.com/test", status, "private response",
                     headers or {}, io.BytesIO(b"secret response body"))


def response(value):
    result = MagicMock()
    result.__enter__.return_value.read.return_value = json.dumps(value).encode()
    return result


class TransportTests(unittest.TestCase):
    def request(self, effects, method="GET"):
        api = review.API("test-token-never-log")
        api.opener.open = MagicMock(side_effect=effects)
        return api

    def test_get_recovers_with_bounded_backoff(self):
        api = self.request([http_error(500), http_error(503), response({"ok": True})])
        with patch.object(review.time, "sleep") as sleep:
            self.assertEqual(api.request("GET", "/test"), {"ok": True})
        self.assertEqual(api.opener.open.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])

    def test_network_get_retries_but_stops_after_three_attempts(self):
        for error in (URLError("private network detail"), TimeoutError(), OSError()):
            with self.subTest(error=type(error).__name__):
                api = self.request([error, error, error])
                with patch.object(review.time, "sleep") as sleep:
                    with self.assertRaisesRegex(review.ReviewError, "network error"):
                        api.request("GET", "/test")
                self.assertEqual(api.opener.open.call_count, 3)
                self.assertEqual(sleep.call_count, 2)

    def test_transient_http_errors_have_the_same_three_attempt_cap(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                api = self.request([http_error(status) for _ in range(3)])
                with patch.object(review.time, "sleep") as sleep:
                    with self.assertRaisesRegex(review.ReviewError, f"HTTP {status}"):
                        api.request("GET", "/test")
                self.assertEqual(api.opener.open.call_count, 3)
                self.assertEqual(sleep.call_count, 2)

    def test_truncated_response_retries_reads_but_not_writes(self):
        for method in ("GET", "POST"):
            with self.subTest(method=method):
                truncated = response(None)
                truncated.__enter__.return_value.read.side_effect = IncompleteRead(b"private partial body", 12)
                api = self.request([truncated, response({"ok": True})])
                with patch.object(review.time, "sleep") as sleep:
                    if method == "GET":
                        self.assertEqual(api.request(method, "/test"), {"ok": True})
                        self.assertEqual(api.opener.open.call_count, 2)
                        sleep.assert_called_once_with(1)
                    else:
                        with self.assertRaisesRegex(review.ReviewError, "network error"):
                            api.request(method, "/test")
                        self.assertEqual(api.opener.open.call_count, 1)
                        sleep.assert_not_called()

    def test_nontransient_or_rate_limited_http_errors_are_not_retried(self):
        cases = [(401, {}), (403, {}), (429, {}),
                 (503, {"Retry-After": "60"}),
                 (500, {"X-RateLimit-Remaining": "0"})]
        for status, headers in cases:
            with self.subTest(status=status, headers=headers):
                api = self.request([http_error(status, headers)])
                with patch.object(review.time, "sleep") as sleep:
                    with self.assertRaisesRegex(review.ReviewError, f"HTTP {status}"):
                        api.request("GET", "/test")
                self.assertEqual(api.opener.open.call_count, 1)
                sleep.assert_not_called()

    def test_mutating_requests_never_retry_a_lost_response(self):
        for method in ("POST", "PUT", "DELETE"):
            for error in (URLError("response lost"), http_error(502)):
                with self.subTest(method=method, error=type(error).__name__):
                    api = self.request([error])
                    with patch.object(review.time, "sleep") as sleep:
                        with self.assertRaises(review.ReviewError) as caught:
                            api.request(method, "/test", {"secret": "payload"})
                    self.assertTrue(caught.exception.uncertain)
                    self.assertEqual(api.opener.open.call_count, 1)
                    sleep.assert_not_called()

    def test_auth_and_rate_limit_write_errors_are_not_uncertain(self):
        for status, headers in [(401, {}), (403, {}), (429, {}),
                                (503, {"Retry-After": "60"}),
                                (500, {"X-RateLimit-Remaining": "0"}),
                                (405, {"Retry-After": "60"})]:
            with self.subTest(status=status, headers=headers):
                api = self.request([http_error(status, headers)])
                with patch.object(review.time, "sleep") as sleep:
                    with self.assertRaises(review.ReviewError) as caught:
                        api.request("POST", "/test", {})
                    self.assertFalse(caught.exception.uncertain)
                    self.assertEqual(caught.exception.rate_limited, bool(headers))
                self.assertEqual(api.opener.open.call_count, 1)
                sleep.assert_not_called()

    def test_invalid_json_only_marks_writes_uncertain(self):
        for method in ("GET", "POST", "PUT", "DELETE"):
            with self.subTest(method=method):
                bad = response(None)
                bad.__enter__.return_value.read.return_value = b"not JSON"
                api = self.request([bad])
                with self.assertRaises(review.ReviewError) as caught:
                    api.request(method, "/test")
                self.assertEqual(caught.exception.uncertain, method != "GET")
                self.assertEqual(api.opener.open.call_count, 1)

    def test_missing_resource_and_invalid_json_do_not_retry(self):
        api = self.request([http_error(404)])
        self.assertIsNone(api.request("GET", "/test", missing_ok=True))
        bad = response(None)
        bad.__enter__.return_value.read.return_value = b"test-token-never-log"
        api = self.request([bad])
        with patch.object(review.time, "sleep") as sleep:
            with self.assertRaisesRegex(review.ReviewError, "invalid JSON"):
                api.request("GET", "/test")
        sleep.assert_not_called()


TEST_DAY = date(2000, 1, 1)


class FakeGitHub:
    """Small stateful fixture: only expected configured endpoints exist."""

    day = TEST_DAY
    text = day.isoformat()
    branch = f"daily-review-{text}"
    path = f"data/reviews/{text}.md"
    title = f"Automated daily consistency check ({text})"
    marker = f"<!-- daily-green-review:{text} -->"

    def __init__(self):
        count = review.planned_count(self.day)
        self.ledger = json.dumps({"timezone": review.CONFIG.timezone, "start_date": self.text,
                                  "days": {self.text: {"commits": count, "planned": count}}})
        self.snapshot = (f"# Automated daily consistency check\n\nDate: {self.text}\nTimezone: {review.CONFIG.timezone}\n"
                         f"Planned daily commits: {count}\nRecorded daily commits: {count}\n"
                         "Ledger blob SHA: ledger-sha\n\nThis is an automated consistency check, not a human code review.\n")
        self.pr = None
        self.head = None
        self.completed_snapshot = False
        self.reviews = []
        self.calls = []
        self.extra_file = False

    def factory(self, token):
        api = MagicMock()
        role = "reviewer" if token == "personal-test-token" else "bot"
        api.request.side_effect = lambda *args, **kwargs: self.request(role, *args, **kwargs)
        return api

    def make_pr(self, merged=False):
        return {"number": 7, "user": {"login": review.BOT}, "title": self.title,
                "base": {"ref": "main", "repo": {"full_name": review.REPOSITORY}},
                "head": {"ref": self.branch, "sha": "head-sha", "repo": {
                    "full_name": review.REPOSITORY, "owner": {"login": review.OWNER}}},
                "state": "closed" if merged else "open", "merged": merged,
                "draft": False, "commits": 1}

    @staticmethod
    def file(raw, sha):
        return {"type": "file", "encoding": "base64", "sha": sha,
                "content": base64.b64encode(raw.encode()).decode()}

    def request(self, role, method, path, payload=None, missing_ok=False):
        self.calls.append((role, method, path, copy.deepcopy(payload)))
        route = path.split("?", 1)[0]
        root = review.ROOT
        if route == "/user":
            return {"login": review.REVIEWER, "type": "User"}
        if method == "GET" and route == root + "/pulls":
            return [{"number": 7}] if self.pr else []
        if method == "GET" and route == root + "/pulls/7":
            return copy.deepcopy(self.pr)
        if route == root + "/git/ref/heads/main":
            return {"object": {"sha": "main-sha"}}
        if route == root + "/git/commits/main-sha":
            return {"tree": {"sha": "base-tree"}}
        if route == root + "/contents/data/activity.json":
            return self.file(self.ledger, "ledger-sha")
        if route == root + "/contents/" + self.path:
            if "ref=head-sha" in path or self.completed_snapshot:
                return self.file(self.snapshot, "snapshot-sha")
            self.assert_missing(missing_ok)
            return None
        if route == root + "/git/ref/heads/" + self.branch:
            return {"object": {"sha": self.head}} if self.head else None
        if method == "POST" and route == root + "/git/trees":
            if payload["tree"][0]["content"] != self.snapshot:
                raise AssertionError("Unexpected snapshot")
            return {"sha": "new-tree"}
        if method == "POST" and route == root + "/git/commits":
            return {"sha": "head-sha"}
        if method == "POST" and route == root + "/git/refs":
            self.head = payload["sha"]
            return {"ref": payload["ref"], "object": {"sha": self.head}}
        if method == "POST" and route == root + "/pulls":
            self.pr = self.make_pr()
            return {"number": 7}
        if method == "GET" and route == root + "/pulls/7/files":
            files = [{"filename": self.path, "status": "added"}]
            return files + ([{"filename": "unexpected.py", "status": "modified"}] if self.extra_file else [])
        if route == root + "/pulls/7/reviews":
            if method == "GET":
                return copy.deepcopy(self.reviews)
            if role != "reviewer" or payload["event"] != "COMMENT":
                raise AssertionError("Unexpected review actor or event")
            item = {"user": {"login": review.REVIEWER}, "state": "COMMENTED",
                    "submitted_at": "2000-01-01T02:17:00Z", "body": payload["body"],
                    "commit_id": payload["commit_id"]}
            self.reviews.append(item)
            return item
        if method == "PUT" and route == root + "/pulls/7/merge":
            if payload != {"sha": "head-sha", "merge_method": "merge"}:
                raise AssertionError("Merge must pin the reviewed head")
            self.pr.update(merged=True, state="closed")
            self.completed_snapshot = True
            return {"merged": True}
        if method == "DELETE" and route == root + "/git/refs/heads/" + self.branch:
            self.head = None
            return None
        raise AssertionError(f"Unexpected fixture request: {role} {method} {path}")

    @staticmethod
    def assert_missing(missing_ok):
        if not missing_ok:
            raise AssertionError("Unexpected mandatory missing file")

    def writes(self):
        return [call for call in self.calls if call[1] != "GET"]


class RunTests(unittest.TestCase):
    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def setUp(self):
        self.config = SimpleNamespace(
            repository="sample-user/sample-garden", reviewer="sample-user",
            review_enabled=True, timezone="UTC", start_date=TEST_DAY,
            configured=True, zone=ZoneInfo("UTC"), author_name="sample-user",
            author_email="1000+sample-user@users.noreply.github.com",
        )
        for name, value in {"CONFIG": self.config, "REPOSITORY": self.config.repository,
                            "OWNER": "sample-user", "REVIEWER": "sample-user",
                            "ROOT": "/repos/" + self.config.repository,
                            "DEFAULT_START": TEST_DAY, "ZONE": self.config.zone}.items():
            self.start_patch(patch.object(review, name, value))
        # Configuration validation has its own tests; these tests exercise review safety.
        self.validate = self.start_patch(patch.object(review, "require_automation"))
        self.github = FakeGitHub()
        self.start_patch(patch.dict(os.environ, {
            "GITHUB_REPOSITORY": review.REPOSITORY, "GH_TOKEN": "bot-test-token",
            "REVIEW_TOKEN": "personal-test-token",
        }, clear=True))
        self.start_patch(patch.object(review, "API", side_effect=self.github.factory))
        self.clock = self.start_patch(patch.object(review, "datetime"))
        self.clock.now.return_value = datetime.combine(self.github.day, datetime.min.time(), review.ZONE)
        self.start_patch(patch("sys.stdout", new=io.StringIO()))

    def test_new_review_merges_then_rerun_does_not_duplicate(self):
        self.assertEqual(review.run(), 0)
        self.assertEqual(len(self.github.reviews), 1)
        self.assertTrue(self.github.pr["merged"])
        self.assertIsNone(self.github.head)
        first_writes = len(self.github.writes())
        self.assertEqual(review.run(), 0)
        self.assertEqual(len(self.github.writes()), first_writes)

    def test_lost_review_response_is_reconciled_in_same_run(self):
        original = self.github.request
        def lose_review_response(role, method, path, *args, **kwargs):
            result = original(role, method, path, *args, **kwargs)
            if role == "reviewer" and method == "POST":
                raise review.ReviewError("GitHub request failed: network error", uncertain=True)
            return result
        with patch.object(self.github, "request", side_effect=lose_review_response):
            self.assertEqual(review.run(), 0)
        self.assertEqual(len(self.github.reviews), 1)
        self.assertTrue(self.github.pr["merged"])
        self.assertIsNone(self.github.head)
        self.assertEqual(review.run(), 0)
        self.assertEqual(sum(role == "reviewer" and method == "POST"
                             for role, method, _, _ in self.github.calls), 1)
        self.assertTrue(self.github.pr["merged"])

    def test_malformed_reviews_list_stops_before_personal_review_or_merge(self):
        for malformed in ({}, None, "", [None], ["review"], [{}], [{"user": None}]):
            with self.subTest(response=malformed):
                github = FakeGitHub()
                original = github.request
                def malformed_reviews(role, method, path, *args, **kwargs):
                    result = original(role, method, path, *args, **kwargs)
                    if method == "GET" and path.split("?", 1)[0] == review.ROOT + "/pulls/7/reviews":
                        return malformed
                    return result
                with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=malformed_reviews):
                    with self.assertRaisesRegex(review.ReviewError, "Invalid GitHub review"):
                        review.run()
                self.assertFalse(any(call[0] == "reviewer" and call[1] == "POST" for call in github.calls))
                self.assertFalse(any(call[1] in ("PUT", "DELETE") for call in github.calls))

    def test_valid_pending_review_with_empty_body_does_not_block_daily_review(self):
        self.github.reviews.append({"user": {"login": review.REVIEWER}, "state": "PENDING",
                                    "body": None, "submitted_at": None, "commit_id": "head-sha"})
        self.assertEqual(review.run(), 0)
        self.assertEqual(sum(call[0] == "reviewer" and call[1] == "POST" for call in self.github.calls), 1)
        self.assertTrue(self.github.pr["merged"])
        self.assertIsNone(self.github.head)

    def test_lost_merge_response_recovers_cleanup_without_second_review(self):
        original = self.github.request
        def lose_merge_response(role, method, path, *args, **kwargs):
            result = original(role, method, path, *args, **kwargs)
            if method == "PUT":
                raise review.ReviewError("GitHub request failed: network error", uncertain=True)
            return result
        with patch.object(self.github, "request", side_effect=lose_merge_response):
            self.assertEqual(review.run(), 0)
        self.assertTrue(self.github.pr["merged"])
        self.assertIsNone(self.github.head)
        self.assertEqual(review.run(), 0)
        self.assertIsNone(self.github.head)
        self.assertEqual(len(self.github.reviews), 1)
        self.assertEqual(sum(call[1] == "PUT" for call in self.github.calls), 1)

    def test_lost_ref_pr_and_delete_responses_recover_without_repeating_writes(self):
        root = review.ROOT
        for method, route in [("POST", root + "/git/refs"), ("POST", root + "/pulls"),
                              ("DELETE", root + "/git/refs/heads/" + FakeGitHub.branch)]:
            with self.subTest(method=method, route=route):
                github = FakeGitHub()
                original = github.request
                def lose_response(role, actual_method, path, *args, **kwargs):
                    result = original(role, actual_method, path, *args, **kwargs)
                    if actual_method == method and path.split("?", 1)[0] == route:
                        raise review.ReviewError("GitHub request failed: network error", uncertain=True)
                    return result
                with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=lose_response):
                    self.assertEqual(review.run(), 0)
                self.assertTrue(github.pr["merged"])
                self.assertIsNone(github.head)
                self.assertEqual(len(github.reviews), 1)
                self.assertEqual(sum(call[1] == method and call[2].split("?", 1)[0] == route
                                     for call in github.calls), 1)

    def test_malformed_successful_mutation_responses_are_confirmed_by_reads(self):
        root = review.ROOT
        routes = [("POST", root + "/git/refs"), ("POST", root + "/pulls"),
                  ("POST", root + "/pulls/7/reviews"), ("PUT", root + "/pulls/7/merge")]
        for method, route in routes:
            for malformed in (None, {}, [], {"wrong": "metadata"}):
                with self.subTest(method=method, route=route, response=malformed):
                    github = FakeGitHub()
                    original = github.request
                    def malformed_response(role, actual_method, path, *args, **kwargs):
                        result = original(role, actual_method, path, *args, **kwargs)
                        return malformed if actual_method == method and path.split("?", 1)[0] == route else result
                    with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=malformed_response):
                        self.assertEqual(review.run(), 0)
                    self.assertTrue(github.pr["merged"])
                    self.assertIsNone(github.head)
                    self.assertEqual(len(github.reviews), 1)
                    self.assertEqual(sum(call[1] == method and call[2].split("?", 1)[0] == route
                                         for call in github.calls), 1)

    def test_uncertain_write_without_confirmation_stops_without_retry(self):
        root = review.ROOT
        for method, route in [("POST", root + "/git/refs"), ("POST", root + "/pulls"),
                              ("POST", root + "/pulls/7/reviews"), ("PUT", root + "/pulls/7/merge"),
                              ("DELETE", root + "/git/refs/heads/" + FakeGitHub.branch)]:
            with self.subTest(method=method, route=route):
                github = FakeGitHub()
                original = github.request
                def fail_before_write(role, actual_method, path, payload=None, **kwargs):
                    if actual_method == method and path.split("?", 1)[0] == route:
                        github.calls.append((role, actual_method, path, copy.deepcopy(payload)))
                        raise review.ReviewError("Unconfirmed write", uncertain=True)
                    return original(role, actual_method, path, payload, **kwargs)
                with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=fail_before_write):
                    with self.assertRaisesRegex(review.ReviewError, "Unconfirmed write"):
                        review.run()
                self.assertEqual(sum(call[1] == method and call[2].split("?", 1)[0] == route
                                     for call in github.calls), 1)
                if method != "DELETE":
                    self.assertFalse(any(call[1] == "DELETE" for call in github.calls))

    def test_reconciliation_preserves_pr_file_and_review_head_guards(self):
        for mismatch in ("extra_file", "review_head", "merge_head", "ref_head"):
            with self.subTest(mismatch=mismatch):
                github = FakeGitHub()
                original = github.request
                def lose_and_change(role, method, path, *args, **kwargs):
                    result = original(role, method, path, *args, **kwargs)
                    route = path.split("?", 1)[0]
                    if mismatch == "extra_file" and method == "POST" and route == review.ROOT + "/pulls":
                        github.extra_file = True
                    elif mismatch == "review_head" and role == "reviewer" and method == "POST":
                        github.reviews[0]["commit_id"] = "different-sha"
                    elif mismatch == "merge_head" and method == "PUT":
                        github.pr["head"]["sha"] = "different-sha"
                    elif mismatch == "ref_head" and method == "POST" and route == review.ROOT + "/git/refs":
                        github.head = "different-sha"
                    else:
                        return result
                    raise review.ReviewError("Uncertain mutation", uncertain=True)
                with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=lose_and_change):
                    with self.assertRaises(review.ReviewError):
                        review.run()
                self.assertFalse(any(call[1] == "DELETE" for call in github.calls))
                if mismatch in ("extra_file", "ref_head"):
                    self.assertFalse(github.reviews)
                if mismatch != "merge_head":
                    self.assertFalse(any(call[1] == "PUT" for call in github.calls))

    def test_uncertain_review_requires_matching_personal_submitted_marker(self):
        for field, value in [("user", {"login": review.BOT}), ("state", "PENDING"),
                             ("submitted_at", None), ("body", "Unrelated comment"),
                             ("commit_id", "another-sha")]:
            with self.subTest(field=field):
                github = FakeGitHub()
                original = github.request
                def lose_review_response(role, method, path, *args, **kwargs):
                    result = original(role, method, path, *args, **kwargs)
                    if role == "reviewer" and method == "POST":
                        github.reviews[0][field] = value
                        raise review.ReviewError("Unconfirmed review", uncertain=True)
                    return result
                with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=lose_review_response):
                    with self.assertRaisesRegex(review.ReviewError, "Unconfirmed review"):
                        review.run()
                self.assertEqual(sum(call[0] == "reviewer" and call[1] == "POST" for call in github.calls), 1)
                self.assertFalse(any(call[1] in ("PUT", "DELETE") for call in github.calls))

    def test_auth_and_rate_limit_failures_do_not_trigger_confirmation_reads(self):
        for role, method, route in [("reviewer", "POST", review.ROOT + "/pulls/7/reviews"),
                                    ("bot", "PUT", review.ROOT + "/pulls/7/merge"),
                                    ("bot", "POST", review.ROOT + "/pulls")]:
            for status in (401, 403, 429, 503, 405):
                with self.subTest(role=role, method=method, route=route, status=status):
                    github = FakeGitHub()
                    original = github.request
                    def unauthorized(actual_role, actual_method, path, payload=None, **kwargs):
                        if actual_role == role and actual_method == method and path.split("?", 1)[0] == route:
                            github.calls.append((actual_role, actual_method, path, copy.deepcopy(payload)))
                            raise review.ReviewError("Authorization or rate limit failure", status=status, rate_limited=True)
                        return original(actual_role, actual_method, path, payload, **kwargs)
                    with patch.object(review, "API", side_effect=github.factory), patch.object(github, "request", side_effect=unauthorized):
                        with self.assertRaises(review.ReviewError):
                            review.run()
                    self.assertEqual(github.calls[-1][1:3], (method, route))

    def test_merged_pr_cleans_only_a_matching_branch(self):
        for head, deletes in [("head-sha", 1), ("different-sha", 0), (None, 0)]:
            with self.subTest(head=head):
                self.github.pr = self.github.make_pr(merged=True)
                self.github.head = head
                self.github.calls.clear()
                self.assertEqual(review.run(), 0)
                writes = self.github.writes()
                self.assertEqual([call[1] for call in writes], ["DELETE"] * deletes)
                self.assertFalse(self.github.reviews)

    def test_completed_snapshot_fallback_never_fetches_tree_or_writes(self):
        self.github.completed_snapshot = True
        self.assertEqual(review.run(), 0)
        self.assertFalse(self.github.writes())
        self.assertFalse(any("/git/commits/" in call[2] for call in self.github.calls))

    def test_existing_open_pr_reuses_branch_without_fetching_tree(self):
        self.github.pr = self.github.make_pr()
        self.github.head = "head-sha"
        self.assertEqual(review.run(), 0)
        self.assertFalse(any("/git/commits/" in call[2] for call in self.github.calls))
        self.assertEqual([call[1] for call in self.github.writes()], ["POST", "PUT", "DELETE"])

    def test_midnight_prevents_new_personal_review_and_merge(self):
        midnight = datetime.combine(self.github.day, datetime.min.time(), review.ZONE)
        self.clock.now.side_effect = [midnight, midnight + timedelta(days=1)]
        with self.assertRaises(review.ReviewError):
            review.run()
        self.assertFalse(any(call[0] == "reviewer" and call[1] == "POST" for call in self.github.calls))
        self.assertFalse(any(call[1] in ("PUT", "DELETE") for call in self.github.calls))

    def test_extra_file_is_rejected_before_personal_review(self):
        self.github.extra_file = True
        with self.assertRaisesRegex(review.ReviewError, "only today's"):
            review.run()
        self.assertFalse(self.github.reviews)
        self.assertFalse(any(call[1] in ("PUT", "DELETE") for call in self.github.calls))

    def test_disabled_review_skips_validation_secrets_and_network(self):
        self.config.review_enabled = False
        os.environ.clear()
        self.assertEqual(review.run(), 0)
        self.validate.assert_not_called()
        self.assertFalse(self.github.calls)

    def test_repository_mismatch_stops_before_api_calls(self):
        os.environ["GITHUB_REPOSITORY"] = "other-user/another-garden"
        with self.assertRaisesRegex(review.ReviewError, "configured repository"):
            review.run()
        self.assertFalse(self.github.calls)

    def test_organization_repository_has_a_separate_individual_reviewer(self):
        self.config.repository = "sample-org/sample-garden"
        os.environ["GITHUB_REPOSITORY"] = self.config.repository
        with patch.object(review, "REPOSITORY", self.config.repository), \
                patch.object(review, "OWNER", "sample-org"), \
                patch.object(review, "ROOT", "/repos/" + self.config.repository):
            self.assertEqual(review.run(), 0)
        self.assertEqual(self.github.reviews[0]["user"]["login"], "sample-user")
        self.assertEqual(self.github.pr["head"]["repo"]["owner"]["login"], "sample-org")

    def test_wrong_reviewer_identity_stops_before_any_writes(self):
        original = self.github.request
        def wrong_identity(role, method, path, *args, **kwargs):
            if path == "/user":
                return {"login": "someone-else", "type": "User"}
            return original(role, method, path, *args, **kwargs)
        with patch.object(self.github, "request", side_effect=wrong_identity):
            with self.assertRaisesRegex(review.ReviewError, "configured individual reviewer"):
                review.run()
        self.assertFalse(self.github.writes())

    def test_personal_review_at_another_head_is_not_duplicated(self):
        self.github.reviews.append({"user": {"login": review.REVIEWER}, "state": "COMMENTED",
                                    "body": self.github.marker, "submitted_at": "2000-01-01T00:01:00Z",
                                    "commit_id": "old-head"})
        with self.assertRaisesRegex(review.ReviewError, "another head"):
            review.run()
        self.assertFalse(any(call[0] == "reviewer" and call[1] == "POST" for call in self.github.calls))
        self.assertFalse(any(call[1] in ("PUT", "DELETE") for call in self.github.calls))

    def test_missing_personal_token_skips_all_api_calls(self):
        os.environ.pop("REVIEW_TOKEN")
        self.assertEqual(review.run(), 0)
        self.assertFalse(self.github.calls)


class ReportingTests(unittest.TestCase):
    def test_report_appends_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), patch("sys.stdout", new=io.StringIO()) as output:
                review.report("First result")
                review.report("Second result")
            self.assertIn("First result", output.getvalue())
            self.assertIn("First result", summary.read_text())
            self.assertIn("Second result", summary.read_text())

    def test_main_safe_failure_warns_and_does_not_expose_tokens(self):
        api = review.API("test-token-never-log")
        api.opener.open = MagicMock(side_effect=http_error(401))
        def fail_safely():
            api.request("GET", "/test")
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary), "GITHUB_ACTIONS": "true"}), patch.object(review, "run", side_effect=fail_safely), patch("sys.stdout", new=io.StringIO()) as out, patch("sys.stderr", new=io.StringIO()) as err:
                self.assertEqual(review.main(), 1)
            combined = out.getvalue() + err.getvalue() + summary.read_text()
            self.assertIn("HTTP 401", combined)
            self.assertIn("::warning", combined)
            for private in ("test-token-never-log", "secret response body", "private response"):
                self.assertNotIn(private, combined)


if __name__ == "__main__":
    unittest.main()
