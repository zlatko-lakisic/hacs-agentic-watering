---
version: "1.0.0"
---

[![CI](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml/badge.svg)](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml)

> **CI:** Green badge = all checks passing on `main`. Red = see [Actions](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml).

# Agentic Watering

Home Assistant blueprint and YAML packages for **sequential AI-assisted irrigation**.

- **Blueprint** — `Smart sequential watering` automation (sunrise/sunset, seasonal window, zone blocks)
- **Script** — `script.ai_sequential_watering` (weather APIs, Recorder history, per-zone LLM, valve control)
- **REST commands** — OpenWeatherMap, Open-Meteo, Recorder history, LLM chat completions

Site-specific zones, sensors, API keys, and runtime helpers stay in your own `configuration.yaml` / packages.
