"""Secure first-boot enrollment with short-lived credentials.

Do not embed production secrets or use shared fleet-wide credentials.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from secrets import token_urlsafe
from uuid import uuid4

from pydantic import BaseModel, Field

from daemonos.core.auth import CapabilityToken
from daemonos.core.capability import Capability, CapabilityManifest


class EnrollmentState(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    ENROLLED = "enrolled"
    REVOKED = "revoked"
    EXPIRED = "expired"


class NodeIdentity(BaseModel):
    node_id: str = Field(default_factory=lambda: str(uuid4()))
    device_serial: str
    public_key_pem: str | None = None
    enrolled_at: datetime | None = None
    state: EnrollmentState = EnrollmentState.PENDING
    capabilities: list[str] = Field(default_factory=list)


class EnrollmentRequest(BaseModel):
    device_serial: str
    model: str = "unknown"
    requested_capabilities: list[str] = Field(default_factory=list)
    nonce: str = Field(default_factory=lambda: token_urlsafe(16))


class EnrollmentService:
    """In-memory enrollment for the initial scaffold / simulator path."""

    def __init__(self, credential_ttl_seconds: int = 3600) -> None:
        self._nodes: dict[str, NodeIdentity] = {}
        self._tokens: dict[str, CapabilityToken] = {}
        self._ttl = credential_ttl_seconds

    def request_enrollment(self, req: EnrollmentRequest) -> NodeIdentity:
        identity = NodeIdentity(
            device_serial=req.device_serial,
            capabilities=list(req.requested_capabilities),
            state=EnrollmentState.PENDING,
        )
        self._nodes[identity.node_id] = identity
        return identity

    def authorize(self, node_id: str, approved_capabilities: list[str] | None = None) -> NodeIdentity:
        node = self._require(node_id)
        if node.state == EnrollmentState.REVOKED:
            raise ValueError("node is revoked")
        node.state = EnrollmentState.AUTHORIZED
        if approved_capabilities is not None:
            node.capabilities = approved_capabilities
        return node

    def complete_enrollment(self, node_id: str) -> tuple[NodeIdentity, CapabilityToken]:
        node = self._require(node_id)
        if node.state not in (EnrollmentState.AUTHORIZED, EnrollmentState.PENDING):
            raise ValueError(f"cannot enroll from state {node.state}")
        node.state = EnrollmentState.ENROLLED
        node.enrolled_at = datetime.now(timezone.utc)

        token = CapabilityToken(
            token_id=str(uuid4()),
            subject=node.node_id,
            capabilities=node.capabilities or ["task.execute", "node.report"],
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=self._ttl),
        )
        self._tokens[token.token_id] = token
        return node, token

    def revoke(self, node_id: str) -> NodeIdentity:
        node = self._require(node_id)
        node.state = EnrollmentState.REVOKED
        # invalidate tokens for this subject
        for t in self._tokens.values():
            if t.subject == node_id:
                t.revoked = True
        return node

    def get_token(self, token_id: str) -> CapabilityToken | None:
        return self._tokens.get(token_id)

    def get_node(self, node_id: str) -> NodeIdentity | None:
        return self._nodes.get(node_id)

    def list_nodes(self) -> list[NodeIdentity]:
        return list(self._nodes.values())

    def build_manifest(self, node_id: str) -> CapabilityManifest:
        node = self._require(node_id)
        caps = [
            Capability(name=c, version="1.0", description=f"Granted capability {c}")
            for c in node.capabilities
        ]
        return CapabilityManifest(node_id=node_id, capabilities=caps)

    def _require(self, node_id: str) -> NodeIdentity:
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(f"unknown node {node_id}")
        return node
