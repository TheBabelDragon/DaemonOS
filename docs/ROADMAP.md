# Roadmap

## Phase 0 — Repository and simulator vertical slice (this branch)

- [x] Repository, license, CI, docs
- [x] Core task/capability/auth/evidence contracts
- [x] Simulated enrollment, fleet, task execution
- [x] Flash dry-run and compatibility checks
- [x] Versioned API
- [x] Automated tests

## Phase 1 — Durable control plane

- Persistent task and enrollment store (SQLite/Postgres)
- Encrypted secret storage
- Proper queue / worker separation for task execution
- Disable or gate bootstrap enroll
- Metrics and structured logging

## Phase 2 — First real Android path

- Document one target device model end-to-end
- ADB/fastboot discovery backend
- Signed image verification pipeline
- Controlled physical dry-run then destructive flash on lab hardware only

## Phase 3 — Hardening and scale

- mTLS / device attestation
- Capability attenuation and delegation
- Quarantine automation and policy engine
- Multi-region control plane considerations
- Integration adapters (optional) toward Octopie / Aurora without core coupling

## Explicit non-goals for early phases

- Custom kernel or full Android fork
- LLM inside the trusted execution core
- Claiming production readiness from mocks
