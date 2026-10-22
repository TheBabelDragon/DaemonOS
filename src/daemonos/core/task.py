"""Versioned task and result contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    """Explicit task lifecycle states."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class TaskSpec(BaseModel):
    """Client-submitted task specification."""

    capability: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    deadline: datetime | None = None
    max_retries: int = 0
    priority: int = 0
    node_id: str | None = None  # optional targeting


class TaskResult(BaseModel):
    """Structured outcome of a task. Outcome is never verified solely from command success."""

    success: bool
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    verified: bool = False  # True only when independent verification succeeded
    verification_method: str | None = None
    message: str = ""


class Task(BaseModel):
    """Durable task record with lifecycle and evidence."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    spec: TaskSpec
    state: TaskState = TaskState.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: TaskResult | None = None
    retry_count: int = 0
    assigned_node_id: str | None = None
    error: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
