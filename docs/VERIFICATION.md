# Watering verification

## Pre-deploy (no valves)

```bash
python -m unittest tests/test_probe_heuristics.py tests/test_scenario_matrix.py \
    tests/test_parse_irrigation_minutes.py tests/test_script_minutes_jinja.py -v
python scripts/mock_watering_run.py
python tests/validate_yaml_packages.py
```

`test_script_minutes_jinja.py` renders the answer-parsing templates lifted out of
the script package instead of a Python mirror of them, because a mirror-only
suite stayed green while production discarded correct answers.

## Answer parsing check (after any prompt or parser change)

Renders those same templates through the running instance, so the result uses
Home Assistant's own filter semantics:

```bash
python scripts/verify_minutes_template.py --ha-url http://192.168.89.25:8123 --token <LONG_LIVED>
```

Every case must pass. Models emphasise the final line (`**MINUTES: 20**`,
`**MINUTES:** 12`) often enough that a parser accepting only a bare
`MINUTES: 20` will silently skip zones it was told to water.

## Reading the per-zone run report

`input_text.ai_watering_simulate_report` records one compact line per zone;
the suffix says why a zone got zero:

| Line | Meaning |
| :--- | :--- |
| `• Tomato—18` | ran (or planned) 18 minutes |
| `• East Lawn—0~` | AI answered 0 — nothing needed |
| `• Peppers and Kale—0~p` | soil probe already in band, AI not consulted |
| `• Zucchini—0~!` | **AI reply unreadable** — answer discarded, zone skipped |
| `• Corn—0v` | valve unavailable |
| `• Corn—0a` | prompt assembly failed |

A `~!` is a bug in parsing or prompting, never a watering decision — check the
`LLM full response` logbook entry for that zone and compare its final line
against `scripts/verify_minutes_template.py`.

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
