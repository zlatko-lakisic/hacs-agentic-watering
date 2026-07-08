# Diagnose & Fix: Irrigation LLM Returns Tool-Call JSON Instead of `MINUTES: N`

## Mission

Home Assistant’s dawn/dusk watering script calls
`https://ai-orchestrator.mostardesigns.com/v1/chat/completions` with a **plain OpenAI-style chat completion** (no `tools`, no agent loop). The model often replies with a **hallucinated / leaked plant-knowledge MCP tool call** instead of ending with:

```text
MINUTES: <integer 0-25>
```

HA then fail-closes that zone to **0 minutes** and does **not** open valves.

**Your job:** diagnose why the orchestrator/model emits MCP tool-call JSON for this endpoint, and fix it so watering requests reliably return parseable `MINUTES: N` text. Prefer fixing on the **AI/orchestrator** side. Do not reintroduce plant-knowledge lookup into the HA integration.

---

## Architecture (current, intentional)

| Layer | Role |
|-------|------|
| **Home Assistant** (`hacs-agentic-watering`) | Assembles zone **facts** only: plant label/profile, area, sun, hardware/flow, days since irrigation, last run duration, soil probes, precip, forecast, temps. Calls chat completions. Parses last line `MINUTES: N`. Opens valves if `run_minutes >= 2`. |
| **AI orchestrator** | `POST /v1/chat/completions` — should return normal assistant **text** for this client. |
| **Plant-knowledge MCP** (AI side only) | Available to real agents with a tool loop. **Not** invoked by HA. HA no longer ships plant CSVs / `get_water_requirement_mm`. |

### HA request shape (exact)

Endpoint:

```text
https://ai-orchestrator.mostardesigns.com/v1/chat/completions
```

Payload HA builds (no tools):

```json
{
  "model": "qwen2.5:14b-instruct",
  "temperature": 0,
  "max_tokens": 500,
  "stream": false,
  "messages": [
    { "role": "system", "content": "<zone_llm_system_prompt>" },
    { "role": "user", "content": "<zone_llm_prompt with sensor/zone facts>" }
  ]
}
```

REST helper lives in:

`custom_components/agentic_watering/packages/rest_command_ai_watering.yaml`  
(`ollama_chat_completions`, `timeout: 86400`)

Script package:

`custom_components/agentic_watering/packages/smart_sequential_watering_script.yaml`

Parser: find last line where `head.upper() == "MINUTES"` and tail matches `^\d+$`, clamp to `0–25`. If not parsed after optional one retry → `run_minutes = 0`.

---

## What already changed on HA (do not undo)

1. Removed plant-knowledge **service call** from watering assembly.
2. Removed plant-knowledge from **fail-closed gate** (gate now only blocks leftover Jinja/`<FILL>` placeholders).
3. Removed injected line like `Knowledge base (plant-knowledge MCP): … weekly need ≈ X mm`.
4. Zone `plant_profile` is a plain fact string (e.g. `"Tall fescue lawn grass"`).
5. Removed bundled CSVs / `plant_knowledge.py` / `get_water_requirement_mm` from the HACS integration.
6. Missing facts default instead of fail-closed (`days_since` → `0`, last run → `0`, missing weather → empty/`unknown`, etc.).

System prompt now explicitly says HA only supplies facts; model should use its own plant knowledge / MCP on the AI side if available in a real agent — but this HA client is **not** an agent session.

---

## Failure evidence (latest dawn simulate dry-run)

**When:** 2026-07-08 ~09:19–09:21 America/New_York  
(`2026-07-08T13:19:26Z`–`13:21:33Z`)

**How:** Manual `script.ai_sequential_watering` with `simulate: true`, dawn lawns only (East Lawn + Kitchen Lawn). Valves never called.

**Model select:** `input_select.ai_dusk_watering_ollama_model` = `qwen2.5:14b-instruct`

### Simulate report (`input_text.ai_watering_simulate_report`, max 255 chars — truncated)

