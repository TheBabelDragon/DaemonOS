"""Tests for image compatibility, flash dry-runs, and enrollment."""

from daemonos.flash.discovery import DeviceInfo, DeviceState
from daemonos.flash.simulator import SimulatorDiscovery, SimulatorFlashBackend
from daemonos.flash.backends import FlashStatus
from daemonos.images.manifest import ImageManifest, CompatibilityConstraint
from daemonos.provision.enrollment import EnrollmentService, EnrollmentRequest, EnrollmentState


def test_image_compatibility():
    img = ImageManifest(
        name="sim-image",
        version="1.0",
        device_family="simulator",
        checksum_sha256="a" * 64,
        size_bytes=1024,
        compatibility=CompatibilityConstraint(device_models=["sim-phone-a"]),
    )
    assert img.is_compatible("sim-phone-a")
    assert not img.is_compatible("other-model")


def test_flash_dry_run_succeeds():
    discovery = SimulatorDiscovery()
    device = DeviceInfo(
        serial="SIM001",
        model="sim-phone-a",
        state=DeviceState.FASTBOOT,
        transport="simulated",
    )
    discovery.add(device)
    backend = SimulatorFlashBackend()
    img = ImageManifest(
        name="sim-image",
        version="1.0",
        device_family="simulator",
        checksum_sha256="b" * 64,
        size_bytes=2048,
        compatibility=CompatibilityConstraint(device_models=["sim-phone-a"]),
    )
    assert backend.supports(device, img)
    result = backend.flash(device, img, dry_run=True)
    assert result.status == FlashStatus.DRY_RUN
    assert result.dry_run is True
    assert "dry-run" in " ".join(result.steps).lower()


def test_flash_rejects_incompatible():
    device = DeviceInfo(serial="SIM002", model="wrong", state=DeviceState.FASTBOOT, transport="simulated")
    backend = SimulatorFlashBackend()
    img = ImageManifest(
        name="sim-image",
        version="1.0",
        device_family="simulator",
        checksum_sha256="c" * 64,
        size_bytes=1024,
        compatibility=CompatibilityConstraint(device_models=["sim-phone-a"]),
    )
    result = backend.flash(device, img, dry_run=True)
    assert result.status == FlashStatus.FAILED
    assert "not compatible" in (result.error or "")


def test_destructive_requires_flag():
    device = DeviceInfo(serial="SIM003", model="sim-phone-a", state=DeviceState.FASTBOOT, transport="simulated")
    backend = SimulatorFlashBackend()
    img = ImageManifest(
        name="sim-image",
        version="1.0",
        device_family="simulator",
        checksum_sha256="d" * 64,
        size_bytes=1024,
        compatibility=CompatibilityConstraint(device_models=["sim-phone-a"]),
    )
    result = backend.flash(device, img, dry_run=False, allow_destructive=False)
    assert result.status == FlashStatus.ABORTED


def test_enrollment_lifecycle():
    svc = EnrollmentService(credential_ttl_seconds=60)
    req = EnrollmentRequest(device_serial="DEV1", requested_capabilities=["task.execute"])
    identity = svc.request_enrollment(req)
    assert identity.state == EnrollmentState.PENDING
    svc.authorize(identity.node_id, ["task.execute", "node.report"])
    node, token = svc.complete_enrollment(identity.node_id)
    assert node.state == EnrollmentState.ENROLLED
    assert token.is_valid()
    assert token.grants("task.execute")
    svc.revoke(identity.node_id)
    assert svc.get_node(identity.node_id).state == EnrollmentState.REVOKED
    assert not token.is_valid()
