"""Evidence, observations, and probe results.

Distinguishes observed facts, inferences, and external claims.
Never treats an unobserved capability as verified.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceKind(str, Enum):
    """How a value was obtained."""

    OBSERVED = "observed"  # directly measured/read from device
    INFERRED = "inferred"  # derived from other observations
    EXTERNAL = "external"  # catalog, vendor docs, operator claim
    UNKNOWN = "unknown"


class ProbeStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"
    UNSUPPORTED = "unsupported"
    TIMEOUT = "timeout"
    CONFLICT = "conflict"


class Observation(BaseModel):
    """A single typed observation with provenance."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    field: str  # e.g. "manufacturer", "arch", "ram_mb"
    value: Any = None
    kind: EvidenceKind = EvidenceKind.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""  # provider name or method
    method: str = ""  # e.g. "adb.getprop", "sysfs", "mock"
    verified: bool = False
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class ProbeResult(BaseModel):
    """Outcome of running a single discovery probe."""

    probe_id: str
    status: ProbeStatus
    observations: list[Observation] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
