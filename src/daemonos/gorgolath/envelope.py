"""Hash-native message envelopes.

Integrity (digest), authentication (optional token binding), semantic
validation, and authorization are separate checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .canonical import PROTOCOL_VERSION, content_digest


class EnvelopeKind(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    RESULT = "result"


class ProtocolErrorCode(str, Enum):
    UNKNOWN_HASH = "unknown_hash"
    MALFORMED = "malformed"
    TAMPERED = "tampered"
    REPLAY = "replay"
    VERSION_MISMATCH = "version_mismatch"
    UNAUTHORIZED = "unauthorized"
    UNSUPPORTED_OP = "unsupported_op"
    SKILL_ISSUE = "skill_issue"
    INTERNAL = "internal"


class Envelope(BaseModel):
    """Versioned protocol envelope."""

    protocol_version: str = PROTOCOL_VERSION
    kind: EnvelopeKind
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None  # links response to request
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nonce: str = Field(default_factory=lambda: uuid4().hex)
    operation: str | None = None  # e.g. discover.profile, plan, resolve
    # Content is referenced by digest; body may be omitted for pure-hash mode
    content_digest: str | None = None
    payload: dict[str, Any] | None = None
    # Optional integrity over the envelope fields excluding this signature field
    envelope_digest: str | None = None
    # Auth binding — token id, not a privilege grant by itself
    auth_ref: str | None = None
    error_code: ProtocolErrorCode | None = None
    error_digest: str | None = None  # hash-oriented error identity

    def compute_content_digest(self) -> str:
        if self.payload is None:
            raise ValueError("no payload to digest")
        return content_digest(self.payload)

    def seal(self) -> Envelope:
        """Fill content_digest and envelope_digest from current fields."""
        if self.payload is not None:
            self.content_digest = content_digest(self.payload)
        self.envelope_digest = self._envelope_digest()
        return self

    def _envelope_digest(self) -> str:
        body = {
            "protocol_version": self.protocol_version,
            "kind": self.kind.value,
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "nonce": self.nonce,
            "operation": self.operation,
            "content_digest": self.content_digest,
            "auth_ref": self.auth_ref,
            "error_code": self.error_code.value if self.error_code else None,
            "error_digest": self.error_digest,
        }
        return content_digest(body)

    def verify_integrity(self) -> bool:
        """Check envelope_digest matches canonical fields (not authorization)."""
        if not self.envelope_digest:
            return False
        return self.envelope_digest == self._envelope_digest()

    def verify_content(self) -> bool:
        if self.payload is None or not self.content_digest:
            return self.payload is None and not self.content_digest
        return self.content_digest == content_digest(self.payload)
