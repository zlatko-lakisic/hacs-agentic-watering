# Agentic Watering for Home Assistant (HACS)

<p align="center">
  <img src="images/readme-hero.png" alt="Agentic Watering — LLM-driven sequential irrigation for Home Assistant" width="720">
</p>

[![CI](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml/badge.svg)](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/zlatko-lakisic/hacs-agentic-watering)](https://github.com/zlatko-lakisic/hacs-agentic-watering/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **CI status:** Green = [all checks passed](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml) on `main` (HACS validation, Hassfest, YAML + blueprint tests). Red = open Actions for logs.

Each dusk or dawn run, an LLM reads your **forecast**, **soil moisture**, and **past watering history**, then decides per zone whether to water, skip, and for how long. Zones run **one at a time** through your valve integration; run state is **snapshotted to MQTT** so a interrupted run can resume where it left off. That closed loop — sense → reason → act → remember — is what makes this *agentic*, not just a timer with an API call.

## Prerequisites

Before you read the component list, confirm this fits your setup:

- Home Assistant **2024.6.0** or newer
- [HACS](https://hacs.xyz/) installed
- **AO Reach** to an Agentic Orchestration engine (`:8765`) with `AGENTIC_SERVE_SESSION_OVERLAY=1` and `AGENTIC_SERVE_MCP_TUNNEL=1`, token `appId: agentic-watering` — **or** a legacy OpenAI-compatible chat-completions URL as fallback
- Node.js / `npx` on the HA host when enabling the **weather-mcp** tunnel
- An irrigation integration that exposes **start** and **stop watering** services on valve entities

**Supported irrigation integrations:** anything that provides `domain.start_watering` and `domain.stop_watering` services you can pass into the blueprint — for example **Orbit B-hyve** (`bhyve.start_watering` / `bhyve.stop_watering`). The script calls those services by name; it is not tied to a single vendor.

## How it works

1. **Trigger** — Sunrise, sunset, or manual run via the blueprint automation.
2. **Gather context** — Soil/valve history in HA; optional Open-Meteo/OWM fallback facts.
3. **Per-zone Reach chat** — `agentic_watering.plan_zone_minutes` runs AO dynamic planning with selected overlay agents (`client.irrigation_planner`, `client.irrigation_zone_specialist`) and optional **weather-mcp** tools; reply ends with `MINUTES: 0–25`. Probe-skip rules can force `0`. Falls back to legacy chat-completions if Reach fails.
4. **Water one zone** — Start/stop services run sequentially with a short delay between valves (skipped in simulate mode).
5. **Snapshot state** — MQTT retained run config for resume-after-restart.

### Tests

```bash
python -m unittest tests/test_probe_heuristics.py tests/test_scenario_matrix.py -v
python scripts/mock_watering_run.py          # pre-deploy, no valves
python scripts/verify_live_watering.py --dry-print
```


<p align="center">
  <img src="images/blueprint-import.png" alt="Home Assistant blueprint import — Smart sequential watering" width="640">
</p>
<p align="center"><em>Import the blueprint under Settings → Automations → Create automation → Import blueprint.</em></p>

## What you get

| Component | Entity / path |
|-----------|----------------|
| Blueprint | `zlatko-lakisic/smart_sequential_watering.yaml` |
| Script | `script.ai_sequential_watering` |
| REST commands | `rest_command.openweathermap_5day_forecast`, `open_meteo_precipitation_past_24h` (72h window), `homeassistant_history_*`, `ollama_chat_completions` |

Site-specific zones, sensors, API keys, and runtime helpers live in **your** blueprint instance and a small local instance package — nothing is hardcoded to one garden.

## Installation

See **[docs/INSTALL.md](docs/INSTALL.md)** for `configuration.yaml` package includes and a site instance template.

### Via HACS (recommended)

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/zlatko-lakisic/hacs-agentic-watering` as category **Integration**
3. Search **Agentic Watering**, download, restart Home Assistant
4. Add the package includes to `configuration.yaml` (see INSTALL.md)
5. Create a site instance package (helpers + MQTT snapshot + resume automation)
6. **Settings → Automations → Create automation → Import blueprint** → *Smart sequential watering*

### Manual install

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-ha.ps1 -ConfigRoot '\\your-ha-host\config'
```

Restart Home Assistant, then add the `configuration.yaml` package includes from [docs/INSTALL.md](docs/INSTALL.md).

## Blueprint inputs

The blueprint accepts ordered zone blocks (valve, soil sensors, plant profile, hardware notes), location, weather/history sensors, LLM/API helpers, irrigation services, and runtime state helpers (`in_progress`, `next_index`, MQTT snapshot topic, etc.).

## Disclaimer

This automation controls **real irrigation valves**. An LLM chooses skip/run duration from sensor and weather context — always **test with simulate mode or a short manual run**, watch the first live cycle, and confirm zones behave as expected before leaving it unattended.

## Contributing & issues

- **Bug reports & feature requests:** [GitHub Issues](https://github.com/zlatko-lakisic/hacs-agentic-watering/issues)
- **Pull requests welcome** — run `python tests/validate_yaml_packages.py` and `python tests/validate_blueprint.py` locally; CI must pass on `main`.

## License

MIT — see [LICENSE](LICENSE).
