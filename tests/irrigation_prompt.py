"""Prompt assembly helpers and tests for goal-framed irrigation."""

from __future__ import annotations

import json
import re
from typing import Any

EAST_LAWN_PROFILE: dict[str, Any] = {
    "label": "East Lawn",
    "entity_id": "valve.east_lawn_timer_east_lawn_zone_zone",
    "area_sqm": 60,
    "sun_exposure": "35 percent shade / partial sun, 65 percent sun",
    "plant_profile": "Tall fescue lawn grass",
    "irrigation_hardware": (
        "Two Orbit H2O-Six style gear-drive sprinklers, spaced apart, "
        "each about 180 degree arc"
    ),
    "estimated_flow_gpm": "3.0-6.0 combined",
    "notes": "Adjustable 25-360 degree arc, typical operating pressure 15-65 psi",
}

SYSTEM_PROMPT_LINES = [
    "You are the irrigation decision-maker for a residential garden zone. Your goal: keep the zone's plants healthy while never applying more water than they need. Overwatering wastes water and harms roots; underwatering stresses plants.",
    "",
    "You will receive raw data: the zone profile (plant type, area, sun exposure, hardware and flow rate), hourly precipitation for the past 72 hours, current and forecast weather, and soil probe readings when available.",
    "",
    "Reason step by step:",
    "1. Estimate how much water this plant type needs per week in this season, and therefore what its current deficit is given days since last irrigation.",
    "2. Total the effective recent rainfall. Treat any single-hour precipitation value that is wildly inconsistent with surrounding hours as a possible data artifact and say so.",
    "3. If a soil probe reading is present, it overrides estimates: adequate moisture means do not water.",
    "4. Check the forecast: imminent significant rain reduces or eliminates the need to water now.",
    "5. Convert any remaining water need into minutes using the zone's hardware flow rate and area.",
    "",
    "Zero is a normal and frequent correct answer — any time recent rainfall or soil moisture already covers the plant's needs, the answer is 0.",
    "",
    "Output format: your reasoning in at most 120 words, then a final line exactly:",
    "MINUTES: <integer 0-25>",
]

SYSTEM_PROMPT = "\n".join(SYSTEM_PROMPT_LINES)

PLACEHOLDER_RE = re.compile(r"<[^>]*FILL[^>]*>", re.IGNORECASE)
UNRENDERED_TEMPLATE_RE = re.compile(r"\{\{|\}\}")


def build_system_prompt(*, has_soil_probe: bool = False) -> str:
    lines = list(SYSTEM_PROMPT_LINES[:-3])
    if has_soil_probe:
        lines.extend(
            [
                "",
                "Soil probe rules (when Soil moisture context shows has_soil_probe true):",
                "- Soil moisture readings (0-100%, higher is wetter) override rainfall and deficit estimates when they indicate adequate moisture.",
                "- Follow the adjustment_guide in Soil moisture context for plant-specific target ranges.",
                "- Answer MINUTES: 0 when probe moisture is adequate for the plant type.",
                "- A heuristic probe hint may appear in the user message; treat strong SKIP hints as MINUTES: 0.",
            ]
        )
    lines.extend(SYSTEM_PROMPT_LINES[-3:])
    return "\n".join(lines)


def build_user_prompt(
    *,
    days_since: str | int,
    last_run_minutes: str,
    knowledge_block: str,
    garden_temp_f: float,
    garden_peak_f: float,
    open_meteo: dict[str, Any],
    forecast_short: list[dict[str, Any]],
    accuweather: str = "[]",
    soil_context: dict[str, Any] | None = None,
    zone_profile: dict[str, Any] | None = None,
) -> str:
    profile = zone_profile or EAST_LAWN_PROFILE
    soil = soil_context or {"has_soil_probe": False}
    lines = [
        f"Zone label: {profile['label']}",
        f"Zone entity: {profile['entity_id']}",
        "",
        f"Zone profile: {json.dumps(profile)}",
        "",
        f"Days since last irrigation: {days_since}",
        f"Last run duration (minutes): {last_run_minutes}",
        "",
        knowledge_block,
        "",
        f"Garden temperature now (F): {garden_temp_f}",
        f"Garden temperature 24h peak (F): {garden_peak_f}",
        f"Soil moisture context: {json.dumps(soil)}",
        f"Open-Meteo past 72h precipitation: {json.dumps(open_meteo)}",
        f"AccuWeather context: {accuweather}",
        f"OpenWeatherMap forecast (next ~24h): {json.dumps(forecast_short)}",
    ]
    return "\n".join(lines)


def has_unresolved_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.search(text) or UNRENDERED_TEMPLATE_RE.search(text))


def numbered_steps_on_separate_lines(system_prompt: str) -> bool:
    for step in ("1.", "2.", "3.", "4.", "5."):
        if f"\n{step}" not in f"\n{system_prompt}":
            return False
    return True


def parse_minutes(raw: str) -> tuple[bool, int]:
    """Parse last MINUTES: line; returns (parsed_ok, minutes)."""
    text = re.sub(r"(?s)```(?:json)?\s*", "", raw)
    text = text.replace("```", "").strip()
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        head, _, tail = line.partition(":")
        if head.strip().upper() != "MINUTES":
            continue
        tail = tail.strip()
        if re.fullmatch(r"\d+", tail):
            value = int(tail)
            return True, max(0, min(value, 25))
    return False, 0


def hourly_precip(hourly_mm: list[float], hours: int = 72) -> dict[str, Any]:
    total = round(sum(hourly_mm), 3)
    mx = round(max(hourly_mm) if hourly_mm else 0.0, 3)
    rows = [{"t": f"h-{i}", "mm": round(v, 3)} for i, v in enumerate(hourly_mm)]
    return {
        "dataset": "open_meteo_hourly_grid",
        "hours": hours,
        "precipitation_mm_sum": total,
        "max_hourly_precipitation_mm": mx,
        "rained_in_past_72h_estimate": total >= 0.1,
        "hourly_mm": rows,
    }
