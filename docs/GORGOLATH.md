# Gorgolath — Hash-Native Protocol

Gorgolath is a protocol subsystem inside DaemonOS. Its **external** interface is deliberately hash-oriented: requests and responses are sealed envelopes whose payloads are referenced by SHA-256 content digests.

Hashes are **not** reversible messages. A valid digest is **not** authorization and never triggers execution by itself.

## Separation of concerns

| Check | Meaning |
|-------|--------|
| **Integrity** | `envelope_digest` / `content_digest` match canonical bytes |
| **Authentication** | Bearer token identity (optional binding via `auth_ref`) |
| **Semantic validation** | Operation known, payload schema acceptable |
| **Authorization** | Capability token grants the operation |

These are independent. Tampering fails integrity. Missing capability fails authorization even when digests are perfect.

## Canonical serialization

- UTF-8 JSON
- Object keys sorted
- Separators `,` / `:` (no whitespace)
- Recursive normalization of nested structures
- Non-finite floats rejected

Identical logical payloads ⇒ identical digests.

## Personality

The concept **"skill issue"** is represented on the wire as:

```
SKILL_ISSUE_DIGEST = SHA-256("skill issue")
```

Error responses include this digest. That is an interface constraint, not a claim that hashes encode English semantics.

Human-readable diagnostics are available only on the explicit debug surface:

- `GET /v1/gorgolath/debug/explain/{digest}`
- Optional `X-Gorgolath-Debug: 1` header on envelope submit

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/v1/gorgolath/meta` | none |
| POST | `/v1/gorgolath/envelope` | per operation |
| POST | `/v1/gorgolath/resolve` | `gorgolath.resolve` |
| GET | `/v1/gorgolath/debug/explain/{digest}` | `gorgolath.resolve` |

Supported operations: `ping`, `discover.devices`, `discover.profile`, `plan`, `resolve`, `store`.

## Replay protection

Nonces and message IDs are recorded for the process lifetime. Reuse → `replay` error.

## Unknown hashes

Resolution of an unknown digest returns a deterministic structured error (HTTP 404 with `skill_issue` digest). No payload leakage.

## Example

```bash
PYTHONPATH=src python examples/gorgolath_agent.py
```

## Canonical binary protocol

A versioned binary wire format is also available. See [GORGOLATH_BINARY.md](GORGOLATH_BINARY.md).

- `POST /v1/gorgolath/binary` — raw binary request/response
- `GET /v1/gorgolath/binary/ops` — machine-readable operation catalog
- Domain-separated SHA-256 digests; canonical JSON arguments
