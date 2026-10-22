"""Simulator flash backend — no physical hardware required."""

from __future__ import annotations

from daemonos.images.manifest import ImageManifest
from .backends import FlashBackend, FlashResult, FlashStatus
from .discovery import DeviceDiscovery, DeviceInfo, DeviceState


class SimulatorDiscovery(DeviceDiscovery):
    """In-memory discovery of simulated devices."""

    def __init__(self) -> None:
        self._devices: dict[str, DeviceInfo] = {}

    def add(self, device: DeviceInfo) -> None:
        self._devices[device.serial] = device

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    def remove(self, serial: str) -> None:
        self._devices.pop(serial, None)


class SimulatorFlashBackend(FlashBackend):
    """Safe, deterministic flash path for tests and local development."""

    def name(self) -> str:
        return "simulator"

    def supports(self, device: DeviceInfo, image: ImageManifest) -> bool:
        if device.transport != "simulated":
            return False
        return image.is_compatible(device.model, device.android_api)

    def preflight(self, device: DeviceInfo, image: ImageManifest) -> list[str]:
        issues: list[str] = []
        if not self.supports(device, image):
            issues.append(f"image {image.name} not compatible with {device.model}")
        if device.state not in (DeviceState.DETECTED, DeviceState.FASTBOOT, DeviceState.BOOTLOADER):
            issues.append(f"device state {device.state.value} not ready for flash")
        if not image.checksum_sha256:
            issues.append("image missing checksum")
        return issues

    def flash(
        self,
        device: DeviceInfo,
        image: ImageManifest,
        *,
        dry_run: bool = True,
        allow_destructive: bool = False,
    ) -> FlashResult:
        steps: list[str] = []
        issues = self.preflight(device, image)
        if issues:
            return FlashResult(
                status=FlashStatus.FAILED,
                device_serial=device.serial,
                image_id=image.id,
                dry_run=dry_run,
                steps=steps,
                error="; ".join(issues),
                recovery_guidance="Fix compatibility or device state and retry.",
            )

        steps.append("preflight ok")
        steps.append(f"selected image {image.name}@{image.version}")
        steps.append(f"checksum {image.checksum_sha256[:16]}...")

        if dry_run:
            steps.append("dry-run: no writes performed")
            return FlashResult(
                status=FlashStatus.DRY_RUN,
                device_serial=device.serial,
                image_id=image.id,
                dry_run=True,
                steps=steps,
                progress_pct=100,
            )

        if not allow_destructive:
            return FlashResult(
                status=FlashStatus.ABORTED,
                device_serial=device.serial,
                image_id=image.id,
                dry_run=False,
                steps=steps,
                error="destructive flash requires allow_destructive=True",
                recovery_guidance="Re-run with allow_destructive=True only after review.",
            )

        # Simulated write path
        steps.append("erase partition (simulated)")
        steps.append("write image (simulated)")
        steps.append("verify checksum (simulated)")
        steps.append("reboot (simulated)")

        return FlashResult(
            status=FlashStatus.SUCCEEDED,
            device_serial=device.serial,
            image_id=image.id,
            dry_run=False,
            steps=steps,
            progress_pct=100,
        )
