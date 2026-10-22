# Provisioning

## Installation (flash)

1. Discover devices via a `DeviceDiscovery` implementation.
2. Select a compatible `ImageManifest`.
3. Run `preflight()` — any issues abort.
4. Call `flash(..., dry_run=True)` by default.
5. Only with explicit `allow_destructive=True` perform real writes.

The **SimulatorFlashBackend** implements the full path for CI and local development without hardware.

## Enrollment

1. Device (or operator) submits `EnrollmentRequest` with serial and requested capabilities.
2. Operator / policy authorizes the node (`authorize`).
3. `complete_enrollment` issues a short-lived `CapabilityToken`.
4. Node is registered in fleet inventory with health=healthy.
5. Revocation invalidates tokens and marks the node quarantined.

Production must replace the in-memory store and open bootstrap endpoint with mutual authentication and an approval workflow.

## Updates and recovery

- Image version and checksum are part of the manifest.
- Recovery guidance is returned on failed flash results.
- Re-enrollment is supported by issuing a new request after revocation.

## Secrets

No production secrets are embedded. Tokens are ephemeral and revocable. Future: hardware-backed keys, encrypted secret store, rotation schedules.
