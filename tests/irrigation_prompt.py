"""Goal-framed irrigation prompt helpers (mirrors HA harness parsing)."""

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

SYSTEM_PROMPT = """You are the irrigation decision-maker for a residential garden zone. Your goal: keep the zone's plants healthy while never applying more water than they need. Overwatering wastes water and harms roots; underwatering stresses plants.

You will receive raw data: the zone profile (plant type, area, sun exposure, hardware and flow rate), hourly precipitation for the past 72 hours, current and forecast weather, and soil probe readings when available.

Reason step by step:
1. Estimate how much water this plant type needs per week in this season, and therefore what its current deficit is given days since last irrigation.
2. Total the effective recent rainfall. Treat any single-hour precipitation value that is wildly inconsistent with surrounding hours as a possible data artifact and say so.
3. If a soil probe reading is present, it overrides estimates: adequate moisture means do not water.
4. Check the forecast: imminent significant rain reduces or eliminates the need to water now.
5. Convert any remaining water need into minutes using the zone's hardware flow rate and area.

Zero is a normal and frequent correct answer — any time recent rainfall or soil moisture already covers the plant's needs, the answer is 0.

Output format: your reasoning in at most 120 words, then a final line exactly:
MINUTES: <integer 0-25>"""


def build_user_prompt(
    *,
    days_since: str,
    last_run_minutes: str,
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
        f"Garden temperature now (F): {garden_temp_f}",
        f"Garden temperature 24h peak (F): {garden_peak_f}",
        f"Soil moisture context: {json.dumps(soil)}",
        f"Open-Meteo past 72h precipitation: {json.dumps(open_meteo)}",
        f"AccuWeather context: {accuweather}",
        f"OpenWeatherMap forecast (next ~24h): {json.dumps(forecast_short)}",
    ]
    return "\n".join(lines)


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
