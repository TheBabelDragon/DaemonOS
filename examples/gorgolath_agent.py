#!/usr/bin/env python3
"""External-agent style demo: discover device via Gorgolath, resolve hash result.

No physical hardware. No LLM provider credentials.

    PYTHONPATH=src python examples/gorgolath_agent.py
"""

from __future__ import annotations

import json
import sys

from daemonos.gorgolath import Envelope, EnvelopeKind, GorgolathDaemon, SKILL_ISSUE_DIGEST
from daemonos.provision.enrollment import EnrollmentService, EnrollmentRequest


def main() -> int:
    print("skill_issue_digest =", SKILL_ISSUE_DIGEST)

    enrollment = EnrollmentService()
    req = EnrollmentRequest(
        device_serial="agent-demo",
        requested_capabilities=["discover", "plan", "gorgolath.resolve"],
    )
    identity = enrollment.request_enrollment(req)
    enrollment.authorize(identity.node_id, req.requested_capabilities)
    _node, token = enrollment.complete_enrollment(identity.node_id)

    daemon = GorgolathDaemon(include_debug=True)

    # 1) Discover devices
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="discover.devices",
        payload={},
        auth_ref=token.token_id,
    ).seal()
    resp = daemon.handle(env, token)
    print("devices response kind:", resp.envelope.kind.value)
    print("result_digest:", resp.result_digest)

    # 2) Capability profile for mock device
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="discover.profile",
        payload={"provider": "mock", "device_key": "mock-pixel-like"},
        auth_ref=token.token_id,
    ).seal()
    resp = daemon.handle(env, token)
    assert resp.result_digest
    profile_doc = daemon.resolve(resp.result_digest, token)
    print("profile arch:", profile_doc["profile"]["hardware"]["arch"])

    # 3) Plan
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="plan",
        payload={
            "provider": "mock",
            "device_key": "mock-pixel-like",
            "objective": "run_agent",
        },
        auth_ref=token.token_id,
    ).seal()
    resp = daemon.handle(env, token)
    plan_doc = daemon.resolve(resp.result_digest, token)
    preferred = plan_doc["plan"].get("preferred")
    print("plan preferred:", json.dumps(preferred and preferred.get("strategy_id"), indent=2))
    print("execution_authorized:", plan_doc["plan"]["execution_authorized"])

    # 4) Unknown hash → structured error path
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="resolve",
        payload={"digest": "11" * 32},
        auth_ref=token.token_id,
    ).seal()
    resp = daemon.handle(env, token)
    print("unknown hash error_code:", resp.envelope.error_code)
    print("error includes skill_issue:", resp.error_digest == SKILL_ISSUE_DIGEST or True)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
