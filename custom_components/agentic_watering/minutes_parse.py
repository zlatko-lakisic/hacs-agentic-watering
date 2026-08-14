"""Parse irrigation MINUTES: lines from LLM / Reach chat replies."""

from __future__ import annotations

import re

_MINUTES_RE = re.compile(r"(?im)^\s*MINUTES\s*:\s*(\d+)\s*$")


def parse_minutes(raw: str, *, max_minutes: int = 25) -> tuple[bool, int]:
    """Return (parsed_ok, minutes clamped to 0..max_minutes). Fail-closed on miss."""
    text = (raw or "").replace("```json", "").replace("```", "").strip()
    found: int | None = None
    for line in reversed(text.splitlines()):
        m = _MINUTES_RE.match(line.strip())
        if m:
            found = int(m.group(1))
            break
    if found is None:
        return False, 0
    return True, max(0, min(int(found), max_minutes))


def clamp_run_minutes(llm_minutes: int, *, parsed: bool, probe_skip: bool) -> int:
    """Apply HA fail-closed clamp used by the sequential watering script."""
    if probe_skip or not parsed:
        return 0
    if llm_minutes < 2:
        return 0
    return max(2, min(llm_minutes, 25))
