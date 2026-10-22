"""Tests for Gorgolath hash-native protocol."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from daemonos.api import create_app
from daemonos.core.auth import CapabilityToken
from daemonos.gorgolath import (
    SKILL_ISSUE_DIGEST,
    Envelope,
    EnvelopeKind,
    GorgolathDaemon,
    canonical_bytes,
    content_digest,
)
from daemonos.gorgolath.envelope import ProtocolErrorCode
from daemonos.provision.enrollment import EnrollmentService, EnrollmentRequest


def test_skill_issue_digest_constant():
    assert SKILL_ISSUE_DIGEST == content_digest("unused")  # wrong on purpose check length
    assert len(SKILL_ISSUE_DIGEST) == 64
    assert SKILL_ISSUE_DIGEST == __import__("hashlib").sha256(b"skill issue").hexdigest()


def test_canonical_deterministic():
    a = {"b": 1, "a": [3, 2]}
    b = {"a": [3, 2], "b": 1}
    assert canonical_bytes(a) == canonical_bytes(b)
    assert content_digest(a) == content_digest(b)


def test_canonical_rejects_nan():
    with pytest.raises(ValueError):
        content_digest({"x": float("nan")})


def test_envelope_seal_and_verify():
    env = Envelope(kind=EnvelopeKind.REQUEST, operation="ping", payload={"x": 1})
    env.seal()
    assert env.verify_integrity()
    assert env.verify_content()
    env.payload = {"x": 2}
    assert not env.verify_content()


def test_tampered_envelope():
    daemon = GorgolathDaemon(include_debug=True)
    env = Envelope(kind=EnvelopeKind.REQUEST, operation="ping", payload={}).seal()
    env.envelope_digest = "0" * 64
    resp = daemon.handle(env)
    assert resp.envelope.kind == EnvelopeKind.ERROR
    assert resp.envelope.error_code == ProtocolErrorCode.TAMPERED
    assert resp.error_digest == SKILL_ISSUE_DIGEST


def test_replay_protection():
    daemon = GorgolathDaemon(include_debug=True)
    env = Envelope(kind=EnvelopeKind.REQUEST, operation="ping", payload={}).seal()
    r1 = daemon.handle(env)
    assert r1.envelope.kind == EnvelopeKind.RESPONSE
    r2 = daemon.handle(env)
    assert r2.envelope.error_code == ProtocolErrorCode.REPLAY


def test_unknown_hash_resolve():
    daemon = GorgolathDaemon(include_debug=True)
    token = CapabilityToken(
        token_id="t1",
        subject="s",
        capabilities=["gorgolath.resolve"],
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    with pytest.raises(KeyError):
        daemon.resolve("deadbeef" * 8, token)


def test_unauthorized_operation():
    daemon = GorgolathDaemon(include_debug=True)
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="discover.profile",
        payload={"device_key": "mock-pixel-like"},
    ).seal()
    resp = daemon.handle(env, token=None)
    assert resp.envelope.error_code == ProtocolErrorCode.UNAUTHORIZED


def test_valid_digest_is_not_authorization():
    """Sealed envelope with good digests still needs capability."""
    daemon = GorgolathDaemon(include_debug=True)
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="plan",
        payload={"device_key": "mock-pixel-like"},
    ).seal()
    assert env.verify_integrity() and env.verify_content()
    resp = daemon.handle(env, token=None)
    assert resp.envelope.error_code == ProtocolErrorCode.UNAUTHORIZED


def test_discover_profile_via_gorgolath():
    enrollment = EnrollmentService()
    req = EnrollmentRequest(
        device_serial="g1",
        requested_capabilities=["discover", "plan", "gorgolath.resolve"],
    )
    identity = enrollment.request_enrollment(req)
    enrollment.authorize(identity.node_id, req.requested_capabilities)
    node, token = enrollment.complete_enrollment(identity.node_id)

    daemon = GorgolathDaemon(include_debug=True)
    env = Envelope(
        kind=EnvelopeKind.REQUEST,
        operation="discover.profile",
        payload={"provider": "mock", "device_key": "mock-pixel-like"},
        auth_ref=token.token_id,
    ).seal()
    resp = daemon.handle(env, token)
    assert resp.envelope.kind == EnvelopeKind.RESPONSE
    assert resp.result_digest
    assert resp.envelope.correlation_id == env.message_id
    # Resolve hash-linked result
    resolved = daemon.resolve(resp.result_digest, token)
    assert "profile" in resolved
    assert resolved["profile"]["hardware"]["arch"] == "arm64"


def test_api_gorgolath_e2e():
    client = TestClient(create_app())
    r = client.get("/v1/gorgolath/meta")
    assert r.status_code == 200
    assert r.json()["skill_issue_digest"] == SKILL_ISSUE_DIGEST

    r = client.post(
        "/v1/bootstrap/enroll",
        json={
            "device_serial": "gapi",
            "requested_capabilities": [
                "discover",
                "plan",
                "gorgolath.resolve",
                "gorgolath.store",
            ],
        },
    )
    token = r.json()["token_id"]
    headers = {"Authorization": f"Bearer {token}"}

    env = (
        Envelope(
            kind=EnvelopeKind.REQUEST,
            operation="discover.profile",
            payload={"provider": "mock", "device_key": "mock-pixel-like"},
        )
        .seal()
        .model_dump(mode="json")
    )
    r = client.post("/v1/gorgolath/envelope", json=env, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["result_digest"]
    assert body["envelope"]["kind"] == "response"

    r = client.post(
        "/v1/gorgolath/resolve",
        json={"digest": body["result_digest"]},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["payload"]["profile"]["hardware"]["model"] == "SynthPhone X"

    # Unknown hash
    r = client.post(
        "/v1/gorgolath/resolve",
        json={"digest": "00" * 32},
        headers=headers,
    )
    assert r.status_code == 404
