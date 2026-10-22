"""Tests for hardware discovery, capability profiles, and deployment planner."""

import json

from daemonos.discovery import DiscoveryService, MockDiscoveryProvider
from daemonos.discovery.evidence import ProbeStatus, EvidenceKind
from daemonos.discovery.profile import DeviceCapabilityProfile, SCHEMA_VERSION
from daemonos.discovery.provider import DiscoveryRegistry
from daemonos.catalog.loader import load_builtin_catalog
from daemonos.planner import DeploymentPlanner, PlanStatus, PlanRisk


def test_mock_list_devices():
    svc = DiscoveryService()
    devices = svc.list_devices()
    keys = {d["device_key"] for d in devices}
    assert "mock-pixel-like" in keys
    assert "mock-unknown" in keys


def test_discover_known_device():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-pixel-like")
    assert isinstance(profile, DeviceCapabilityProfile)
    assert profile.schema_version == SCHEMA_VERSION
    assert profile.hardware.arch == "arm64"
    assert profile.hardware.model == "SynthPhone X"
    assert profile.runtime.os_family == "android"
    assert profile.runtime.android_api == 34
    assert profile.runtime.bootloader_state == "locked"
    assert profile.has_interface("adb")
    # Observations present with provenance
    assert any(o.kind == EvidenceKind.OBSERVED for o in profile.observations)
    assert all(o.source for o in profile.observations if o.kind == EvidenceKind.OBSERVED)


def test_unknown_device_partial():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-unknown")
    assert profile.hardware.arch is None or profile.identification_confidence.value in (
        "low",
        "unknown",
        "medium",
    )
    assert profile.unresolved_questions  # should ask for more probes


def test_permission_denied_probe():
    svc = DiscoveryService()
    result = svc.run_probe("mock", "mock-pixel-like", "probe.root_only")
    assert result.status == ProbeStatus.PERMISSION_DENIED


def test_conflict_probe():
    svc = DiscoveryService()
    result = svc.run_probe("mock", "mock-conflict", "probe.arch")
    assert result.status == ProbeStatus.CONFLICT
    archs = [o.value for o in result.observations if o.field == "arch"]
    assert len(archs) >= 2


def test_profile_serialization_roundtrip():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-pixel-like")
    data = profile.model_dump(mode="json")
    restored = DeviceCapabilityProfile.model_validate(data)
    assert restored.device_key == profile.device_key
    assert restored.hardware.arch == profile.hardware.arch
    # JSON serializable
    json.dumps(data)


def test_schema_version_present():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-linux-dev")
    assert profile.schema_version == "1.0"


def test_plan_compatible_android():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-pixel-like")
    planner = DeploymentPlanner()
    result = planner.plan(profile, objective="run_agent")
    assert result.execution_authorized is False
    assert result.side_effects == []
    assert result.overall_status == PlanStatus.VIABLE
    assert result.preferred is not None
    assert result.preferred.target_id == "agent-android-existing"
    assert result.preferred.risk in (PlanRisk.LOW, PlanRisk.NONE)
    assert result.preferred.invasiveness == "low"


def test_plan_linux_device():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-linux-dev")
    planner = DeploymentPlanner()
    result = planner.plan(profile, objective="run_agent")
    assert result.execution_authorized is False
    assert result.preferred is not None
    assert result.preferred.target_id == "agent-linux-native"


def test_plan_unknown_indeterminate():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-unknown")
    planner = DeploymentPlanner()
    result = planner.plan(profile, objective="run_agent")
    assert result.execution_authorized is False
    # Unknown device should not get a confident viable destructive path
    if result.preferred:
        assert result.preferred.invasiveness != "destructive"
    assert result.overall_status in (
        PlanStatus.UNCERTAIN,
        PlanStatus.REJECTED,
        PlanStatus.UNSUPPORTED,
    )


def test_destructive_rejected_when_locked():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-pixel-like")
    # bootloader is locked on mock-pixel-like
    assert profile.runtime.bootloader_state == "locked"
    planner = DeploymentPlanner()
    result = planner.plan(profile)
    flash_candidates = [c for c in result.candidates if c.strategy_id == "strat-flash-aosp"]
    assert flash_candidates
    assert flash_candidates[0].status == PlanStatus.REJECTED
    assert any("bootloader" in u for u in flash_candidates[0].unmet_hard_requirements)


def test_planner_deterministic():
    svc = DiscoveryService()
    profile = svc.discover("mock", "mock-pixel-like")
    planner = DeploymentPlanner()
    r1 = planner.plan(profile)
    r2 = planner.plan(profile)
    assert r1.overall_status == r2.overall_status
    assert [c.strategy_id for c in r1.candidates] == [c.strategy_id for c in r2.candidates]
    assert [c.status for c in r1.candidates] == [c.status for c in r2.candidates]


def test_planning_has_no_side_effects():
    """Planning must not mutate provider device list or catalog."""
    reg = DiscoveryRegistry()
    mock = MockDiscoveryProvider()
    reg.register(mock)
    svc = DiscoveryService(reg)
    before = mock.list_devices()
    profile = svc.discover("mock", "mock-pixel-like")
    planner = DeploymentPlanner()
    planner.plan(profile)
    assert mock.list_devices() == before


def test_catalog_synthetic_labeled():
    cat = load_builtin_catalog()
    assert "synthetic" in cat.catalog_version or cat.provenance == "builtin-synthetic"
    for s in cat.strategies:
        assert s.verification.value == "synthetic"
