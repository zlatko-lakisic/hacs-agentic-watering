"""Deterministic soil probe SKIP / WATER heuristics (mirrors script YAML)."""

from __future__ import annotations

import re
from typing import Any


def probe_skip_recommendation(
    *,
    plant_profile: str,
    moisture_values: list[float],
) -> str:
    """Return SKIP… or WATER OK… hint string; SKIP prefix means hard force 0."""
    if not moisture_values:
        return "unknown probe values"
    plants = (plant_profile or "").lower()
    mn = min(moisture_values)
    mx = max(moisture_values)

    if mx >= 66:
        return f"SKIP — reply 0: wettest probe {mx:.1f}% >= 66% (saturated)."
    if re.search(r"tomato", plants) and mn >= 45 and mx <= 62:
        return f"SKIP — reply 0: tomato probe(s) {mn:.1f}-{mx:.1f}% within target 45-62%."
    if re.search(r"pepper|kale|basil|parsley", plants) and mn >= 40 and mx <= 65:
        return f"SKIP — reply 0: pepper/herb probe(s) {mn:.1f}-{mx:.1f}% within target 40-65%."
    if re.search(r"hosta|mint|flower", plants) and mn >= 40 and mx <= 68:
        return f"SKIP — reply 0: ornamental probe(s) {mn:.1f}-{mx:.1f}% within target 40-68%."
    if re.search(r"zucchini|eggplant|pea", plants) and mx >= 60:
        return (
            f"SKIP — reply 0: wettest probe {mx:.1f}% >= 60%; driest {mn:.1f}% — zone wet enough."
        )
    if re.search(r"zucchini|eggplant|pea", plants) and mn >= 48 and mx < 60:
        return f"SKIP — reply 0: driest probe {mn:.1f}% in comfortable 48-59% range."
    if re.search(r"corn", plants) and mn >= 45 and mx <= 62:
        return "SKIP — reply 0: corn probe(s) within target 45-62%."
    # Generic fallback: only skip when clearly moist enough for untyped plants.
    # Do NOT use 36-55% — that incorrectly skipped tomato at 38% (target floor 45%).
    if mn >= 55 and mx <= 65:
        return f"SKIP — reply 0: probe(s) moist but adequate at {mn:.1f}-{mx:.1f}%."
    if mn >= 66:
        return f"SKIP — reply 0: wettest probe {mx:.1f}% saturated."
    return (
        f"WATER OK — driest probe {mn:.1f}%, wettest {mx:.1f}%; "
        "add minutes only if below plant minimum in adjustment_guide."
    )


def recommends_skip(hint: str) -> bool:
    return (hint or "").strip().startswith("SKIP")


def soil_adjustment_guide(plant_profile: str) -> str:
    """Corrected minute bands for LLM / overlay agents (not 3–6 min token runs)."""
    plants = (plant_profile or "").lower()
    guide = (
        "Soil probe is the PRIMARY decision signal (0-100%, higher = wetter). "
        "Probe overrides rainfall and deficit estimates when moisture is adequate for plant_profile. "
        "Generic bands: very dry <=25% add 15-25 min for high-water veg / 10-18 for ornamentals; "
        "dry 26-35% add 10-18 min (high-water) / 8-15 ornamentals; "
        "below plant target minimum but above very-dry: size a full session toward mid-target (typically 12-20 min). "
        "Comfortable within plant target → REPLY 0. Wet >=66% always REPLY 0."
    )
    if re.search(r"hosta|mint|flower", plants):
        guide += (
            " Ornamentals (hosta/mint/flowers): target ~40-68%. "
            "REPLY 0 when every probe is 40-68%. Water when driest <40%."
        )
    if re.search(r"tomato", plants):
        guide += (
            " Tomatoes: target ~45-62% (~25 mm/week peak). "
            "REPLY 0 when every probe is 45-62%. "
            "Add a substantial soaker session when any probe <45% (prefer 15-25 min when <32%)."
        )
    if re.search(r"pepper|kale|basil|parsley", plants):
        guide += (
            " Peppers/kale/herbs: target ~40-65% (~16 mm/week). "
            "REPLY 0 when every probe is 40-65% or wetter. Add only when any probe <40%."
        )
    if re.search(r"zucchini|eggplant|pea", plants):
        guide += (
            " Zucchini/eggplant/peas: high water (~25 mm/week). "
            "Use driest reading for add decisions. REPLY 0 if ANY probe >=66% or wettest >=60%. "
            "REPLY 0 when driest is 48-59% and wettest <60%. "
            "When driest <48% (especially <30%), run a full micro-irrigation session 15-25 min — never 1-6 min token runs."
        )
    if re.search(r"corn", plants):
        guide += (
            " Corn: target ~45-62% (~25 mm/week). "
            "REPLY 0 when every probe is 45-62%. When dry or no probe, prefer 12-20 min soaker."
        )
    if re.search(r"lawn|fescue|grass", plants):
        guide += (
            " Tall fescue lawn: ~16 mm/week equivalent. Prefer deep infrequent runs "
            "(typically 12-20 min) when overdue and recent rain is insufficient."
        )
    return guide


def extract_moisture_values(soil_context: dict[str, Any] | None) -> list[float]:
    if not soil_context or not soil_context.get("has_soil_probe"):
        return []
    out: list[float] = []
    for p in soil_context.get("probes") or []:
        if not isinstance(p, dict):
            continue
        raw = p.get("moisture_pct_now")
        try:
            if raw is not None and str(raw).lower() not in (
                "unknown",
                "unavailable",
                "none",
                "",
            ):
                out.append(float(raw))
        except (TypeError, ValueError):
            continue
    return out
