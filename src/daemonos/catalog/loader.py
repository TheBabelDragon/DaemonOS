"""Load the builtin synthetic compatibility catalog.

All entries are labeled synthetic. No real-world compatibility is claimed.
"""

from __future__ import annotations

from .models import (
    CompatibilityCatalog,
    RuntimeTarget,
    DeploymentStrategy,
    DeviceFamilyProfile,
    VerificationStatus,
)


def load_builtin_catalog() -> CompatibilityCatalog:
    targets = [
        RuntimeTarget(
            id="agent-android-existing",
            name="DaemonOS agent on existing Android OS",
            kind="agent_on_existing_os",
            arch_requirements=["arm64", "arm"],
            os_families=["android"],
            min_android_api=28,
            min_ram_mb=2048,
            requires_unlocked_bootloader=False,
            requires_root=False,
            description=(
                "Install a userspace agent runtime on the stock Android OS. "
                "No firmware modification. Synthetic catalog entry."
            ),
        ),
        RuntimeTarget(
            id="agent-linux-native",
            name="DaemonOS agent on native Linux",
            kind="linux_native",
            arch_requirements=["x86_64", "aarch64", "arm64"],
            os_families=["linux"],
            min_ram_mb=1024,
            requires_unlocked_bootloader=False,
            requires_root=False,
            description="Userspace agent on an existing Linux userspace. Synthetic.",
        ),
        RuntimeTarget(
            id="alt-image-aosp-generic",
            name="Generic AOSP-like image (high risk)",
            kind="alternative_image",
            arch_requirements=["arm64"],
            os_families=["android"],
            min_android_api=30,
            requires_unlocked_bootloader=True,
            requires_root=False,
            description=(
                "Placeholder alternative image path. Requires unlocked bootloader "
                "and device-specific validation. Synthetic — not a real image claim."
            ),
        ),
    ]

    strategies = [
        DeploymentStrategy(
            id="strat-android-agent",
            name="Userspace Android agent install",
            target_id="agent-android-existing",
            invasiveness="low",
            requires_authorization=True,
            prerequisites=[
                "adb available",
                "android_api >= 28",
                "ram_mb >= 2048",
            ],
            steps_summary=[
                "Verify ADB connectivity (read-only)",
                "Push agent package to userspace",
                "Start agent under existing OS",
            ],
            known_limitations=[
                "Vendor restrictions may block background execution",
                "No claim of universal Android support",
            ],
            verification=VerificationStatus.SYNTHETIC,
            evidence_notes="Synthetic fixture for planner tests",
        ),
        DeploymentStrategy(
            id="strat-linux-agent",
            name="Userspace Linux agent install",
            target_id="agent-linux-native",
            invasiveness="low",
            requires_authorization=True,
            prerequisites=["ssh or local shell", "linux os_family"],
            steps_summary=["Install agent package", "Enable service"],
            verification=VerificationStatus.SYNTHETIC,
            evidence_notes="Synthetic fixture",
        ),
        DeploymentStrategy(
            id="strat-flash-aosp",
            name="Flash alternative AOSP-like image",
            target_id="alt-image-aosp-generic",
            invasiveness="destructive",
            requires_authorization=True,
            prerequisites=[
                "bootloader unlocked",
                "fastboot available",
                "device-specific image validated",
            ],
            steps_summary=[
                "Unlock bootloader (destructive, voids warranty)",
                "Flash partitions",
                "Verify boot",
            ],
            known_limitations=[
                "Device-specific drivers/firmware required",
                "Not safe without laboratory validation",
            ],
            verification=VerificationStatus.SYNTHETIC,
            evidence_notes="Synthetic high-risk strategy for rejection tests",
        ),
    ]

    families = [
        DeviceFamilyProfile(
            id="family-synth-phone",
            match_models=["SynthPhone X"],
            match_model_ids=["synth_x_2024"],
            known_compatible_targets=["agent-android-existing"],
            known_incompatible_targets=[],
            notes="Synthetic family for mock-pixel-like",
            verification=VerificationStatus.SYNTHETIC,
        ),
    ]

    return CompatibilityCatalog(
        catalog_version="1.0.0-synthetic",
        provenance="builtin-synthetic",
        targets=targets,
        strategies=strategies,
        device_families=families,
    )
