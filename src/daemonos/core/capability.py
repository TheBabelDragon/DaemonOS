"""Machine-readable capability manifests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Capability(BaseModel):
    """A single named capability a node can expose."""

    name: str = Field(..., description="Canonical capability name, e.g. 'exec.shell' or 'flash.android'")
    version: str = Field("1.0", description="SemVer of the capability interface")
    description: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    requires_privilege: bool = False
    max_concurrent: int | None = None


class CapabilityManifest(BaseModel):
    """Versioned declaration of capabilities offered by a node."""

    node_id: str
    manifest_id: str = Field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    capabilities: list[Capability] = Field(default_factory=list)
    hardware_profile: str | None = None
    software_versions: dict[str, str] = Field(default_factory=dict)

    def has(self, name: str) -> bool:
        return any(c.name == name for c in self.capabilities)

    def get(self, name: str) -> Capability | None:
        for c in self.capabilities:
            if c.name == name:
                return c
        return None