```text
East Lawn: 0 min (LLM 0 parse-fail retry) | HTTP 200 | {\ "name": "plant_knowledge_mcp_plant_knowledge_svc_cluster_local_8_ab8816c0", \ "parameters": {"query": "tall fescue lawn grass"}}
Kitchen Lawn: 0 min (LLM 0 retry) | HTTP 200 | When c
```

Interpretation:

- Assembly **passed** (LLM was called).
- HTTP **200**.
- East Lawn content is MCP-style tool JSON, not `MINUTES:`.
- Kitchen Lawn also failed to yield a usable `MINUTES:` line after retry (snippet truncated by helper).
- Both zones → simulated **0 min** → no valve action (expected for simulate).

### Earlier dry-run samples (same class of bug)

Previous simulate (before plant-catalog removal) also showed:

- East Lawn: HTTP 200 + prose / incomplete output + `parse-fail retry` → 0 min
- Flower Bed: HTTP 200 + starts with `{"name` … → 0 min

So this is **not** caused only by the old HA plant-knowledge injection; it continues after removal.

### Successful assembly, failed product outcome (live dawn this morning)

| Time (EDT) | Event |
|------------|--------|
| 05:31:14 | Automation `AI Sequential Watering at Dawn` triggered (sunrise) |
| 05:31:14 | `script.ai_sequential_watering` started (live, not simulate) |
| 05:33:14 | next_index `1 → 2` (East Lawn done at **0 min**) |
| 05:34:34 | Run finished (Kitchen Lawn also **0 min**) |

Zone history unchanged since Jul 6 (no watering occurred):

- East Lawn: `2026-07-06T09:30:16+00:00`
- Kitchen Lawn: `2026-07-06T09:33:22+00:00`

No `Prompt assembly failed` / `Fail-closed: … LLM not called` for that morning run — times match LLM latency, then skip.

Orbit **rain delay** was also on for some controllers (East Lawn delay=9 days auto/rain; Back lawn delay=1 day) — secondary risk if minutes ever go >0, not the direct cause of this morning’s 0 because HA never reached `bhyve.start_watering`.

---

## System prompt HA sends (current)

```text
You are the irrigation decision-maker for a residential garden zone. Your goal: keep the zone's plants healthy while never applying more water than they need. Overwatering wastes water and harms roots; underwatering stresses plants.

You will receive raw data: the zone profile (plant type, area, sun exposure, hardware and flow rate), hourly precipitation for the past 72 hours, current and forecast weather, and soil probe readings when available.

Missing or unknown facts are provided with defaults like 0 or unknown. Use plant knowledge you already have for water requirements; Home Assistant only supplies sensor and zone facts.

Reason step by step:
1. Estimate how much water this plant type needs per week in this season, and therefore what its current deficit is given days since last irrigation.
2. Total the effective recent rainfall. Treat any single-hour precipitation value that is wildly inconsistent with surrounding hours as a possible data artifact and say so.
3. If a soil probe reading is present, it overrides estimates: adequate moisture means do not water.
4. Check the forecast: imminent significant rain reduces or eliminates the need to water now.
5. Convert any remaining water need into minutes using the zone's hardware flow rate and area.

Zero is a normal and frequent correct answer — any time recent rainfall or soil moisture already covers the plant's needs, the answer is 0.

Output format: your reasoning in at most 120 words, then a final line exactly:
MINUTES: <integer 0-25>
```

### User prompt fact lines HA includes

- Zone label / entity
- Zone profile JSON (includes `plant_profile` text)
- Days since last irrigation (default `0` if unknown)
- Last run duration minutes (default `0`)
- Garden temp now / 24h peak (or `unknown`)
- Optional heuristic probe skip hint
- Soil moisture context JSON
- Open-Meteo past 72h precip JSON
- Weather/forecast context JSON
- OpenWeatherMap short forecast JSON (may be `[]` if API/key/entity missing)

Blueprint still configures stale entity IDs in some inputs (`weather.home_2`, `sensor.home_precipitation` — missing on live HA; live weather is `weather.home` / `weather.forecast_home`). That weakens forecast facts but is separate from the tool-call leak.

