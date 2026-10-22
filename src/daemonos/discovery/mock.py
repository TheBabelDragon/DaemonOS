"""Deterministic mock discovery provider for tests and local demos.

No physical hardware, no root, no network side effects.
"""

from __future__ import annotations

from typing import Any

from .evidence import EvidenceKind, Observation, ProbeResult, ProbeStatus
from .provider import DiscoveryProvider, ProbeDescriptor


# Synthetic device fixtures (explicitly labeled synthetic)
MOCK_DEVICES: dict[str, dict[str, Any]] = {
    "mock-pixel-like": {
        "manufacturer": "SyntheticCo",
        "model": "SynthPhone X",
        "model_id": "synth_x_2024",
        "serial": "MOCKSERIAL001",
        "arch": "arm64",
        "cpu_cores": 8,
        "ram_mb": 6144,
        "storage_mb": 128000,
        "features": ["neon", "aes"],
        "os_family": "android",
        "os_version": "14",
        "os_build": "SYNTH.240101.001",
        "android_api": 34,
        "bootloader_state": "locked",
        "kernel": "5.15.synthetic",
        "management_interface": {
            "name": "adb",
            "available": True,
            "requires_auth": True,
            "requires_root": False,
            "read_only_safe": True,
            "notes": "synthetic adb transport",
        },
    },
    "mock-unknown": {
        "serial": "UNKNOWNDEV",
        # intentionally sparse — partial identification
    },
    "mock-linux-dev": {
        "manufacturer": "SyntheticCo",
        "model": "SynthBoard",
        "serial": "MOCKLINUX01",
        "arch": "x86_64",
        "cpu_cores": 4,
        "ram_mb": 8192,
        "storage_mb": 256000,
        "os_family": "linux",
        "os_version": "6.6",
        "kernel": "6.6.0-synth",
        "management_interface": {
            "name": "ssh",
            "available": True,
            "requires_auth": True,
            "requires_root": False,
            "read_only_safe": True,
        },
    },
    "mock-conflict": {
        "manufacturer": "SyntheticCo",
        "model": "ConflictPhone",
        "serial": "MOCKCONFLICT",
        "arch": "arm64",
        "os_family": "android",
        "android_api": 30,
        "_conflict_arch": "x86_64",  # second probe reports different arch
    },
}


