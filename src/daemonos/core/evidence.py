"""Structured execution evidence and audit events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    TASK_SUBMITTED = "task.submitted"
    TASK_ACCEPTED = "task.accepted"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    AUTH_DENIED = "auth.denied"
    NODE_ENROLLED = "node.enrolled"
    NODE_REVOKED = "node.revoked"
    FLASH_DRY_RUN = "flash.dry_run"
    FLASH_STARTED = "flash.started"
    CONFIG_APPLIED = "config.applied"


class AuditEvent(BaseModel):
    """Immutable audit record."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str | None = None
    subject: str | None = None  # task_id, node_id, etc.
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionEvidence(BaseModel):
    """Evidence attached to a task execution; verification is explicit."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str  # e.g. "simulated-backend", "node-agent"
    kind: str  # e.g. "stdout", "hash", "photo", "attestation"
    payload: dict[str, Any] = Field(default_factory=dict)
    verified: bool = False
    verification_notes: str = ""
