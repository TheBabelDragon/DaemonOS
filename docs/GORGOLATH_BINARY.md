# Gorgolath Canonical Binary Protocol

Wire-protocol version **1**. Complements the existing JSON hash-oriented surface.

## Design principles

| Check | Meaning |
|-------|--------|
| **Integrity** | `payload_digest` matches SHA-256 of content region |
| **Authentication** | Optional Bearer / integrity_metadata binding |
| **Semantic validation** | Operation known; arguments match schema |
| **Authorization** | Capability token grants the operation |

These are independent. A valid digest is **never** authorization and never triggers execution by itself.

## Wire format

All multi-byte integers are **big-endian**.

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | magic = `GORG` (`47 4F 52 47`) |
| 4 | 2 | `protocol_version` (uint16) — currently `1` |
| 6 | 1 | `message_type` (1=request, 2=response, 3=event, 4=error) |
| 7 | 1 | `flags` (bit0 = has integrity_metadata) |
| 8 | 16 | `request_id` (UUID bytes) |
| 24 | 2 | `operation_len` (uint16) |
| 26 | N | `operation` (UTF-8) |
| 26+N | 4 | `arguments_len` (uint32) |
| … | M | `arguments` (canonical JSON UTF-8) |
| … | 32 | `payload_digest` (SHA-256) |
| … | 4 | `integrity_len` (uint32, 0 if absent) |
| … | K | `integrity_metadata` (optional) |

### Canonical arguments

Arguments use the same deterministic JSON rules as the JSON surface:

- UTF-8
- Object keys sorted
- Separators `,` / `:` (no whitespace)
- Non-finite floats rejected

On decode, arguments are re-serialized; if the result differs from the wire bytes, the message is **rejected as noncanonical**.

### Digest coverage and algorithm

```
content_region = bytes from magic through end of arguments (inclusive)
payload_digest = SHA-256( b"gorgolath-v1\0" || content_region )
```

Domain separation string: `gorgolath-v1` + NUL. Digest length: 32 bytes.
Identical semantic messages under the same protocol version produce identical
canonical bytes and digests.

Optional `integrity_metadata` is **outside** digest coverage (it authenticates
the already-digested message). Algorithm IDs: `0` none, `1` Ed25519, `2` HMAC-SHA256.

## Runtime pipeline

1. Parse / structural validity
2. Payload digest verification
3. Protocol version negotiation
4. Schema / argument validation
5. Replay protection (`request_id` uniqueness for process lifetime)
6. Authorization (capability token)
7. Dispatch

Structured deterministic errors use `message_type=ERROR` with fields
`code`, `detail`, `skill_issue`, `error_digest`.

## Registered operations

| Operation | Auth | Read-only |
|-----------|------|-----------|
| `ping` | none | yes |
| `ops.list` | none | yes |
| `ops.permissions` | none | yes |
| `discover.devices` | `discover` | yes |
| `discover.profile` | `discover` | yes |
| `plan` | `plan` | yes |
| `task.submit` | `task.submit` | no |
| `task.status` | `task.submit` | yes |
| `evidence.get` | `gorgolath.resolve` | yes |
| `resolve` | `gorgolath.resolve` | yes |
| `store` | `gorgolath.store` | no |

Unknown operations → `unsupported_operation`.
Backends not wired → explicit `{ "unsupported": true, ... }` result (not simulated success).

Discovery document: `GET /v1/gorgolath/binary/ops`.

## Evidence records

Each significant operation can produce a sealed evidence record:

- `evidence_id`, `protocol_version`, `operation`
- `device_id` / `task_id` when applicable
- `input_digest`, `config_digest`, `result_digest`
- `parent_digests` (chain links)
- `provenance`, `timestamp`
- `record_digest` = SHA-256 of canonical JSON of the above fields (excluding itself)

Verification detects modified records and broken parent links. Missing
referenced content is reported as a limitation; verification does not claim
success when parents are unavailable.

A hash does **not** prove device identity, result correctness, or authorization.

## HTTP endpoints

| Method | Path | Body |
|--------|------|------|
| GET | `/v1/gorgolath/meta` | — |
| GET | `/v1/gorgolath/binary/ops` | — |
| POST | `/v1/gorgolath/binary` | raw binary (`application/octet-stream`) |
| POST | `/v1/gorgolath/envelope` | JSON envelope (existing) |
| POST | `/v1/gorgolath/resolve` | `{ "digest": "..." }` |
| GET | `/v1/gorgolath/debug/explain/{digest}` | debug only |

## Security

- Never execute before parse, digest verify, schema validate, and authorize.
- Keep integrity, authentication, authorization, and semantic validation separate.
- Do not expose secrets through public hash lookups.
- Protect against replay, malformed inputs, and ambiguous encodings.
- Never execute instructions embedded in untrusted payloads merely because they are correctly hashed.
- Clients cannot elevate their own permissions.
- Key material is never hard-coded; signature verification is opt-in via integrity_metadata.

## Python API

```python
from daemonos.gorgolath import (
    encode_message, decode_message, MessageType,
    BinaryGorgolathRuntime,
)

req = encode_message(
    message_type=MessageType.REQUEST,
    request_id="...",
    operation="ping",
    arguments={},
)
rt = BinaryGorgolathRuntime()
resp = rt.handle_binary(req)
print(decode_message(resp))
```

See `examples/gorgolath_binary_demo.py` and `tests/test_gorgolath_binary.py`.
