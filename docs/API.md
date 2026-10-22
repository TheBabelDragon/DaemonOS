# API Contracts (v1.1)

Base path: `/v1`

Authentication: `Authorization: Bearer <token_id>`

All responses are JSON. Errors use HTTP status codes with `{"detail": "..."}` bodies (FastAPI default).

## Endpoints implemented

### Self-description

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/operations` | none | Machine-readable list of operations and schemas |

### Discovery (read-only, never modifies devices)

| Method | Path | Auth | Capability |
|--------|------|------|------------|
| GET | `/v1/discovery/providers` | required | `discover` |
| GET | `/v1/discovery/devices` | required | `discover` |
| GET | `/v1/discovery/devices/{provider}/{device_key}/probes` | required | `discover` |
| POST | `/v1/discovery/profile` | required | `discover` |
| GET | `/v1/catalog/targets` | required | `discover` |

### Planning (never executes)

| Method | Path | Auth | Capability |
|--------|------|------|------------|
| POST | `/v1/plan` | required | `plan` |

Plan responses always include `execution_authorized: false` and `side_effects: []`.

### Fleet / tasks (existing)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/nodes` | required | List enrolled nodes |
| GET | `/v1/nodes/{id}` | required | Node record |
| GET | `/v1/nodes/{id}/capabilities` | required | Capability manifest |
| GET | `/v1/nodes/{id}/health` | required | Health snapshot |
| POST | `/v1/tasks` | required (`task.submit`) | Create + execute task (sim auto-runs) |
| GET | `/v1/tasks/{id}` | required | Task status and result |
| POST | `/v1/tasks/{id}/cancel` | required (`task.cancel`) | Cancel task |
| POST | `/v1/bootstrap/enroll` | **none (dev only)** | Enroll and issue token |

## Example bodies

### Discover profile

```json
{"provider": "mock", "device_key": "mock-pixel-like", "probe_ids": null}
```

### Plan

```json
{"provider": "mock", "device_key": "mock-pixel-like", "objective": "run_agent"}
```

### Task create

```json
{
  "capability": "echo",
  "parameters": {"message": "hello"},
  "idempotency_key": "optional-key",
  "max_retries": 0,
  "node_id": null
}
```

## Authorization rules

- Missing/invalid/expired/revoked token → 401
- Valid token lacking required capability → 403
- Default-deny: only capabilities present on the token are allowed
- Discovery and planning cannot escalate privileges

## Structured errors

| Status | Meaning |
|--------|--------|
| 401 | Authentication required or token invalid |
| 403 | Authorization denied (capability) |
| 404 | Node, task, provider, or device not found |
| 409 | Invalid lifecycle transition |

## Notes

- Bootstrap enroll is for local/sim development only.
- See [DISCOVERY.md](DISCOVERY.md) for evidence semantics and planner behavior.
