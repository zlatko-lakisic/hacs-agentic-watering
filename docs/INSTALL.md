# Installation

## 1. Install the integration

### HACS

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Repository: `https://github.com/zlatko-lakisic/hacs-agentic-watering`
3. Category: **Integration**
4. Search **Agentic Watering** → Download
5. **Restart Home Assistant**

### Manual

From this repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-to-ha.ps1 -ConfigRoot '\\192.168.89.25\config'
```

Restart Home Assistant after copying files.

## 2. Load YAML packages

Add to `configuration.yaml` under `homeassistant: packages:`:

```yaml
homeassistant:
  packages:
    rest_command_ai_watering: !include custom_components/agentic_watering/packages/rest_command_ai_watering.yaml
    smart_sequential_watering_script: !include custom_components/agentic_watering/packages/smart_sequential_watering_script.yaml
```

Reload **Scripts**, **REST commands**, and **Template** entities (or run **Check configuration** then reload YAML).

## 2b. Configure AO Reach (v1.4.0+)

1. On Jetson AO: enable `AGENTIC_SERVE_SESSION_OVERLAY=1` and `AGENTIC_SERVE_MCP_TUNNEL=1`; expose engine `:8765`.
2. Mint two credentials with **`appId: agentic-watering`** (do not reuse `home-assistant` or `comstar-ha`):
   - an **API token** (bearer, sent as `Authorization`)
   - an **mTLS enrollment token** — required when `GET /health` reports `mtls.required: true`
3. **Settings → Devices & services → Agentic Watering** — set engine URL (e.g. `https://172.16.90.20:8765`), paste both tokens, enable weather-mcp, select agents.
4. HA host needs **Node/`npx`** for `@dangahagan/weather-mcp`.
5. Verify: Developer Tools → Services → `agentic_watering.probe_reach` (check `paired: true`).
6. Pre-deploy: `python scripts/mock_watering_run.py` (see [VERIFICATION.md](VERIFICATION.md)).

### mTLS pairing

The engine presents a self-signed certificate and requires a client certificate; a
bearer token alone gets **403** on the WebSocket upgrade. The enrollment token is
redeemed once for client material stored in `config/agentic_watering_mtls_<entry_id>/`
(`cert.pem`, `key.pem`, `ca.pem`) — the `ca.pem` is also what lets the client trust
the engine's self-signed server cert.

- Enrollment token is **one-time**: it is consumed at setup and removed from storage.
- To re-pair later: `agentic_watering.pair` with `enroll_token` (optional `client_name`).
- To reset: `agentic_watering.clear_pairing`.
- CSR generation prefers the `openssl` binary and falls back to the `cryptography`
  package, so it works on HA Core images that ship without `openssl`.

Legacy `rest_command.ollama_chat_completions` remains as automatic fallback if Reach fails.

## 3. Site instance package (your home only)

Create a local package (not part of this repo) with:

- `input_boolean` / `input_number` / `input_text` helpers for run state
- `input_text` helpers for API tokens (OpenWeatherMap, HA Recorder, LLM)
- `input_text` for the per-zone run report (blueprint `simulate_report_text`) — keep `max: 255` (Home Assistant’s hard limit for `input_text`)
- MQTT retained snapshot sensor on topic `homeassistant/ai_watering/active_run_config`
- Optional resume-after-restart automation reading the snapshot sensor

Point blueprint inputs at your helpers, zones, sensors, and irrigation services.

The completion notification summarizes **actual per-zone LLM decisions** (compact lines such as `• East Lawn—0~p`). Set a long-lived access token on the HA Recorder API helper so 24h history reaches the model.

## 4. Create automations from the blueprint

1. **Settings → Automations & scenes → + Create automation → Import blueprint**
2. Select **Smart sequential watering** (`zlatko-lakisic/smart_sequential_watering.yaml`)
3. Configure zones, location, sensors, API helpers, and `watering_script: script.ai_sequential_watering`

Example automation stub:

```yaml
- id: my_ai_watering
  alias: AI Sequential Watering at Dusk
  use_blueprint:
    path: zlatko-lakisic/smart_sequential_watering.yaml
    input:
      zones: [...]
      latitude: 41.0
      longitude: -73.8
      # ... see blueprint for all inputs
      watering_script: script.ai_sequential_watering
```

## Upgrading

After HACS reports an update: download in HACS, restart Home Assistant. Package includes stay the same path under `custom_components/agentic_watering/packages/`.
