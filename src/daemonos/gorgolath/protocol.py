"""Gorgolath protocol daemon.

Processes sealed envelopes. Never executes an operation merely because
a digest is valid. Authorization uses DaemonOS capability tokens.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from daemonos.core.auth import AuthorizationError, CapabilityToken, check_capability
from daemonos.discovery.service import DiscoveryService
from daemonos.planner.planner import DeploymentPlanner

from .canonical import PROTOCOL_VERSION, SKILL_ISSUE_DIGEST, content_digest
from .envelope import Envelope, EnvelopeKind, ProtocolErrorCode
from .store import HashStore


class GorgolathResponse(BaseModel):
    """Hash-oriented external response."""

    envelope: Envelope
    # Hash references only on the external surface
    result_digest: str | None = None
    error_digest: str | None = None
    # Debug payload is never the primary interface
    debug: dict[str, Any] | None = None


class GorgolathDaemon:
    """Hash-native request processor bound to DaemonOS services."""

    SUPPORTED_OPS = frozenset(
        {
            "ping",
            "discover.devices",
            "discover.profile",
            "plan",
            "resolve",
            "store",
        }
    )

    def __init__(
        self,
        discovery: DiscoveryService | None = None,
        planner: DeploymentPlanner | None = None,
        store: HashStore | None = None,
        *,
        include_debug: bool = False,
    ) -> None:
        self.discovery = discovery or DiscoveryService()
        self.planner = planner or DeploymentPlanner()
        self.store = store or HashStore()
        self.include_debug = include_debug
        self._seen_nonces: set[str] = set()
        self._seen_message_ids: set[str] = set()

    def handle(
        self,
        envelope: Envelope,
        token: CapabilityToken | None = None,
    ) -> GorgolathResponse:
        # 1) Version negotiation
        if envelope.protocol_version != PROTOCOL_VERSION:
            return self._error(
                envelope,
                ProtocolErrorCode.VERSION_MISMATCH,
                debug_msg=f"expected {PROTOCOL_VERSION}",
            )

        # 2) Malformed / integrity (separate from auth)
        if envelope.envelope_digest and not envelope.verify_integrity():
            return self._error(envelope, ProtocolErrorCode.TAMPERED, debug_msg="envelope digest mismatch")

        if envelope.payload is not None and envelope.content_digest:
            if not envelope.verify_content():
                return self._error(envelope, ProtocolErrorCode.TAMPERED, debug_msg="content digest mismatch")

        # 3) Replay protection
        if envelope.nonce in self._seen_nonces or envelope.message_id in self._seen_message_ids:
            return self._error(envelope, ProtocolErrorCode.REPLAY, debug_msg="nonce or message_id reused")
        self._seen_nonces.add(envelope.nonce)
        self._seen_message_ids.add(envelope.message_id)

        # 4) Operation present
        op = envelope.operation
        if not op:
            return self._error(envelope, ProtocolErrorCode.MALFORMED, debug_msg="missing operation")

        if op not in self.SUPPORTED_OPS:
            return self._error(
                envelope,
                ProtocolErrorCode.UNSUPPORTED_OP,
                debug_msg=f"unsupported operation {op}",
            )

        # 5) Authorization (valid hash ≠ authorization)
        try:
            self._authorize(op, token)
        except AuthorizationError as e:
            return self._error(
                envelope,
                ProtocolErrorCode.UNAUTHORIZED,
                debug_msg=str(e),
            )

        # 6) Dispatch
        try:
            result_payload = self._dispatch(op, envelope, token)
        except KeyError as e:
            return self._error(envelope, ProtocolErrorCode.UNKNOWN_HASH, debug_msg=str(e))
        except Exception as e:  # noqa: BLE001 — mapped to structured protocol error
            return self._error(envelope, ProtocolErrorCode.INTERNAL, debug_msg=str(e))

        result_digest = self.store.put(
            result_payload,
            owner_ref=token.subject if token else None,
        )
        resp_env = Envelope(
            kind=EnvelopeKind.RESPONSE,
            correlation_id=envelope.message_id,
            operation=op,
            content_digest=result_digest,
            payload=None,  # external interface: hash-oriented
            auth_ref=token.token_id if token else None,
        ).seal()

        debug = None
        if self.include_debug:
            debug = {"result_payload": result_payload, "result_digest": result_digest}

        return GorgolathResponse(
            envelope=resp_env,
            result_digest=result_digest,
            debug=debug,
        )

    def resolve(
        self,
        digest: str,
        token: CapabilityToken | None = None,
        *,
        allow_sensitive: bool = False,
    ) -> dict[str, Any]:
        """Resolve a hash to payload. Requires auth; not a public oracle."""
        check_capability(token, "gorgolath.resolve")
        obj = self.store.get(digest)
        if obj is None:
            raise KeyError(digest)
        if obj.sensitive and not allow_sensitive:
            raise AuthorizationError("sensitive payload requires elevated resolve")
        return dict(obj.payload)

    def _authorize(self, op: str, token: CapabilityToken | None) -> None:
        needed = {
            "ping": None,  # no auth for ping
            "discover.devices": "discover",
            "discover.profile": "discover",
            "plan": "plan",
            "resolve": "gorgolath.resolve",
            "store": "gorgolath.store",
        }.get(op, "gorgolath")
        if needed is None:
            return
        check_capability(token, needed)

    def _dispatch(
        self,
        op: str,
        envelope: Envelope,
        token: CapabilityToken | None,
    ) -> dict[str, Any]:
        payload = envelope.payload or {}

        if op == "ping":
            return {"pong": True, "protocol_version": PROTOCOL_VERSION}

        if op == "discover.devices":
            return {"devices": self.discovery.list_devices()}

        if op == "discover.profile":
            provider = str(payload.get("provider", "mock"))
            device_key = str(payload["device_key"])
            probe_ids = payload.get("probe_ids")
            profile = self.discovery.discover(provider, device_key, probe_ids)
            data = profile.model_dump(mode="json")
            # timestamps to strings already via mode=json
            return {"profile": data}

        if op == "plan":
            provider = str(payload.get("provider", "mock"))
            device_key = str(payload["device_key"])
            objective = str(payload.get("objective", "run_agent"))
            profile = self.discovery.discover(provider, device_key, payload.get("probe_ids"))
            plan = self.planner.plan(profile, objective=objective)
            return {"plan": plan.model_dump(mode="json")}

        if op == "resolve":
            digest = str(payload["digest"])
            resolved = self.resolve(digest, token)
            return {"digest": digest, "payload": resolved}

        if op == "store":
            body = payload.get("data")
            if not isinstance(body, dict):
                raise ValueError("store requires data object")
            digest = self.store.put(
                body,
                sensitive=bool(payload.get("sensitive", False)),
                owner_ref=token.subject if token else None,
            )
            return {"digest": digest}

        raise ValueError(f"unhandled op {op}")

    def _error(
        self,
        request: Envelope,
        code: ProtocolErrorCode,
        *,
        debug_msg: str = "",
    ) -> GorgolathResponse:
        # Personality: skill-issue concept always present as digest on errors
        error_digest = SKILL_ISSUE_DIGEST
        if code == ProtocolErrorCode.UNKNOWN_HASH:
            error_digest = content_digest({"code": code.value, "ref": "unknown"})

        err_payload = {
            "code": code.value,
            "error_digest": error_digest,
            "skill_issue": SKILL_ISSUE_DIGEST,
        }
        stored = self.store.put(err_payload)

        env = Envelope(
            kind=EnvelopeKind.ERROR,
            correlation_id=request.message_id,
            operation=request.operation,
            error_code=code,
            error_digest=error_digest,
            content_digest=stored,
            payload=None,
        ).seal()

        debug = None
        if self.include_debug:
            debug = {"message": debug_msg, "code": code.value, "error_payload": err_payload}

        return GorgolathResponse(
            envelope=env,
            error_digest=error_digest,
            result_digest=stored,
            debug=debug,
        )
