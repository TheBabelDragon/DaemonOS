"""Capability-based authorization (default-deny)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AuthorizationError(Exception):
    """Raised when a capability check fails."""

    def __init__(self, message: str = "authorization denied"):
        super().__init__(message)


class CapabilityToken(BaseModel):
    """Short-lived token granting specific capabilities."""

    token_id: str
    subject: str  # node or principal id
    capabilities: list[str]
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    issuer: str = "daemonos-control"
    revoked: bool = False

    def is_valid(self) -> bool:
        if self.revoked:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def grants(self, capability: str) -> bool:
        if not self.is_valid():
            return False
        return capability in self.capabilities or "*" in self.capabilities


def check_capability(token: CapabilityToken | None, required: str) -> None:
    """Default-deny check. Raises AuthorizationError if not granted."""
    if token is None:
        raise AuthorizationError("no token provided")
    if not token.grants(required):
        raise AuthorizationError(f"capability '{required}' not granted")
