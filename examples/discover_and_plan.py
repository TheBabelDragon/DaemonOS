#!/usr/bin/env python3
"""End-to-end example: discover unknown mock device and request a deployment plan.

Runs fully offline — no physical hardware, no LLM credentials.

Usage:
    PYTHONPATH=src python examples/discover_and_plan.py
"""

from __future__ import annotations

import json
import sys

from daemonos.discovery import DiscoveryService
from daemonos.planner import DeploymentPlanner


def main() -> int:
    svc = DiscoveryService()
    planner = DeploymentPlanner()

    print("=== 1. List visible devices ===")
    devices = svc.list_devices()
    for d in devices:
        print(f"  provider={d['provider']} key={d['device_key']}")

    device_key = "mock-pixel-like"
    print(f"\n=== 2. Discover profile for {device_key} ===")
    profile = svc.discover("mock", device_key)
    print(f"  schema_version: {profile.schema_version}")
    print(f"  identification: {profile.identification_confidence.value}")
    print(f"  model: {profile.hardware.model}")
    print(f"  arch: {profile.hardware.arch}")
    print(f"  os: {profile.runtime.os_family} api={profile.runtime.android_api}")
    print(f"  bootloader: {profile.runtime.bootloader_state}")
    print(f"  interfaces: {[i.name for i in profile.management_interfaces if i.available]}")
    print(f"  unresolved: {profile.unresolved_questions}")
    print(f"  recommended_probes: {profile.recommended_probes}")

    print("\n=== 3. Capability profile (JSON excerpt) ===")
    excerpt = {
        "schema_version": profile.schema_version,
        "device_key": profile.device_key,
        "hardware": profile.hardware.model_dump(),
        "runtime": profile.runtime.model_dump(),
        "capabilities": profile.capabilities,
        "unresolved_questions": profile.unresolved_questions,
    }
    print(json.dumps(excerpt, indent=2, default=str))

    print("\n=== 4. Request deployment plan ===")
    result = planner.plan(profile, objective="run_agent")
    print(f"  overall_status: {result.overall_status.value}")
    print(f"  execution_authorized: {result.execution_authorized}")
    print(f"  side_effects: {result.side_effects}")
    print(f"  summary: {result.summary}")

    if result.preferred:
        p = result.preferred
        print(f"\n  Preferred plan:")
        print(f"    strategy: {p.strategy_id}")
        print(f"    target: {p.target_id}")
        print(f"    risk: {p.risk.value}")
        print(f"    invasiveness: {p.invasiveness}")
        print(f"    reasons: {p.reasons}")
    else:
        print("\n  No preferred plan.")
        for c in result.candidates[:3]:
            print(f"    - {c.strategy_id}: {c.status.value} — {c.reasons[:2]}")

    print("\n=== 5. Unknown device (indeterminate) ===")
    unknown = svc.discover("mock", "mock-unknown")
    unknown_plan = planner.plan(unknown)
    print(f"  overall_status: {unknown_plan.overall_status.value}")
    print(f"  unresolved: {unknown_plan.unresolved_questions[:5]}")

    print("\nDone. No device state was modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
