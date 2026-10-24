#!/usr/bin/env python3
"""End-to-end demonstration of the Gorgolath Canonical Binary Protocol.

  PYTHONPATH=src python examples/gorgolath_binary_demo.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from daemonos.core.auth import CapabilityToken
from daemonos.gorgolath import (
    BINARY_PROTOCOL_VERSION,
    MessageType,
    encode_message,
    decode_message,
    verify_message,
    BinaryGorgolathRuntime,
    BinaryProtocolError,
    SKILL_ISSUE_DIGEST,
)


def main() -> int:
    print("=== Gorgolath Canonical Binary Protocol demo ===")
    print(f"binary protocol_version = {BINARY_PROTOCOL_VERSION}")
    print(f"skill_issue_digest     = {SKILL_ISSUE_DIGEST}")
    print()

    rt = BinaryGorgolathRuntime()
    token = CapabilityToken(
        token_id="demo",
        subject="demo-agent",
        capabilities=["discover", "plan", "gorgolath.resolve"],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    # 1) Encode typed request
    rid = str(uuid4())
    req = encode_message(
        message_type=MessageType.REQUEST,
        request_id=rid,
        operation="discover.profile",
        arguments={"provider": "mock", "device_key": "mock-pixel-like"},
    )
    print(f"[1] encoded request ({len(req)} bytes)")
    print(f"    verify_message = {verify_message(req)}")

    # 2) Verify + dispatch
    resp_bytes = rt.handle_binary(req, token)
    resp = decode_message(resp_bytes)
    print(f"[2] response type = {resp['message_type'].name}")
    print(f"    model = {resp['arguments']['profile']['hardware']['model']}")
    print(f"    payload_digest = {resp['payload_digest_hex'][:16]}…")

    # 3) Detect one-bit modification
    tampered = bytearray(resp_bytes)
    tampered[40] ^= 0x01
    try:
        decode_message(bytes(tampered))
        print("[3] ERROR: tamper was not detected")
        return 1
    except BinaryProtocolError as e:
        print(f"[3] tamper detected: {e}")

    # 4) Unauthorized (valid digest ≠ authority)
    req2 = encode_message(
        message_type=MessageType.REQUEST,
        request_id=str(uuid4()),
        operation="plan",
        arguments={"device_key": "mock-pixel-like"},
    )
    assert verify_message(req2)
    err = decode_message(rt.handle_binary(req2, token=None))
    print(f"[4] no-token plan → {err['arguments']['code']}")

    # 5) Operation discovery
    req3 = encode_message(
        message_type=MessageType.REQUEST,
        request_id=str(uuid4()),
        operation="ops.list",
        arguments={},
    )
    catalog = decode_message(rt.handle_binary(req3))
    names = [o["name"] for o in catalog["arguments"]["operations"]]
    print(f"[5] discovered ops: {', '.join(sorted(names))}")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
