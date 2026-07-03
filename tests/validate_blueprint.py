"""Lightweight blueprint checks (HA !input tags are not valid standard YAML)."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLUEPRINT = (
    ROOT / "blueprints" / "automation" / "zlatko-lakisic" / "smart_sequential_watering.yaml"
)

REQUIRED_SNIPPETS = (
    "blueprint:",
    "domain: automation",
    "name: Smart sequential watering",
    "zones:",
    "watering_script:",
    "irrigation_start_service:",
    "irrigation_stop_service:",
    "llm_api_url:",
)


def main() -> int:
    if not BLUEPRINT.is_file():
        print(f"Missing blueprint: {BLUEPRINT}", file=sys.stderr)
        return 1

    text = BLUEPRINT.read_text(encoding="utf-8")
    errors: list[str] = []

    for snippet in REQUIRED_SNIPPETS:
        if snippet not in text:
            errors.append(f"blueprint missing expected content: {snippet!r}")

    if not re.search(r"min_version:\s*['\"]20\d{2}\.", text):
        errors.append("blueprint missing homeassistant min_version")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    print(f"OK {BLUEPRINT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
