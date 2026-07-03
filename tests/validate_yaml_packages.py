"""Parse Agentic Watering package YAML files (standard YAML, no HA tags)."""

from __future__ import annotations

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "agentic_watering" / "packages"

REQUIRED_TOP_LEVEL_KEYS = {
    "rest_command_ai_watering.yaml": {"rest_command"},
    "smart_sequential_watering_script.yaml": {"script"},
}


def main() -> int:
    if not PACKAGE_DIR.is_dir():
        print(f"Missing package directory: {PACKAGE_DIR}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in sorted(PACKAGE_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{path.name}: YAML parse error: {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(f"{path.name}: expected mapping at document root")
            continue

        expected = REQUIRED_TOP_LEVEL_KEYS.get(path.name)
        if expected and not expected.intersection(data.keys()):
            errors.append(f"{path.name}: missing required keys {sorted(expected)}")

        print(f"OK {path.name}")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
