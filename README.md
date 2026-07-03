# Agentic Watering for Home Assistant (HACS)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/zlatko-lakisic/hacs-agentic-watering)](LICENSE)

Sequential AI-assisted irrigation for Home Assistant: a reusable **blueprint** plus generic **script** and **REST command** packages. All site-specific zones, sensors, API keys, and runtime helpers are configured in your blueprint automation instance — nothing is hardcoded to a particular garden.

## What you get

| Component | Entity / path |
|-----------|----------------|
| Blueprint | `zlatko-lakisic/smart_sequential_watering.yaml` |
| Script | `script.ai_sequential_watering` |
| REST commands | `rest_command.openweathermap_5day_forecast`, `open_meteo_precipitation_past_24h`, `homeassistant_history_*`, `ollama_chat_completions` |

## Prerequisites

- Home Assistant **2024.6.0** or newer
- [HACS](https://hacs.xyz/) installed
- An LLM HTTP API (OpenAI-compatible chat completions endpoint)
- Irrigation integration exposing start/stop services (e.g. Orbit B-hyve `bhyve.start_watering` / `bhyve.stop_watering`)

## Installation

See **[docs/INSTALL.md](docs/INSTALL.md)** for full setup including `configuration.yaml` package includes and a site instance template.

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

## License

MIT — see [LICENSE](LICENSE).
