#!/usr/bin/env python3
"""Locally bundle the greenhouse's libraries; never run by Actions."""

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def bundle():
    html = (ROOT / "garden/index.html").read_text(encoding="utf-8")
    for name in ("garden-core.js", "plant-art.js", "visitor-art.js"):
        source = (ROOT / "garden" / name).read_text(encoding="utf-8").rstrip()
        if "</script" in source.lower():
            raise ValueError("Library contains a closing script tag")
        block = f'<script data-source="{name}">\n{source}\n</script>'
        external = f'<script src="{name}"></script>'
        pattern = r'<script data-source="' + re.escape(name) + r'">[\s\S]*?</script>'
        if external in html:
            if html.count(external) != 1:
                raise ValueError("Duplicate library source")
            html = html.replace(external, block)
        else:
            html, count = re.subn(pattern, lambda match: block, html)
            if count != 1:
                raise ValueError("Expected one embedded library")
    return html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "garden/index.html")
    args = parser.parse_args()
    html = bundle()
    args.output.write_text(html, encoding="utf-8")
    print(f"Offline greenhouse ready: {args.output}")


if __name__ == "__main__":
    main()
