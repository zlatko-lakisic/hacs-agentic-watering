#!/usr/bin/env python3
"""Replay goal-framed irrigation prompts against the configured LLM (Task 2 protocol)."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "agentic_watering"))

from irrigation_prompt import (
    EAST_LAWN_PROFILE,
    SYSTEM_PROMPT,
    build_user_prompt,
    hourly_precip,
    parse_minutes,
)
from plant_knowledge import format_knowledge_block, resolve_water_requirement_mm


def _knowledge_block() -> str:
    result = resolve_water_requirement_mm(
        EAST_LAWN_PROFILE["plant_profile"],
        climate_setting="temperate_humid",
    )
    return format_knowledge_block(result)


@dataclass
class Case:
    name: str
    build_user: Callable[[], str]
    expect_minutes: int | None = None
    expect_nonzero: bool = False
    expect_zero_or_low: bool = False
    note_rainfall: bool = False
    note_artifact: bool = False


def _dry_forecast() -> list[dict[str, Any]]:
    return [
        {"dt_txt": "2026-07-07 15:00:00", "temp_f": 78, "rain_mm_3h": 0.0},
        {"dt_txt": "2026-07-07 18:00:00", "temp_f": 76, "rain_mm_3h": 0.0},
    ]


def _heavy_rain_forecast() -> list[dict[str, Any]]:
    return [
        {"dt_txt": "2026-07-07 15:00:00", "temp_f": 72, "rain_mm_3h": 0.0},
        {"dt_txt": "2026-07-07 18:00:00", "temp_f": 70, "rain_mm_3h": 18.0},
    ]


def build_cases() -> list[Case]:
    def real_failure() -> str:
        hours = [0.0] * 48 + [42.4] + [0.0] * 23
        return build_user_prompt(
            days_since=2,
            last_run_minutes="10",
            knowledge_block=_knowledge_block(),
            garden_temp_f=72.0,
            garden_peak_f=75.0,
            open_meteo=hourly_precip(hours),
            forecast_short=_dry_forecast(),
        )

    def drought() -> str:
        return build_user_prompt(
            days_since="5.0",
            last_run_minutes="8",
            knowledge_block=_knowledge_block(),
            garden_temp_f=85.0,
            garden_peak_f=88.0,
            open_meteo=hourly_precip([0.0] * 72),
            forecast_short=_dry_forecast(),
        )

    def partial_rain() -> str:
        hours = [0.0] * 47 + [8.0] + [0.0] * 24
        return build_user_prompt(
            days_since="3.0",
            last_run_minutes="12",
            knowledge_block=_knowledge_block(),
            garden_temp_f=80.0,
            garden_peak_f=82.0,
            open_meteo=hourly_precip(hours),
            forecast_short=_dry_forecast(),
        )

    def forecast_rain() -> str:
        return build_user_prompt(
            days_since="4.0",
            last_run_minutes="10",
            knowledge_block=_knowledge_block(),
            garden_temp_f=78.0,
            garden_peak_f=80.0,
            open_meteo=hourly_precip([0.0] * 72),
            forecast_short=_heavy_rain_forecast(),
        )

    def artifact_spike() -> str:
        hours = [0.3] * 35 + [32.4] + [0.4] * 36
        return build_user_prompt(
            days_since="2.0",
            last_run_minutes="9",
            knowledge_block=_knowledge_block(),
            garden_temp_f=74.0,
            garden_peak_f=76.0,
            open_meteo=hourly_precip(hours),
            forecast_short=_dry_forecast(),
        )

    return [
        Case("real_failure_42_4mm", real_failure, expect_minutes=0, note_rainfall=True),
        Case("drought_5d_85f", drought, expect_nonzero=True),
        Case("partial_rain_8mm", partial_rain),
        Case("forecast_heavy_rain", forecast_rain, expect_zero_or_low=True),
        Case("artifact_32_4mm_spike", artifact_spike, note_artifact=True),
    ]


def call_llm(
    *,
    api_url: str,
    api_key: str,
    model: str,
    user_prompt: str,
    retry: bool,
) -> tuple[int, str]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    content = _post_chat(api_url, api_key, model, messages)
    ok, minutes = parse_minutes(content)
    if ok or not retry:
        return minutes, content
    messages.append({"role": "assistant", "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                "Your previous reply did not include a valid final line. "
                "Restate your reasoning briefly, then end with exactly:\n"
                "MINUTES: <integer 0-25>"
            ),
        }
    )
    content = _post_chat(api_url, api_key, model, messages)
    _, minutes = parse_minutes(content)
    return minutes, content


def _post_chat(
    api_url: str, api_key: str, model: str, messages: list[dict[str, str]]
) -> str:
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 500,
        "stream": False,
        "messages": messages,
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or choices[0].get("text") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="Runs per case")
    parser.add_argument(
        "--model", default=os.environ.get("IRRIGATION_LLM_MODEL", "qwen2.5:14b-instruct")
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get(
            "IRRIGATION_LLM_API_URL",
            "https://ai-orchestrator.mostardesigns.com/v1/chat/completions",
        ),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("IRRIGATION_LLM_API_KEY") or os.environ.get("LLM_API_KEY"),
    )
    args = parser.parse_args()

    if not args.api_key:
        print(
            "Set IRRIGATION_LLM_API_KEY (or LLM_API_KEY) to run live replays.",
            file=sys.stderr,
        )
        return 2

    cases = build_cases()
    failures: list[str] = []
    log: list[dict[str, Any]] = []

    for case in cases:
        print(f"\n=== {case.name} ({args.runs} runs) ===")
        for run in range(1, args.runs + 1):
            user_prompt = case.build_user()
            minutes, content = call_llm(
                api_url=args.api_url,
                api_key=args.api_key,
                model=args.model,
                user_prompt=user_prompt,
                retry=True,
            )
            ok, parsed = parse_minutes(content)
            entry = {
                "case": case.name,
                "run": run,
                "minutes": minutes,
                "parsed": ok,
                "raw": content,
                "zone": EAST_LAWN_PROFILE["label"],
            }
            log.append(entry)
            print(f"  run {run}: MINUTES={minutes} parsed={ok}")
            if case.expect_minutes is not None and minutes != case.expect_minutes:
                failures.append(
                    f"{case.name} run {run}: expected {case.expect_minutes}, got {minutes}"
                )
            if case.expect_nonzero and minutes < 2:
                failures.append(f"{case.name} run {run}: expected nonzero, got {minutes}")
            if case.expect_zero_or_low and minutes > 5:
                failures.append(f"{case.name} run {run}: expected 0/low, got {minutes}")
            if case.note_rainfall and "rain" not in content.lower():
                print("    warning: reasoning did not mention rain")
            if case.note_artifact and "artifact" not in content.lower():
                print("    warning: reasoning did not mention artifact/anomaly")
            time.sleep(0.5)

    out_path = os.environ.get("IRRIGATION_REPLAY_LOG", "tests/replay_irrigation_log.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)
    print(f"\nWrote log: {out_path}")

    if failures:
        print("\nFAILURES:")
        for line in failures:
            print(f"  - {line}")
        return 1

    print("\nAll hard assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
