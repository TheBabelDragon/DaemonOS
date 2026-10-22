# Security

Security is a foundational architectural constraint, not an add-on.

## Threat model (initial)

### Assets

- Device enrollment credentials and capability tokens
- Task payloads and execution evidence
- Image manifests and signing keys (future)
- Fleet inventory and health state

### Trust boundaries

1. **Public API ↔ Control plane** — All endpoints require authentication (Bearer token). Default-deny on capabilities.
2. **Control plane ↔ Device** — Devices receive only tasks they are authorized for; no unrestricted shell.
3. **Flash / provisioning path** — Destructive operations require explicit `allow_destructive=True`; dry-run is the default.
4. **Operator workstation ↔ CI** — No production secrets in repository; simulator uses ephemeral in-memory credentials.

### Adversaries (considered)

- Unauthenticated network client probing the API
- Stolen or expired capability token
- Malicious or compromised enrolled node
- Supply-chain tampering of device images (signature model present; full verification pipeline planned)
- Accidental destructive flash against wrong device

### Mitigations implemented in this milestone

| Control | Status |
|---------|--------|
| Default-deny capability checks | Implemented |
| Short-lived tokens with expiry + revocation | Implemented |
| Explicit task lifecycle (no silent success) | Implemented |
| Dry-run default for flash | Implemented |
| Destructive flash opt-in | Implemented |
| Compatibility rejection before flash | Implemented |
| Audit events for key actions | Implemented |
| No unrestricted remote shell in API | Implemented |

### Known limitations (not production-ready)

- In-memory token and task stores (no durable encrypted secret store)
- Bootstrap enroll endpoint is open for local/sim convenience — **must not** be exposed in production
- Signature verification model exists; cryptographic verify path is not fully wired
- No mTLS or device attestation yet
- No rate limiting or anomaly detection

## Assumptions

- Operators run the control plane on a trusted host for development.
- Simulated devices are not a substitute for hardware security evaluation.
- Physical Android flashing remains unclaimed until tested on documented hardware.

## Reporting

Open a private security advisory or contact the repository owner for sensitive issues.
