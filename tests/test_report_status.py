"""Validate the local Actions summary without Git, credentials, or network."""

from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_green
import report_status as status

BASE = date(2000, 1, 1)


def completed_report(through=None, created=0):
    through = through or BASE + timedelta(days=6)
    history = {}
    day = BASE
    while day <= through:
        history[day] = set(range(1, daily_green.planned_count(day) + 1))
        day += timedelta(days=1)
    report = daily_green.summary(BASE, through, history)
    # The CLI input is JSON, whose object keys are always strings.
    report = json.loads(json.dumps(report))
    report["created_commits"] = created
    return report


class ConfiguredSummaryTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("DEFAULT_START", BASE), ("CONFIG", SimpleNamespace(timezone="UTC"))):
            setting = patch.object(status, name, value)
            setting.start()
            self.addCleanup(setting.stop)


class SummaryTests(ConfiguredSummaryTests):
    def test_local_plant_preview_does_not_write_an_actions_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "summary.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}):
                for day in ("0001-01-01", "2010-03-04", "2030-01-01"):
                    with patch("sys.stdout", new=io.StringIO()) as output:
                        self.assertEqual(status.main(["--plant", day]), 0)
                    self.assertEqual(output.getvalue(), status.render_plant_card(status.report_date(day)))
                    self.assertIn(f"DG-{day.replace('-', '')}-", output.getvalue())
                    self.assertFalse(destination.exists())
                with patch("sys.stderr", new=io.StringIO()) as error:
                    self.assertEqual(status.main(["--plant", "private-value"]), 1)
                self.assertNotIn("private-value", error.getvalue())
                self.assertFalse(destination.exists())

    def test_complete_and_repeat_results_report_repository_counts(self):
        for created in (0, 5):
            with self.subTest(created=created):
                report = completed_report(created=created)
                rendered = status.render_summary(report)
                through = status.report_date(report["through"])
                daily = daily_green.planned_count(through)
                self.assertIn(f"| 当日记录 / 计划 | {daily} / {daily} |", rendered)
                self.assertIn("| 连续完成天数 | 7 |", rendered)
                self.assertIn(f"| 累计标记 commit | {report['planned_commits']} |", rendered)
                self.assertIn(f"| 本次新增 commit | {created} |", rendered)
                self.assertIn("不代表 GitHub 个人主页实际统计", rendered)

    def test_report_uses_the_configured_timezone_label(self):
        with patch.object(status, "CONFIG", SimpleNamespace(timezone="Pacific/Honolulu")):
            self.assertIn("记录截至（Pacific/Honolulu）", status.render_summary(completed_report()))

    def test_schema_and_dates_are_strict(self):
        cases = []
        for key, value in (
            ("extra", 1), ("start", "2000-01-02"), ("through", "1999-12-31"),
            ("through", "2999-01-01"), ("through", "2000-01-08T00:00:00"),
            ("through", 20000108), ("through", "<script>private-value</script>"),
        ):
            report = completed_report()
            report[key] = value
            cases.append(report)
        missing = completed_report()
        del missing["created_commits"]
        cases.extend([missing, [], None])
        for report in cases:
            with self.subTest(report=report):
                with self.assertRaises(ValueError):
                    status.render_summary(report)

    def test_corrupted_counts_and_distribution_are_rejected(self):
        for key in ("days", "planned_commits", "existing_commits", "missing_commits", "created_commits"):
            for value in (True, False, "1", -1, 1.5):
                with self.subTest(key=key, value=value):
                    report = completed_report()
                    report[key] = value
                    with self.assertRaises(ValueError):
                        status.render_summary(report)
        for key in ("days", "planned_commits", "existing_commits"):
            report = completed_report()
            report[key] += 1
            with self.assertRaises(ValueError):
                status.render_summary(report)
        report = completed_report()
        report["created_commits"] = report["existing_commits"] + 1
        with self.assertRaises(ValueError):
            status.render_summary(report)
        for value in ({"2": True}, {"2": 7}, [], None):
            report = completed_report()
            report["daily_distribution"] = value
            with self.assertRaises(ValueError):
                status.render_summary(report)

    def test_incomplete_results_never_claim_completion(self):
        for key, value in (("missing_commits", 1), ("incomplete_days", {"2000-01-08": 1}),
                           ("incomplete_days", []), ("incomplete_days", None)):
            with self.subTest(key=key, value=value):
                report = completed_report()
                report[key] = value
                with self.assertRaises(ValueError):
                    status.render_summary(report)

    def test_cli_prints_and_appends_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "report.json"
            destination = Path(directory) / "summary.md"
            source.write_text(json.dumps(completed_report()), encoding="utf-8")
            destination.write_text("Previous step\n", encoding="utf-8")
            output = io.StringIO()
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}), patch("sys.stdout", output):
                self.assertEqual(status.main([str(source)]), 0)
            self.assertEqual(destination.read_text(encoding="utf-8"), "Previous step\n\n" + output.getvalue())

    def test_cli_errors_do_not_leak_input_or_write_success(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "private-value.json"
            destination = Path(directory) / "summary.md"
            bad_reports = [
                "not JSON private-value", '{"start":"private-value","start":"duplicate"}',
                json.dumps({**completed_report(), "through": "private-value"}),
                json.dumps({**completed_report(), "missing_commits": 1}),
                "[" * 1500 + "]" * 1500,
                "x" * (status.MAX_REPORT_BYTES + 1),
            ]
            for raw in bad_reports:
                with self.subTest(raw=raw[:80]):
                    source.write_text(raw, encoding="utf-8")
                    output, error = io.StringIO(), io.StringIO()
                    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}), \
                            patch("sys.stdout", output), patch("sys.stderr", error):
                        self.assertEqual(status.main([str(source)]), 1)
                    self.assertEqual(output.getvalue(), "")
                    self.assertNotIn("private-value", error.getvalue())
                    self.assertNotIn("Traceback", error.getvalue())
                    self.assertFalse(destination.exists())
            source.unlink()
            with patch("sys.stderr", io.StringIO()) as error:
                self.assertEqual(status.main([str(source)]), 1)
                self.assertNotIn("private-value", error.getvalue())
                self.assertEqual(status.main([]), 1)


