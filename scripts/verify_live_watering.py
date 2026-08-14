#!/usr/bin/env python3
"""Post-deploy live verification against Home Assistant.

Checks soil moisture bands and optional Reach probe service.
Does not open valves.

Usage:
  python scripts/verify_live_watering.py --ha-url https://ha.example.com --token TOKEN
  python scripts/verify_live_watering.py --dry-print   # print expected entity IDs only
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

SOIL = {
    "sensor.garden_controller_soil_moisture_1": ("Eggplant/zucchini secondary", 48, 60),
    "sensor.garden_controller_soil_moisture_2": ("Flower bed", 40, 68),
    "sensor.garden_controller_soil_moisture_3": ("Peppers", 40, 65),
    "sensor.garden_controller_soil_moisture_4": ("Tomato", 45, 62),
    "sensor.garden_controller_soil_moisture_6": ("Zucchini primary", 48, 60),
}

HISTORY = {
    "Tomato": "sensor.vegitable_garden_timer_tomato_zone_zone_history",
    "Zucchini": "sensor.vegitable_garden_timer_zucchini_and_eggplant_zone_zone_history",
    "Corn": "sensor.flower_garden_back_lawn_time_zone_4_zone_history",
}


def ha_get(base: str, token: str, path: str) -> dict:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ha-url", default="")
    ap.add_argument("--token", default="")
    ap.add_argument("--dry-print", action="store_true")
    ap.add_argument("--probe-reach", action="store_true")
    args = ap.parse_args()

    if args.dry_print:
        print(json.dumps({"soil": list(SOIL), "history": HISTORY}, indent=2))
        return 0

    if not args.ha_url or not args.token:
        print("Need --ha-url and --token (or --dry-print)", file=sys.stderr)
        return 2

    warnings: list[str] = []
    rows = []
    for eid, (label, lo, hi) in SOIL.items():
        try:
            st = ha_get(args.ha_url, args.token, f"/api/states/{eid}")
            val = float(st.get("state"))
        except (urllib.error.URLError, ValueError, TypeError, json.JSONDecodeError) as exc:
            warnings.append(f"{eid}: {exc}")
            continue
        in_band = lo <= val <= hi
        # Critical under-water: zucchini primary very dry
        critical = eid.endswith("_6") and val < 30
        rows.append(
            {
                "entity_id": eid,
                "label": label,
                "moisture": val,
                "target": f"{lo}-{hi}",
                "in_band": in_band,
                "critical_dry": critical,
            }
        )
        if critical:
            warnings.append(f"{label} critically dry at {val}%")

    hist = {}
    for name, eid in HISTORY.items():
        try:
            st = ha_get(args.ha_url, args.token, f"/api/states/{eid}")
            hist[name] = {
                "state": st.get("state"),
                "run_time": (st.get("attributes") or {}).get("run_time"),
            }
        except urllib.error.URLError as exc:
            hist[name] = {"error": str(exc)}

    reach = None
    if args.probe_reach:
        try:
            req = urllib.request.Request(
                args.ha_url.rstrip("/") + "/api/services/agentic_watering/probe_reach",
                data=b"{}",
                headers={
                    "Authorization": f"Bearer {args.token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                reach = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            reach = {"ok": False, "error": str(exc)}
            warnings.append(f"probe_reach: {exc}")

    out = {"soil": rows, "history": hist, "reach": reach, "warnings": warnings}
    print(json.dumps(out, indent=2))
    # Soft fail: critical dry after a watering night should be investigated
    if any(r.get("critical_dry") for r in rows):
        print("WARN: critical dry soil present — review last dusk plan", file=sys.stderr)
        return 1
    if args.probe_reach and isinstance(reach, dict) and not reach.get("ok", True):
        return 1
    print("OK: live verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
