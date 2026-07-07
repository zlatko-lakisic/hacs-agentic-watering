"""Plant-knowledge lookups for irrigation prompt pre-injection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .plant_knowledge_store import PlantKnowledgeStore
except ImportError:  # pragma: no cover - standalone test imports
    from plant_knowledge_store import PlantKnowledgeStore

_DATA_DIR = Path(__file__).resolve().parent / "data"
_store = PlantKnowledgeStore(_DATA_DIR)


def _rank_candidates(name: str, candidates: list[str]) -> list[str]:
    tokens = [token for token in name.lower().replace("/", " ").split() if len(token) > 2]

    def score(candidate: str) -> tuple[int, int, str]:
        lowered = candidate.lower()
        hits = sum(1 for token in tokens if token in lowered)
        return (-hits, len(lowered), lowered)

    return sorted(dict.fromkeys(candidates), key=score)


def resolve_water_requirement_mm(
    name: str,
    *,
    climate_setting: str | None = None,
    et0_mm_per_week: float | None = None,
) -> dict[str, Any]:
    """Match plant-knowledge MCP semantics, with search fallback for zone labels."""
    direct = _store.get_water_requirement_mm(
        name,
        climate_setting=climate_setting,
        et0_mm_per_week=et0_mm_per_week,
    )
    if direct.get("found"):
        direct["matched_query"] = name
        return direct

    profile = _store.get_plant_profile(name)
    candidates: list[str] = []
    if not profile.get("found"):
        candidates.extend(profile.get("suggestions", []))

    search = _store.search_plants(name, limit=3)
    for plant in search.get("results", []):
        candidate = plant.get("common_name") or plant.get("scientific_name")
        if candidate:
            candidates.append(candidate)

    plants_lower = name.lower()
    if "fescue" in plants_lower and "tall fescue" not in candidates:
        candidates.append("Tall fescue")
    if "lawn" in plants_lower or "grass" in plants_lower:
        for label in ("Tall fescue", "Kentucky bluegrass", "Perennial ryegrass"):
            if label not in candidates:
                candidates.append(label)

    seen: set[str] = set()
    for candidate in _rank_candidates(name, candidates):
        key = candidate.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        retry = _store.get_water_requirement_mm(
            candidate,
            climate_setting=climate_setting,
            et0_mm_per_week=et0_mm_per_week,
        )
        if retry.get("found"):
            retry["matched_query"] = name
            retry["resolved_plant_name"] = candidate
            return retry

    return direct


def format_knowledge_block(result: dict[str, Any]) -> str:
    if not result.get("found"):
        return ""
    plant_name = result.get("plant_name") or result.get("resolved_plant_name") or "plant"
    weekly = result.get("weekly_need_mm")
    factor = result.get("plant_factor")
    et0 = result.get("et0_mm_per_week")
    et0_source = result.get("et0_source", "reference")
    return (
        f"Knowledge base (plant-knowledge MCP): {plant_name} — weekly water need "
        f"≈ {weekly} mm at this ET₀ (plant_factor {factor} × ET₀ {et0} mm/week, "
        f"source: {et0_source}). Source: curated seed dataset, not full WUCOLS."
    )
