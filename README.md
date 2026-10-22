# DaemonOS

**AI-native, headless execution operating system and device-management stack** for turning inexpensive phones and other supported hardware into secure, remotely managed execution nodes.

DaemonOS is not merely an Android agent application, a generic LLM wrapper, or a phone-farm dashboard. It provides a machine-native control plane and execution model with explicit capability-based authorization, durable tasks, hardware discovery, deployment planning, and clear security boundaries.

DaemonOS is an **execution substrate**, not an AI model. External agents (ChatGPT, local LLMs, scripts, humans) interact through versioned machine-readable APIs.

## Status

| Area | State |
|------|--------|
| Core task lifecycle & contracts | **Implemented** (simulated) |
| Capability manifests & auth | **Implemented** |
| Simulated device enrollment | **Implemented** |
| Fleet inventory & health | **Implemented** |
| Flash dry-run / simulator backend | **Implemented** |
| Agent-native hardware discovery | **Implemented** (mock provider) |
| Versioned device capability profile | **Implemented** |
| Deterministic deployment planner | **Implemented** |
| Compatibility catalog (synthetic) | **Implemented** |
| Self-describing `/v1/operations` | **Implemented** |
| Versioned HTTP API (`/v1/...`) | **Implemented** |
| Physical Android flashing | **Planned** — not claimed complete |
| Real ADB/fastboot discovery | **Planned** |
| Production credential store | **Planned** |

## Architecture (modules)

| Module | Role |
|--------|------|
| `daemonos.core` | Task/result contracts, lifecycle, capabilities, auth, evidence |
| `daemonos.discovery` | Provider-based hardware discovery, observations, capability profiles |
| `daemonos.catalog` | Versioned compatibility catalog (targets, strategies) |
| `daemonos.planner` | Deterministic deployment planner (never executes) |
| `daemonos.images` | Image manifests, compatibility, signature model |
| `daemonos.flash` | Pluggable backends, simulator, dry-run safeguards |
| `daemonos.provision` | Enrollment lifecycle, short-lived credentials |
| `daemonos.fleet` | Inventory, health, capability discovery |
| `daemonos.api` | Versioned FastAPI control plane |
| `daemonos.runtime` | Task store + simulated executor |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q

# Offline discover + plan demo (no hardware, no LLM keys)
PYTHONPATH=src python examples/discover_and_plan.py

# API server
daemonos serve --host 127.0.0.1 --port 8080
```

### Agent discovery flow

```bash
# Self-describe
curl -s http://127.0.0.1:8080/v1/operations

# Enroll (dev bootstrap)
TOKEN=$(curl -s -X POST http://127.0.0.1:8080/v1/bootstrap/enroll \
  -H 'Content-Type: application/json' \
  -d '{"device_serial":"agent-1","requested_capabilities":["discover","plan","task.submit","task.execute"]}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token_id'])")

# Discover devices and plan
curl -s http://127.0.0.1:8080/v1/discovery/devices -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://127.0.0.1:8080/v1/plan \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"provider":"mock","device_key":"mock-pixel-like","objective":"run_agent"}'
```

## Documentation

- [Discovery & planning](docs/DISCOVERY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security / threat model](docs/SECURITY.md)
- [Device compatibility](docs/DEVICE_COMPATIBILITY.md)
- [Provisioning](docs/PROVISIONING.md)
- [API](docs/API.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache-2.0 — see [LICENSE](LICENSE).
