# DaemonOS

**AI-native, headless execution operating system and device-management stack** for turning inexpensive phones and other supported hardware into secure, remotely managed execution nodes.

DaemonOS is not merely an Android agent application, a generic LLM wrapper, or a phone-farm dashboard. It provides a machine-native control plane and execution model with explicit capability-based authorization, durable tasks, simulated and real provisioning paths, and clear security boundaries.

## Status

| Area | State |
|------|--------|
| Core task lifecycle & contracts | **Implemented** (simulated) |
| Capability manifests & auth | **Implemented** |
| Simulated device enrollment | **Implemented** |
| Fleet inventory & health | **Implemented** |
| Flash dry-run / simulator backend | **Implemented** |
| Versioned HTTP API (`/v1/...`) | **Implemented** |
| Physical Android flashing | **Planned** — not claimed complete |
| Production credential store | **Planned** |
| Multi-backend real hardware | **Planned** |

This branch delivers a complete vertical slice against the **simulator**. Physical device support is intentionally out of scope for the initial milestone.

## Architecture (modules)

| Module | Role |
|--------|------|
| `daemonos.core` | Task/result contracts, lifecycle, capabilities, auth, evidence |
| `daemonos.images` | Image manifests, compatibility, signature model |
| `daemonos.flash` | Discovery, pluggable backends, simulator, dry-run safeguards |
| `daemonos.provision` | Enrollment lifecycle, short-lived credentials |
| `daemonos.fleet` | Inventory, health, capability discovery |
| `daemonos.api` | Versioned FastAPI control plane |
| `daemonos.runtime` | Task store + simulated executor |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for boundaries and lifecycle details.

## Relationship to existing work

- **Octopie** (`TheBabelDragon/Octopie`): secure multi-node head architecture with explicit authorization and simulation. DaemonOS reuses the *ideas* of capability admission, audit, and simulated nodes but does **not** fork or import Octopie code. Ownership boundary: Octopie remains the specialized multi-arm head; DaemonOS is the broader execution OS + provisioning stack.
- **Aurora family** (aurora-coordination, throne-room, metafield-engine, etc.): coordination and field/sensing layers. DaemonOS does not embed Aurora; integration points can be added later via adapters without coupling the trusted execution core to any LLM or sensing stack.

## Quick start

```bash
# Requires Python 3.11+
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest -q

# Start API
daemonos serve --host 127.0.0.1 --port 8080
```

### Minimal flow (simulator)

```bash
# 1. Enroll a simulated node
curl -s -X POST http://127.0.0.1:8080/v1/bootstrap/enroll \
  -H 'Content-Type: application/json' \
  -d '{"device_serial":"sim-1","requested_capabilities":["task.submit","task.execute","task.cancel"]}' \
  | tee enroll.json

TOKEN=$(python -c "import json; print(json.load(open('enroll.json'))['token_id'])")

# 2. List nodes
curl -s http://127.0.0.1:8080/v1/nodes -H "Authorization: Bearer $TOKEN"

# 3. Submit a task
curl -s -X POST http://127.0.0.1:8080/v1/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"capability":"echo","parameters":{"message":"hello DaemonOS"},"idempotency_key":"demo-1"}'
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Security / threat model](docs/SECURITY.md)
- [Device compatibility](docs/DEVICE_COMPATIBILITY.md)
- [Provisioning](docs/PROVISIONING.md)
- [API](docs/API.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache-2.0 — see [LICENSE](LICENSE).

## Language choice

Python 3.11+ was selected to align with the existing TheBabelDragon ecosystem (Octopie, Aurora tools) and for rapid, testable scaffolding of the control plane and simulator. Device-side agents and flash backends may later use other languages; the portable core stays hardware-independent.
