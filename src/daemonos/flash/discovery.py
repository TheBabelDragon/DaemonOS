"""Device discovery interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DeviceState(str, Enum):
    UNKNOWN = "unknown"
    DETECTED = "detected"
    BOOTLOADER = "bootloader"
    FASTBOOT = "fastboot"
    ADB = "adb"
    RECOVERY = "recovery"
    OFFLINE = "offline"


class DeviceInfo(BaseModel):
    """Discovered device descriptor."""

    serial: str
    model: str = "unknown"
    manufacturer: str = "unknown"
    state: DeviceState = DeviceState.UNKNOWN
    transport: str = "simulated"  # usb, network, simulated
    android_api: int | None = None
    product: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DeviceDiscovery(ABC):
    """Pluggable device discovery."""

    @abstractmethod
    def list_devices(self) -> list[DeviceInfo]:
        ...

    def get(self, serial: str) -> DeviceInfo | None:
        for d in self.list_devices():
            if d.serial == serial:
                return d
        return None