class MockDiscoveryProvider(DiscoveryProvider):
    """In-memory provider with configurable synthetic devices."""

    def __init__(self, devices: dict[str, dict[str, Any]] | None = None) -> None:
        self._devices = dict(devices) if devices is not None else dict(MOCK_DEVICES)

    def name(self) -> str:
        return "mock"

    def list_devices(self) -> list[str]:
        return sorted(self._devices.keys())

    def available_probes(self, device_key: str) -> list[ProbeDescriptor]:
        if device_key not in self._devices:
            return []
        return [
            ProbeDescriptor(
                id="probe.identity",
                name="Identity",
                description="Read manufacturer, model, serial",
                read_only=True,
            ),
            ProbeDescriptor(
                id="probe.arch",
                name="Architecture",
                description="Read CPU architecture",
                read_only=True,
            ),
            ProbeDescriptor(
                id="probe.memory",
                name="Memory/Storage",
                description="Read RAM and storage capacity",
                read_only=True,
            ),
            ProbeDescriptor(
                id="probe.os",
                name="Operating System",
                description="Read OS family, version, API level",
                read_only=True,
            ),
            ProbeDescriptor(
                id="probe.bootloader",
                name="Bootloader",
                description="Read bootloader lock state if available",
                read_only=True,
            ),
            ProbeDescriptor(
                id="probe.interfaces",
                name="Management Interfaces",
                description="Enumerate management transports",
                read_only=True,
            ),
            ProbeDescriptor(
                id="probe.root_only",
                name="Root-only probe",
                description="Requires root — always denied on mock",
                read_only=True,
                requires_root=True,
            ),
        ]

    def run_probe(self, device_key: str, probe_id: str) -> ProbeResult:
        if device_key not in self._devices:
            return ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.FAILED,
                error=f"unknown device {device_key}",
            )

        data = self._devices[device_key]

        if probe_id == "probe.root_only":
            return ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.PERMISSION_DENIED,
                error="root required; mock provider never elevates",
            )

        if probe_id == "probe.identity":
            return self._obs_probe(
                probe_id,
                data,
                ["manufacturer", "model", "model_id", "serial", "hardware_revision"],
            )

        if probe_id == "probe.arch":
            obs = []
            if "arch" in data:
                obs.append(
                    Observation(
                        field="arch",
                        value=data["arch"],
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.95,
                        source="mock",
                        method="mock.arch",
                        verified=True,
                    )
                )
            # conflict fixture: second observation differs
            if "_conflict_arch" in data:
                obs.append(
                    Observation(
                        field="arch",
                        value=data["_conflict_arch"],
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.5,
                        source="mock",
                        method="mock.arch.secondary",
                        verified=False,
                        notes="conflicting architecture report",
                    )
                )
                return ProbeResult(
                    probe_id=probe_id,
                    status=ProbeStatus.CONFLICT,
                    observations=obs,
                    error="conflicting architecture observations",
                )
            if not obs:
                return ProbeResult(
                    probe_id=probe_id,
                    status=ProbeStatus.UNSUPPORTED,
                    error="architecture not available",
                )
            if "cpu_cores" in data:
                obs.append(
                    Observation(
                        field="cpu_cores",
                        value=data["cpu_cores"],
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.9,
                        source="mock",
                        method="mock.cpu",
                        verified=True,
                    )
                )
            if "features" in data:
                obs.append(
                    Observation(
                        field="features",
                        value=data["features"],
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.85,
                        source="mock",
                        method="mock.features",
                        verified=True,
                    )
                )
            return ProbeResult(probe_id=probe_id, status=ProbeStatus.OK, observations=obs)

        if probe_id == "probe.memory":
            return self._obs_probe(probe_id, data, ["ram_mb", "storage_mb"])

        if probe_id == "probe.os":
            return self._obs_probe(
                probe_id,
                data,
                ["os_family", "os_version", "os_build", "android_api", "kernel", "firmware_id"],
            )

        if probe_id == "probe.bootloader":
            if "bootloader_state" not in data:
                return ProbeResult(
                    probe_id=probe_id,
                    status=ProbeStatus.UNSUPPORTED,
                    error="bootloader state not detectable",
                )
            return self._obs_probe(probe_id, data, ["bootloader_state"])

        if probe_id == "probe.interfaces":
            if "management_interface" in data:
                obs = [
                    Observation(
                        field="management_interface",
                        value=data["management_interface"],
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.95,
                        source="mock",
                        method="mock.iface",
                        verified=True,
                    )
                ]
                return ProbeResult(probe_id=probe_id, status=ProbeStatus.OK, observations=obs)
            return ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.UNSUPPORTED,
                error="no management interface advertised",
            )

        return ProbeResult(
            probe_id=probe_id,
            status=ProbeStatus.UNSUPPORTED,
            error=f"unknown probe {probe_id}",
        )

    def _obs_probe(
        self, probe_id: str, data: dict[str, Any], fields: list[str]
    ) -> ProbeResult:
        obs: list[Observation] = []
        for f in fields:
            if f in data and data[f] is not None:
                obs.append(
                    Observation(
                        field=f,
                        value=data[f],
                        kind=EvidenceKind.OBSERVED,
                        confidence=0.9,
                        source="mock",
                        method=f"mock.{probe_id}",
                        verified=True,
                    )
                )
        if not obs:
            return ProbeResult(
                probe_id=probe_id,
                status=ProbeStatus.UNSUPPORTED,
                error="no data for requested fields",
            )
        return ProbeResult(probe_id=probe_id, status=ProbeStatus.OK, observations=obs)
