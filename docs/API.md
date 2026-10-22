# API Contracts (v1)

Base path: `/v1`

Authentication: `Authorization: Bearer <token_id>`

All responses are JSON. Errors use HTTP status codes with `{"detail": "..."}` bodies (FastAPI default).

## Endpoints implemented

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/nodes` | required | List enrolled nodes |
| GET | `/v1/nodes/{id}` | required | Node record |
| GET | `/v1/nodes/{id}/capabilities` | required | Capability manifest |
| GET | `/v1/nodes/{id}/health` | required | Health snapshot |
| POST | `/v1/tasks` | required (`task.submit`) | Create + execute task (sim auto-runs) |
| GET | `/v1/tasks/{id}` | required | Task status and result |
| POST | `/v1/tasks/{id}/cancel` | required (`task.cancel`) | Cancel task |
| POST | `/v1/bootstrap/enroll` | **none (dev only)** | Enroll simulated node and issue token |

## Task create body

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

## Structured errors

| Status | Meaning |
|--------|--------|
| 401 | Authentication required or token invalid |
| 403 | Authorization denied (capability) |
| 404 | Node or task not found |
| 409 | Invalid lifecycle transition |

## Notes

- The bootstrap enroll endpoint exists solely for local/sim development and **must be disabled or gated** in any shared or production deployment.
- Task submission currently auto-runs via the simulated executor for the vertical-slice demo; a future queue worker will decouple accept from execute.
