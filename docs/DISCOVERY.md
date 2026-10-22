# Hardware Discovery & Deployment Planning

## Overview

DaemonOS provides a **model-agnostic** discovery and planning layer so external agents (LLMs, scripts, CLIs, humans) can investigate unfamiliar hardware and obtain evidence-backed deployment plans without modifying device state.

DaemonOS is an execution substrate, not an AI model. It works with any agent that can call the versioned HTTP API or import the Python packages.

## Architecture

```
DiscoveryProvider (mock, future: adb, ssh, …)
        │
        ▼
DiscoveryService ──► DeviceCapabilityProfile (schema v1.0)
        │
        ▼
DeploymentPlanner + CompatibilityCatalog
        │
        ▼
PlanResult (candidates, preferred, never authorized/executed)
```

### Provider extension point

Implement `DiscoveryProvider`:

- `name()`, `list_devices()`, `available_probes()`, `run_probe()`
- Optional: override `build_profile()` for custom field mapping

Register via `DiscoveryRegistry.register(provider)`. The core domain model does not change when providers are added.

### Evidence semantics

| Kind | Meaning |
|------|--------|
| `observed` | Directly read from the device |
| `inferred` | Derived from other observations |
| `external` | Catalog, vendor docs, operator claim |
| `unknown` | No evidence |

Each `Observation` carries confidence, source, method, verification flag, and timestamp. Unobserved capabilities are never marked verified.

Probe statuses: `ok`, `failed`, `permission_denied`, `unsupported`, `timeout`, `conflict`.

## Capability profile (schema 1.0)

Machine-readable fields include:

- Identity + identification confidence
- Hardware and runtime facts (all optional)
- Management interfaces
- Positive capabilities, constraints, unavailable list
- Full observation list with provenance
- Unresolved questions and recommended probes
- Supported operations and prerequisites

Serialize with `profile.model_dump(mode="json")`. Validate with `DeviceCapabilityProfile.model_validate(...)`.

## Compatibility catalog

Versioned catalog of:

- **Runtime targets** (agent on existing OS, linux native, alternative image placeholders)
- **Deployment strategies** (invasiveness, prerequisites, verification status)
- **Device family hints** (optional)

Builtin catalog is **synthetic** (`verification=synthetic`). Real-world claims require lab verification labels and must not be fabricated.

## Planner

`DeploymentPlanner.plan(profile, objective="run_agent")` returns a `PlanResult`:

- Zero or more `CandidatePlan`s with status `viable` / `uncertain` / `rejected` / `unsupported`
- Preferred least-invasive viable plan when one exists
- Explicit `execution_authorized=False` and empty `side_effects`
- Unresolved questions and recommended probes

Deterministic for identical profile + catalog version.

**Generating a plan never executes it.** Destructive strategies are rejected when bootloader is locked or unknown.

## Agent API

| Operation | Method | Path |
|-----------|--------|------|
| List operations | GET | `/v1/operations` (no auth) |
| Providers | GET | `/v1/discovery/providers` |
| Devices | GET | `/v1/discovery/devices` |
| Probes | GET | `/v1/discovery/devices/{provider}/{key}/probes` |
| Profile | POST | `/v1/discovery/profile` |
| Catalog | GET | `/v1/catalog/targets` |
| Plan | POST | `/v1/plan` |

Capabilities: `discover`, `plan` (granted by bootstrap enroll by default).

## Safety boundaries

| Action | Modifies device? | Requires authz to execute? |
|--------|------------------|----------------------------|
| Discovery / probes | No | N/A (read-only) |
| Planning | No | N/A |
| Future flash/install | Yes | Explicit authorization required |

Planning cannot trigger destructive operations. Missing evidence is treated conservatively (uncertain/rejected, never silent yes).

## Example

```bash
PYTHONPATH=src python examples/discover_and_plan.py
```

## Adding a mock device

Extend `MOCK_DEVICES` in `src/daemonos/discovery/mock.py` or construct `MockDiscoveryProvider(devices={...})` and register it.

## Limitations

- Only the `mock` provider is implemented; no real ADB/fastboot transport yet
- Catalog entries are synthetic fixtures
- No MCP server in this milestone (HTTP + Python library only)
- Planning does not download or execute firmware