class PlantCardTests(ConfiguredSummaryTests):
    def test_repeat_and_history_reports_keep_the_same_dated_card(self):
        through = BASE + timedelta(days=6)
        expected = status.render_plant_card(through)
        for created in (0, 5):
            for elapsed in (0, 10, 365):
                with self.subTest(created=created, elapsed=elapsed):
                    rendered = status.render_summary(
                        completed_report(through, created), today=through + timedelta(days=elapsed),
                    )
                    self.assertTrue(rendered.endswith(expected))
        self.assertIn(f"DG-{through.strftime('%Y%m%d')}-", expected)
        self.assertEqual(status.render_plant_card(through), expected)

    def test_species_and_leaf_meter_are_bounded(self):
        seen = set()
        for offset in range(96):
            day = BASE + timedelta(days=offset)
            rendered = status.render_plant_card(day)
            matches = [species for emoji, species in status.PLANTS if f"{emoji} {species}" in rendered]
            self.assertEqual(len(matches), 1)
            seen.update(matches)
            meter = re.search(r"叶片：(.*) \*\*(\d)/6\*\*", rendered)
            self.assertIsNotNone(meter)
            leaves = daily_green.planned_count(day)
            self.assertEqual(int(meter[2]), leaves)
            self.assertEqual(meter[1].count("🌿"), leaves)
            self.assertEqual(meter[1].count("▫"), 6 - leaves)
            self.assertEqual(len(meter[1]), 6)
            self.assertRegex(rendered, rf"DG-{day.strftime('%Y%m%d')}-[a-f0-9]{{6}}")
        self.assertEqual(len(seen), 6)

    def test_moonlight_variant_is_rare_and_reproducible(self):
        moonlight = []
        for offset in range(366):
            day = BASE + timedelta(days=offset)
            if "月光叶" in status.render_plant_card(day):
                moonlight.append(day)
        self.assertTrue(moonlight)
        self.assertLess(len(moonlight), 32)
        for day in moonlight:
            card = status.render_plant_card(day)
            self.assertIn("特别款", card)
            self.assertEqual(status.render_plant_card(day), card)


if __name__ == "__main__":
    unittest.main()
