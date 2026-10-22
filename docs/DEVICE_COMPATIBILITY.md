# Device Compatibility Registry

## Design

Compatibility is expressed on **image manifests**, not hard-coded in the core runtime.

```python
CompatibilityConstraint(
    device_models=["sim-phone-a", "pixel-6"],
    min_android_api=30,
    max_android_api=34,
    required_partitions=["boot", "system"],
    bootloader_unlocked=True,
)
```

An image is accepted for a device only when `ImageManifest.is_compatible(model, android_api)` returns true.

## Staged deployment strategy

1. **Simulator** — no physical hardware; transport=`simulated` (implemented).
2. **Linux development environment** — core runtime and controller on x86_64/aarch64 Linux (controller side implemented).
3. **One explicitly selected Android model** — documented later with exact unlock, fastboot, and partition assumptions.
4. **Additional families** — via new compatibility profiles and installation adapters.

## Non-goals (initial)

- Universal Android compatibility claims
- Treating a generic Linux runtime as a substitute for Android application compatibility
- Embedding device-specific kernel/firmware/driver assumptions in the portable core

## Registry evolution

Future work: persistent registry (DB or signed JSON), automatic discovery of model/API from ADB/fastboot, and per-backend capability flags.
