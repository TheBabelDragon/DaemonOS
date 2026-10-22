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


def _ts(dt: datetime) -> str:
    """UTC timestamp with millisecond precision for stable digests."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(dt.microsecond / 1000):03d}Z"


class Envelope(BaseModel):
    """Versioned protocol envelope."""

    protocol_version: str = PROTOCOL_VERSION
    kind: EnvelopeKind
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nonce: str = Field(default_factory=lambda: uuid4().hex)
    operation: str | None = None
    content_digest: str | None = None
    payload: dict[str, Any] | None = None
    envelope_digest: str | None = None
    auth_ref: str | None = None
    error_code: ProtocolErrorCode | None = None
    error_digest: str | None = None

    def compute_content_digest(self) -> str:
        if self.payload is None:
            raise ValueError("no payload to digest")
        return content_digest(self.payload)

    def seal(self) -> Envelope:
        if self.payload is not None:
            self.content_digest = content_digest(self.payload)
        self.envelope_digest = self._envelope_digest()
        return self

    def _envelope_digest(self) -> str:
        # Only non-null fields participate — stable across JSON omit/include of nulls
        body: dict[str, Any] = {
            "protocol_version": self.protocol_version,
            "kind": self.kind.value,
            "message_id": self.message_id,
            "timestamp": _ts(self.timestamp),
            "nonce": self.nonce,
        }
        if self.correlation_id is not None:
            body["correlation_id"] = self.correlation_id
        if self.operation is not None:
            body["operation"] = self.operation
        if self.content_digest is not None:
            body["content_digest"] = self.content_digest
        if self.auth_ref is not None:
            body["auth_ref"] = self.auth_ref
        if self.error_code is not None:
            body["error_code"] = self.error_code.value
        if self.error_digest is not None:
            body["error_digest"] = self.error_digest
        return content_digest(body)

    def verify_integrity(self) -> bool:
        if not self.envelope_digest:
            return False
        return self.envelope_digest == self._envelope_digest()

    def verify_content(self) -> bool:
        if self.payload is None or not self.content_digest:
            return self.payload is None and not self.content_digest
        return self.content_digest == content_digest(self.payload)
