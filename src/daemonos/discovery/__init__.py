"""Agent-native hardware discovery and capability profiling."""

from .evidence import EvidenceKind, Observation, ProbeResult, ProbeStatus
from .profile import DeviceCapabilityProfile, HardwareFacts, RuntimeFacts, ManagementInterface
from .provider import DiscoveryProvider, DiscoveryRegistry
from .service import DiscoveryService
from .mock import MockDiscoveryProvider

__all__ = [
    "EvidenceKind",
    "Observation",
    "ProbeResult",
    "ProbeStatus",
    "DeviceCapabilityProfile",
    "HardwareFacts",
    "RuntimeFacts",
    "ManagementInterface",
    "DiscoveryProvider",
    "DiscoveryRegistry",
    "DiscoveryService",
    "MockDiscoveryProvider",
]
