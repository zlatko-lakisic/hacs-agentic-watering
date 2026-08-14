# Watering verification

## Pre-deploy (no valves)

```bash
python -m unittest tests/test_probe_heuristics.py tests/test_scenario_matrix.py -v
python scripts/mock_watering_run.py
python tests/validate_yaml_packages.py
```

## Live Reach check (no valves)

Drives the real session — pairing, `sessionOverlay`, `mcpTunnel`, registered agents,
the reply, and parsed minutes — using the settings from the HA config entry:

```bash
python scripts/live_reach_test.py --from-ha-config \\your-ha-host\config
python scripts/live_reach_test.py --engine-url https://172.16.90.20:8765 --token ao_xxx
```

Reading the failure:

| Symptom | Cause |
| :--- | :--- |
| `mtls paired: False` | no enrollment token redeemed yet |
| `CERTIFICATE_VERIFY_FAILED … self-signed` | not paired, so no `ca.pem` to trust the engine |
| `WSServerHandshakeError: 403` | engine requires a client cert; pair first |
| `AO session overlay disabled` | set `AGENTIC_SERVE_SESSION_OVERLAY=1` on the engine |
| `mcpTunnel: False` | set `AGENTIC_SERVE_MCP_TUNNEL=1` |
| no `MINUTES:` line | prompt/agent problem, not transport |

## On Home Assistant (after installing 1.4.0+)

1. Configure **Agentic Watering** entry: Jetson engine URL `https://172.16.90.20:8765`,
   API token and **mTLS enrollment token** with `appId: agentic-watering`, weather MCP on.
2. Call `agentic_watering.probe_reach` — expect `paired: true` and `session_overlay: true`.
   Pairing can also be confirmed on disk: `config/agentic_watering_mtls_<entry_id>/`
   should contain `cert.pem`, `key.pem`, `ca.pem`.
3. Run `script.ai_watering_simulate_test` (`simulate: true`) — valves stay closed; check logbook for Reach `question_id`.

## Post-deploy (real conditions)

```bash
python scripts/verify_live_watering.py --ha-url https://ha.mostardesigns.com --token <LONG_LIVED> --probe-reach
```

Then allow one real dusk/dawn; next day re-check soil bands (zucchini should not stay ~21% after a planned 15–25 min run).
