---
version: "1.0.1"
---

[![CI](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml/badge.svg)](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/zlatko-lakisic/hacs-agentic-watering)](https://github.com/zlatko-lakisic/hacs-agentic-watering/releases)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

> **CI:** Green badge = all checks passing on `main`. Red = see [Actions](https://github.com/zlatko-lakisic/hacs-agentic-watering/actions/workflows/ci.yml).

<p align="center">
  <img src="https://raw.githubusercontent.com/zlatko-lakisic/hacs-agentic-watering/main/images/readme-hero.png" alt="Agentic Watering" width="480">
</p>

# Agentic Watering

LLM-driven sequential irrigation for Home Assistant: forecast + soil + history → per-zone skip/duration → one valve at a time, MQTT-resumable runs.

**Blueprint:** `zlatko-lakisic/smart_sequential_watering.yaml` · **Script:** `script.ai_sequential_watering`

Works with any integration exposing start/stop watering services (e.g. Orbit B-hyve). Site zones and sensors stay in your blueprint instance.

**Install:** [docs/INSTALL.md](https://github.com/zlatko-lakisic/hacs-agentic-watering/blob/main/docs/INSTALL.md) · **Issues:** [GitHub Issues](https://github.com/zlatko-lakisic/hacs-agentic-watering/issues)
