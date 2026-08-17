"""Parse irrigation MINUTES: lines from LLM / Reach chat replies."""

from __future__ import annotations

import re

# Models routinely emphasise the final answer ("**MINUTES: 20**", "**MINUTES:** 12"),
# so decoration is stripped before matching. Treating those as unparseable made the
# clamp fail closed and skip zones the model had asked to water.
_DECORATION_RE = re.compile(r"[*_`]+")
_LEADING_MARKUP_RE = re.compile(r"^[#>\s]+")
_MINUTES_RE = re.compile(r"(?i)^MINUTES\s*:\s*(\d{1,4})")


def _normalize_line(line: str) -> str:
    return _DECORATION_RE.sub("", _LEADING_MARKUP_RE.sub("", line)).strip()


def parse_minutes(raw: str, *, max_minutes: int = 25) -> tuple[bool, int]:
    """Return (parsed_ok, minutes clamped to 0..max_minutes). Fail-closed on miss."""
    text = (raw or "").replace("```json", "").replace("```", "").strip()
    for line in reversed(text.splitlines()):
        m = _MINUTES_RE.match(_normalize_line(line))
        if m:
            return True, max(0, min(int(m.group(1)), max_minutes))
    return False, 0


def clamp_run_minutes(llm_minutes: int, *, parsed: bool, probe_skip: bool) -> int:
    """Apply HA fail-closed clamp used by the sequential watering script."""
    if probe_skip or not parsed:
        return 0
    if llm_minutes < 2:
        return 0
    return max(2, min(llm_minutes, 25))
