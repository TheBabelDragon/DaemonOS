"""Extensible discovery providers. Core model stays stable when providers are added."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from .evidence import ProbeResult
from .profile import DeviceCapabilityProfile


class ProbeDescriptor(BaseModel):
    """Machine-readable description of a probe."""

    id: str
    name: str
    description: str = ""
    read_only: bool = True
    requires_root: bool = False
    requires_interface: str | None = None  # e.g. "adb"
    prerequisites: list[str] = Field(default_factory=list)


class DiscoveryProvider(ABC):
    """Provider that can list devices and run probes."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def list_devices(self) -> list[str]:
        """Return device keys (serials or mock ids) currently visible."""
        ...

    @abstractmethod
    def available_probes(self, device_key: str) -> list[ProbeDescriptor]:
        ...

    @abstractmethod
    def run_probe(self, device_key: str, probe_id: str) -> ProbeResult:
        """Execute a single read-only probe. Must not modify device state."""
        ...

    def build_profile(self, device_key: str, probe_results: list[ProbeResult]) -> DeviceCapabilityProfile:
        """Assemble a profile from probe results. Override for provider-specific mapping."""
        from .profile import (
            DeviceCapabilityProfile,
            HardwareFacts,
            RuntimeFacts,
            IdentificationConfidence,
            ManagementInterface,
        )
        from .evidence import EvidenceKind

        observations = []
        for pr in probe_results:
            observations.extend(pr.observations)

        hw = HardwareFacts()
        rt = RuntimeFacts()
        interfaces: list[ManagementInterface] = []
        capabilities: list[str] = []
        constraints: list[str] = []
        unresolved: list[str] = []
        recommended: list[str] = []

        field_map_hw = {
            "manufacturer": "manufacturer",
            "model": "model",
            "model_id": "model_id",
            "hardware_revision": "hardware_revision",
            "serial": "serial",
            "arch": "arch",
            "cpu_cores": "cpu_cores",
            "ram_mb": "ram_mb",
            "storage_mb": "storage_mb",
        }
        field_map_rt = {
            "os_family": "os_family",
            "os_version": "os_version",
            "os_build": "os_build",
            "firmware_id": "firmware_id",
            "android_api": "android_api",
            "bootloader_state": "bootloader_state",
            "kernel": "kernel",
        }

        best: dict[str, tuple[float, Any]] = {}
        for obs in observations:
            prev = best.get(obs.field)
            if prev is None or obs.confidence > prev[0]:
                best[obs.field] = (obs.confidence, obs.value)

        for field, attr in field_map_hw.items():
            if field in best:
                setattr(hw, attr, best[field][1])
        for field, attr in field_map_rt.items():
            if field in best:
                setattr(rt, attr, best[field][1])

        if "features" in best and isinstance(best["features"][1], list):
            hw.features = list(best["features"][1])

        # Interfaces from observations
        for obs in observations:
            if obs.field == "management_interface" and isinstance(obs.value, dict):
                interfaces.append(ManagementInterface(**obs.value))

        if not interfaces:
            # default simulated interface if provider is mock-like
            interfaces.append(
                ManagementInterface(name=self.name(), available=True, read_only_safe=True)
            )

        # Confidence heuristic
        observed_count = sum(1 for o in observations if o.kind == EvidenceKind.OBSERVED)
        if observed_count >= 5 and hw.model and hw.arch:
            confidence = IdentificationConfidence.HIGH
        elif observed_count >= 2:
            confidence = IdentificationConfidence.MEDIUM
        elif observed_count >= 1:
            confidence = IdentificationConfidence.LOW
        else:
            confidence = IdentificationConfidence.UNKNOWN

        if not hw.arch:
            unresolved.append("architecture unknown")
            recommended.append("probe.arch")
        if not rt.os_family:
            unresolved.append("os_family unknown")
            recommended.append("probe.os")
        if rt.os_family == "android" and rt.bootloader_state is None:
            unresolved.append("bootloader_state unknown")
            recommended.append("probe.bootloader")

        if hw.arch:
            capabilities.append(f"arch:{hw.arch}")
        if rt.os_family:
            capabilities.append(f"os:{rt.os_family}")

        supported_ops = ["discover", "profile", "plan"]
        if any(i.name == "adb" and i.available for i in interfaces):
            supported_ops.append("adb_readonly")

        return DeviceCapabilityProfile(
            device_key=device_key,
            identification_confidence=confidence,
            hardware=hw,
            runtime=rt,
            management_interfaces=interfaces,
            capabilities=capabilities,
            constraints=constraints,
            observations=observations,
            unresolved_questions=unresolved,
            recommended_probes=recommended,
            supported_operations=supported_ops,
        )


class DiscoveryRegistry:
    """Register and look up discovery providers."""

    def __init__(self) -> None:
        self._providers: dict[str, DiscoveryProvider] = {}

    def register(self, provider: DiscoveryProvider) -> None:
        self._providers[provider.name()] = provider

    def get(self, name: str) -> DiscoveryProvider | None:
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def all_devices(self) -> list[tuple[str, str]]:
        """Return (provider_name, device_key) pairs."""
        out: list[tuple[str, str]] = []
        for name, p in self._providers.items():
            for key in p.list_devices():
                out.append((name, key))
        return out
