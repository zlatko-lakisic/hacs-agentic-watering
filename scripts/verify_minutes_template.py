#!/usr/bin/env python3
"""Verify the deployed watering script parses MINUTES answers, via HA's template API.

The MINUTES answer is extracted by Jinja inside
``packages/smart_sequential_watering_script.yaml``. Local Python mirrors of that
logic can drift from Home Assistant's own filter semantics, which is how
emphasised replies ("**MINUTES: 20**") came to be discarded as unreadable while
the unit tests stayed green. This renders the real templates through the running
instance so the result reflects production exactly.

    python scripts/verify_minutes_template.py --ha-url http://192.168.89.25:8123 \
        --token "$HA_TOKEN"
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_YAML = (
    REPO
    / "custom_components"
    / "agentic_watering"
    / "packages"
    / "smart_sequential_watering_script.yaml"
)
TEMPLATE_KEYS = ("llm_minutes_parsed", "llm_minutes")

# (name, reply, expect_parsed, expect_minutes)
CASES = (
    ("plain answer", "Rain is coming.\nMINUTES: 0", True, 0),
    ("bold whole line", "Soil at 21%.\n\n**MINUTES: 20**", True, 20),
    ("bold label", "Rain tomorrow.\n\n**MINUTES:** 12", True, 12),
    ("repeated bold", "**MINUTES: 7**\n\nReassess.\n\n**MINUTES: 7**", True, 7),
    ("heading", "### MINUTES: 5", True, 5),
    ("trailing unit", "MINUTES: 20 minutes.", True, 20),
    ("backticks", "`MINUTES: 9`", True, 9),
    ("over cap clamps", "**MINUTES: 99**", True, 25),
    ("prose only", "I would water for **20 minutes** today.", False, 0),
    ("no answer", "It is hard to say.", False, 0),
)


def collect_templates(node, out=None):
    out = {} if out is None else out
    if isinstance(node, dict):
        for key, value in node.items():
            if key in TEMPLATE_KEYS and isinstance(value, str) and "{%" in value:
                out.setdefault(key, []).append(value)
            collect_templates(value, out)
    elif isinstance(node, list):
        for item in node:
            collect_templates(item, out)
    return out


def render(ha_url: str, token: str, template: str) -> str:
    req = urllib.request.Request(
        f"{ha_url.rstrip('/')}/api/template",
        data=json.dumps({"template": template}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode().strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ha-url", default=os.environ.get("HA_URL", "http://192.168.89.25:8123"))
    ap.add_argument("--token", default=os.environ.get("HA_TOKEN", ""))
    args = ap.parse_args()

    if not args.token:
        print("ERROR: pass --token or set HA_TOKEN", file=sys.stderr)
        return 2

    templates = collect_templates(yaml.safe_load(SCRIPT_YAML.read_text(encoding="utf-8")))
    for key in TEMPLATE_KEYS:
        if not templates.get(key):
            print(f"ERROR: no {key} template found in {SCRIPT_YAML.name}", file=sys.stderr)
            return 2

    failures = 0
    for name, reply, want_parsed, want_minutes in CASES:
        prefix = f"{{% set zone_llm_raw = {json.dumps(reply)} %}}"
        results: dict[str, set[str]] = {}
        try:
            for key in TEMPLATE_KEYS:
                results[key] = {
                    render(args.ha_url, args.token, prefix + body)
                    for body in templates[key]
                }
        except urllib.error.URLError as exc:
            print(f"ERROR: template API call failed: {exc}", file=sys.stderr)
            return 2

        notes = []
        for key in TEMPLATE_KEYS:
            if len(results[key]) != 1:
                notes.append(f"{key} copies disagree: {sorted(results[key])}")

        parsed = next(iter(results["llm_minutes_parsed"])).lower() == "true"
        minutes = int(next(iter(results["llm_minutes"])) or 0)
        if parsed != want_parsed:
            notes.append(f"parsed={parsed} want {want_parsed}")
        if minutes != want_minutes:
            notes.append(f"minutes={minutes} want {want_minutes}")

        if notes:
            failures += 1
            print(f"FAIL {name}: " + "; ".join(notes))
        else:
            print(f"ok   {name}: parsed={parsed} minutes={minutes}")

    print(f"\n{len(CASES) - failures}/{len(CASES)} cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
