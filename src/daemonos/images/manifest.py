"""Versioned image manifests, checksums, and signature verification model.

Do not claim an image is reproducible, signed, or verified unless
the corresponding implementation and tests establish it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class CompatibilityConstraint(BaseModel):
    """Hardware / firmware constraint for an image."""

    device_models: list[str] = Field(default_factory=list)
    min_android_api: int | None = None
    max_android_api: int | None = None
    required_partitions: list[str] = Field(default_factory=list)
    bootloader_unlocked: bool | None = None
    notes: str = ""


class ImageSignature(BaseModel):
    """Cryptographic signature record (verification is explicit)."""

    algorithm: str  # e.g. "ed25519", "rsa-pss"
    public_key_id: str
    signature_b64: str
    signed_at: datetime | None = None
    verified: bool = False  # set only after successful verification


class ImageManifest(BaseModel):
    """Versioned device image description."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    device_family: str  # e.g. "android", "linux-x86_64", "simulator"
    checksum_sha256: str
    size_bytes: int
    url: str | None = None
    compatibility: CompatibilityConstraint = Field(default_factory=CompatibilityConstraint)
    signatures: list[ImageSignature] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    # provenance may include reproducible-build metadata when available

    def is_compatible(self, device_model: str, android_api: int | None = None) -> bool:
        c = self.compatibility
        if c.device_models and device_model not in c.device_models:
            return False
        if android_api is not None:
            if c.min_android_api is not None and android_api < c.min_android_api:
                return False
            if c.max_android_api is not None and android_api > c.max_android_api:
                return False
        return True

    def has_verified_signature(self) -> bool:
        return any(s.verified for s in self.signatures)
