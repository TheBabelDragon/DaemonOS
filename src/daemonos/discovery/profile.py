"""Versioned, machine-readable device capability profile.

Designed so an external LLM or agent can interpret device state
without prior knowledge of DaemonOS internals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .evidence import Observation

SCHEMA_VERSION = "1.0"


class IdentificationConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ManagementInterface(BaseModel):
    """Available management / transport interface."""

    name: str  # e.g. "adb", "fastboot", "ssh", "simulated"
    available: bool = False
    requires_auth: bool = False
    requires_root: bool = False
    read_only_safe: bool = True
    notes: str = ""


class HardwareFacts(BaseModel):
    """Hardware attributes; all fields optional / unknown-safe."""

    manufacturer: str | None = None
    model: str | None = None
    model_id: str | None = None
    hardware_revision: str | None = None
    serial: str | None = None
    arch: str | None = None  # e.g. arm64, x86_64
    cpu_cores: int | None = None
    ram_mb: int | None = None
    storage_mb: int | None = None
    features: list[str] = Field(default_factory=list)


class RuntimeFacts(BaseModel):
    """OS / firmware runtime attributes."""

    os_family: str | None = None  # android, linux, unknown
    os_version: str | None = None
    os_build: str | None = None
    firmware_id: str | None = None
    android_api: int | None = None
    bootloader_state: str | None = None  # locked, unlocked, unknown
    kernel: str | None = None


class CompatibilityFinding(BaseModel):
    """A single compatibility evaluation result."""

    target_id: str
    status: str  # compatible, incompatible, indeterminate
    reasons: list[str] = Field(default_factory=list)
    missing_prerequisites: list[str] = Field(default_factory=list)


class DeviceCapabilityProfile(BaseModel):
    """Canonical versioned capability profile for one device."""

    schema_version: str = SCHEMA_VERSION
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    device_key: str  # stable key used by discovery (often serial or mock id)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    identification_confidence: IdentificationConfidence = IdentificationConfidence.UNKNOWN
    hardware: HardwareFacts = Field(default_factory=HardwareFacts)
    runtime: RuntimeFacts = Field(default_factory=RuntimeFacts)

    management_interfaces: list[ManagementInterface] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)  # positive known capabilities
    constraints: list[str] = Field(default_factory=list)  # known limitations
    unavailable: list[str] = Field(default_factory=list)

    observations: list[Observation] = Field(default_factory=list)
    compatibility: list[CompatibilityFinding] = Field(default_factory=list)

    unresolved_questions: list[str] = Field(default_factory=list)
    recommended_probes: list[str] = Field(default_factory=list)

    # Supported operations (what can be done *with current evidence*)
    supported_operations: list[str] = Field(default_factory=list)
    operation_prerequisites: dict[str, list[str]] = Field(default_factory=dict)

    extra: dict[str, Any] = Field(default_factory=dict)

    def has_interface(self, name: str) -> bool:
        return any(i.name == name and i.available for i in self.management_interfaces)

    def observed_value(self, field: str) -> Any:
        for obs in self.observations:
            if obs.field == field and obs.kind.value == "observed" and obs.verified:
                return obs.value
        for obs in self.observations:
            if obs.field == field:
                return obs.value
        return None
