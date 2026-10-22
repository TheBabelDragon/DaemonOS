"""Versioned compatibility catalog models.

Synthetic fixtures are labeled. Missing evidence never becomes a positive claim.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    SYNTHETIC = "synthetic"  # test fixture only
    LAB_VERIFIED = "lab_verified"
    VENDOR_DOC = "vendor_doc"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"


class RuntimeTarget(BaseModel):
    """A runtime or OS image a device might run."""

    id: str
    name: str
    kind: str  # agent_on_existing_os | alternative_image | linux_native
    arch_requirements: list[str] = Field(default_factory=list)
    os_families: list[str] = Field(default_factory=list)
    min_android_api: int | None = None
    max_android_api: int | None = None
    min_ram_mb: int | None = None
    requires_unlocked_bootloader: bool = False
    requires_root: bool = False
    description: str = ""


class DeploymentStrategy(BaseModel):
    """A known installation / deployment strategy."""

    id: str
    name: str
    target_id: str
    invasiveness: str  # none | low | medium | high | destructive
    requires_authorization: bool = True
    prerequisites: list[str] = Field(default_factory=list)
    steps_summary: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNVERIFIED
    evidence_notes: str = ""


class DeviceFamilyProfile(BaseModel):
    """Optional curated hints for a device family."""

    id: str
    match_models: list[str] = Field(default_factory=list)
    match_model_ids: list[str] = Field(default_factory=list)
    known_compatible_targets: list[str] = Field(default_factory=list)
    known_incompatible_targets: list[str] = Field(default_factory=list)
    notes: str = ""
    verification: VerificationStatus = VerificationStatus.UNVERIFIED


class CompatibilityCatalog(BaseModel):
    """Versioned catalog of targets, strategies, and family hints."""

    catalog_version: str = "1.0"
    schema_version: str = "1.0"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance: str = "builtin-synthetic"
    targets: list[RuntimeTarget] = Field(default_factory=list)
    strategies: list[DeploymentStrategy] = Field(default_factory=list)
    device_families: list[DeviceFamilyProfile] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def target_by_id(self, target_id: str) -> RuntimeTarget | None:
        for t in self.targets:
            if t.id == target_id:
                return t
        return None

    def strategies_for_target(self, target_id: str) -> list[DeploymentStrategy]:
        return [s for s in self.strategies if s.target_id == target_id]
