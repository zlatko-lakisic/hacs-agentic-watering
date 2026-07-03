"""Ensure HACS brand assets exist."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "custom_components" / "agentic_watering" / "brand"


def main() -> int:
    icon = BRAND_DIR / "icon.png"
    if not icon.is_file():
        print(f"Missing brand icon: {icon}", file=sys.stderr)
        return 1
    if icon.stat().st_size < 1024:
        print(f"Brand icon too small: {icon}", file=sys.stderr)
        return 1
    print(f"OK {icon}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
