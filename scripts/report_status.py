#!/usr/bin/env python3
"""Render a validated daily-green result without reading credentials or GitHub."""

from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

from daily_green import CONFIG, DEFAULT_START, ZONE, planned_count


REPORT_KEYS = {
    "start", "through", "days", "planned_commits", "existing_commits",
    "missing_commits", "daily_distribution", "incomplete_days", "created_commits",
}
MAX_REPORT_BYTES = 64 * 1024
PLANTS = (
    ("🌿", "薄荷"), ("☘️", "三叶草"), ("🌵", "仙人掌"),
    ("🌻", "向日葵"), ("🌱", "铃兰"), ("🍃", "含羞草"),
)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("报告包含重复字段")
        result[key] = value
    return result


def report_date(value):
    if not isinstance(value, str):
        raise ValueError("报告日期无效")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("报告日期无效") from None
    if parsed.isoformat() != value:
        raise ValueError("报告日期无效")
    return parsed


def render_plant_card(day):
    """A decorative calendar seed, independent of run count and wall clock."""
    digest = hashlib.sha256(f"daily-green-garden-v1:{day.isoformat()}".encode("ascii")).digest()
    emoji, species = PLANTS[int.from_bytes(digest[:8], "big") % len(PLANTS)]
    variant = "🌙 月光叶 · 特别款" if digest[8] % 32 == 0 else "晨绿叶 · 常规款"
    leaves = planned_count(day)
    meter = "🌿" * leaves + "▫" * (6 - leaves)
    day_key = day.isoformat().replace("-", "")
    card_id = f"DG-{day_key}-{digest.hex()[:6]}"
    return (
        "\n### 每日一盆\n\n"
        f"**{emoji} {species}** · {variant}\n\n"
        f"叶片：{meter} **{leaves}/6**\n\n"
        f"`{card_id}`\n\n"
        "*按日期固定生成的装饰卡片，同日重跑还是同一盆。*\n"
    )


def render_summary(report, today=None):
    """Only a complete, internally consistent result may claim completion."""
    if not isinstance(report, dict) or set(report) != REPORT_KEYS:
        raise ValueError("报告字段无效")
    start = report_date(report["start"])
    through = report_date(report["through"])
    if today is None:
        today = datetime.now(ZONE).date()
    if start != DEFAULT_START or not start <= through <= today:
        raise ValueError("报告日期范围无效")

    for key in ("days", "planned_commits", "existing_commits", "missing_commits", "created_commits"):
        if type(report[key]) is not int or report[key] < 0:
            raise ValueError("报告计数无效")

    days = (through - start).days + 1
    distribution = Counter(planned_count(start + timedelta(days=offset)) for offset in range(days))
    expected_distribution = {str(count): frequency for count, frequency in distribution.items()}
    supplied_distribution = report["daily_distribution"]
    if not isinstance(supplied_distribution, dict) or any(
        type(value) is not int or value < 1 for value in supplied_distribution.values()
    ) or supplied_distribution != expected_distribution:
        raise ValueError("报告每日分布无效")

    planned = sum(count * frequency for count, frequency in distribution.items())
    if report["days"] != days or report["planned_commits"] != planned:
        raise ValueError("报告天数或计划总数不一致")
    if report["missing_commits"] != 0 or report["incomplete_days"] != {}:
        raise ValueError("记录尚未全部完成")
    if report["existing_commits"] != planned or not 0 <= report["created_commits"] <= planned:
        raise ValueError("报告完成总数不一致")

    daily = planned_count(through)
    return (
        "daily-green 记录状态：已完成。\n\n"
        "| 项目 | 结果 |\n"
        "| --- | --- |\n"
        f"| 记录截至（{CONFIG.timezone}） | {through.isoformat()} |\n"
        f"| 当日记录 / 计划 | {daily} / {daily} |\n"
        f"| 连续完成天数 | {days} |\n"
        f"| 累计标记 commit | {planned} |\n"
        f"| 本次新增 commit | {report['created_commits']} |\n\n"
        "以上为仓库记录，不代表 GitHub 个人主页实际统计的贡献数。\n"
    ) + render_plant_card(through)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "--plant":
        try:
            card = render_plant_card(report_date(args[1]))
        except ValueError:
            print("植物卡日期无效，请使用 YYYY-MM-DD。", file=sys.stderr)
            return 1
        print(card, end="")
        return 0
    if len(args) != 1:
        print("用法：report_status.py <每日运行结果.json> 或 --plant YYYY-MM-DD", file=sys.stderr)
        return 1
    try:
        with Path(args[0]).open("rb") as handle:
            raw = handle.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            raise ValueError("报告过大")
        report = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        summary = render_summary(report)
        destination = os.environ.get("GITHUB_STEP_SUMMARY")
        if destination:
            with Path(destination).open("a", encoding="utf-8") as handle:
                handle.write("\n" + summary)
    except (ValueError, OSError, UnicodeError, TypeError, RecursionError):
        # Inputs and filesystem paths can be untrusted; do not echo their content.
        print("无法生成每日记录摘要：结果缺失、无效或尚未完成。", file=sys.stderr)
        return 1
    print(summary, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
