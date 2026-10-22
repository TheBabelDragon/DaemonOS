"""Pluggable installation backends with dry-run and safeguards.

Never assume all Android devices support the same flashing mechanism.
Do not issue destructive commands to real devices by default.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from daemonos.images.manifest import ImageManifest
from .discovery import DeviceInfo


class FlashStatus(str, Enum):
    PENDING = "pending"
    PREFLIGHT = "preflight"
    DRY_RUN = "dry_run"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"


class FlashResult(BaseModel):
    status: FlashStatus
    device_serial: str
    image_id: str | None = None
    dry_run: bool = True
    steps: list[str] = Field(default_factory=list)
    error: str | None = None
    recovery_guidance: str | None = None
    progress_pct: int = 0


class FlashBackend(ABC):
    """Installation backend. Destructive operations require explicit opt-in."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def supports(self, device: DeviceInfo, image: ImageManifest) -> bool:
        ...

    @abstractmethod
    def preflight(self, device: DeviceInfo, image: ImageManifest) -> list[str]:
        """Return list of preflight warnings/errors. Empty means ok."""
        ...

    @abstractmethod
    def flash(
        self,
        device: DeviceInfo,
        image: ImageManifest,
        *,
        dry_run: bool = True,
        allow_destructive: bool = False,
    ) -> FlashResult:
        """Perform (or simulate) installation.

        dry_run=True by default. allow_destructive must be True for real writes.
        """
        ...
