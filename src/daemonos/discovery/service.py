"""Discovery service: list devices, run probes, build profiles.

Discovery is always read-only. It never modifies device state.
"""

from __future__ import annotations

from .profile import DeviceCapabilityProfile
from .provider import DiscoveryRegistry, ProbeDescriptor
from .evidence import ProbeResult
from .mock import MockDiscoveryProvider


class DiscoveryService:
    """Facade over registered discovery providers."""

    def __init__(self, registry: DiscoveryRegistry | None = None) -> None:
        self.registry = registry or DiscoveryRegistry()
        if not self.registry.list_providers():
            self.registry.register(MockDiscoveryProvider())

    def list_providers(self) -> list[str]:
        return self.registry.list_providers()

    def list_devices(self) -> list[dict[str, str]]:
        return [
            {"provider": prov, "device_key": key}
            for prov, key in self.registry.all_devices()
        ]

    def list_probes(self, provider: str, device_key: str) -> list[ProbeDescriptor]:
        p = self.registry.get(provider)
        if p is None:
            raise KeyError(f"unknown provider {provider}")
        return p.available_probes(device_key)

    def run_probe(self, provider: str, device_key: str, probe_id: str) -> ProbeResult:
        p = self.registry.get(provider)
        if p is None:
            raise KeyError(f"unknown provider {provider}")
        return p.run_probe(device_key, probe_id)

    def discover(
        self,
        provider: str,
        device_key: str,
        probe_ids: list[str] | None = None,
    ) -> DeviceCapabilityProfile:
        """Run probes and assemble a capability profile. Read-only."""
        p = self.registry.get(provider)
        if p is None:
            raise KeyError(f"unknown provider {provider}")

        if probe_ids is None:
            # default: all non-root probes
            probe_ids = [
                d.id
                for d in p.available_probes(device_key)
                if not d.requires_root
            ]

        results: list[ProbeResult] = []
        for pid in probe_ids:
            results.append(p.run_probe(device_key, pid))

        return p.build_profile(device_key, results)