---

## Root-cause hypotheses to investigate (AI side)

1. **Orchestrator injects MCP tools / tool-choice** into every `/v1/chat/completions` request even when client sends none.
2. **Model/system template** trained or stubbed to emit `plant_knowledge_mcp_*` tool calls when it sees plant names.
3. **Agent middleware** rewrites completions into tool-call envelopes without executing tools or returning final text.
4. Retry path still gets tool JSON; HA retry only appends “end with `MINUTES:`” and does one more chat call — still no tool execution.

Broken response shape observed:

```json
{
  "name": "plant_knowledge_mcp_plant_knowledge_svc_cluster_local_8_ab8816c0",
  "parameters": { "query": "tall fescue lawn grass" }
}
```

Required response shape:

```text
<short reasoning ≤120 words>
MINUTES: 12
```

---

## Acceptance criteria

1. Replay East Lawn + Kitchen Lawn fact prompts against the orchestrator; both return HTTP 200 with a final line matching `MINUTES: \d+`.
2. No tool-call JSON (`name` / `parameters` / `tool_calls`) in `choices[0].message.content` for this HA client path.
3. Optional: document whether plant-knowledge MCP is used **inside** the orchestrator for this route (OK), vs. exposing raw tool calls to HA (not OK).
4. Confirm with a HA dawn simulate dry-run (`simulate: true`, East+Kitchen lawns) that report lines are **not** `parse-fail` and preferably show non-zero minutes when conditions warrant (or explicit `MINUTES: 0` with reasoning).
5. Do **not** restore plant-knowledge CSV/service into `hacs-agentic-watering`.

---

## Suggested investigation steps

1. Capture one full orchestrator request/response for the failing East Lawn call (headers, whether tools were injected server-side, raw `choices`).
2. Call the same endpoint with tools disabled / `tool_choice: "none"` if supported; compare.
3. If the stack must use plant-knowledge MCP, wrap an **internal** tool loop on the orchestrator and only return final assistant text to HA.
4. Add a regression test: fixture prompts that mention “Tall fescue lawn grass” / “corn plants” must not return MCP tool JSON.
5. Lower response timeout for HA later (currently 86400s) — separate ops issue; not the parse bug.

---

## Repro from HA (simulate, valves safe)

Call `script.ai_sequential_watering` with dawn zones + `simulate: true` (same fields as `smart_watering_lawns_dawn_blueprint_input.yaml`, but use a live weather entity like `weather.home`, empty/missing precip OK).

Zones:

```yaml
- label: East Lawn
  entity_id: valve.east_lawn_timer_east_lawn_zone_zone
  zone_history_sensor: sensor.east_lawn_timer_east_lawn_zone_zone_history
  area_sqm: 60
  plant_profile: Tall fescue lawn grass
  # … sun/hardware/flow as in smart_watering_lawns_zones.yaml
- label: Kitchen Lawn
  entity_id: valve.flower_garden_back_lawn_time_back_lawn_zone_zone
  zone_history_sensor: sensor.flower_garden_back_lawn_time_back_lawn_zone_zone_history
  area_sqm: 36
  plant_profile: Two lawn sections, mostly grass with a few lilies between
```

Read result from `input_text.ai_watering_simulate_report`.

---

## Related context chronologically

- **2026-07-07 dusk:** many zones fail-closed on bad `zone_history_sensor` IDs + missing Corn plant knowledge (HA side) → all 0 / no LLM. **Fixed** (sensor IDs + later removed plant gate).
- **2026-07-08 ~05:31 dawn:** assembly OK enough to run ~3.5 min; both lawns still 0 minutes; history unchanged since Jul 6.
- **2026-07-08 ~09:19 dawn simulate after plant-catalog removal:** assembly OK, LLM HTTP 200, **tool-call JSON parse-fail** still present.

Primary remaining bug for valve actuation: **orchestrator/model output format for the HA chat-completions client.**
