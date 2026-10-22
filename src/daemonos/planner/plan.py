"""Deployment plan structures. Generating a plan never executes it."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    VIABLE = "viable"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"


class PlanRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class CandidatePlan(BaseModel):
    """One candidate deployment path with evidence-backed explanation."""

    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    strategy_id: str
    target_id: str
    status: PlanStatus
    risk: PlanRisk
    requires_authorization: bool = True
    invasiveness: str = "unknown"
    score: int = 0  # higher = preferred (least invasive viable)
    reasons: list[str] = Field(default_factory=list)
    missing_prerequisites: list[str] = Field(default_factory=list)
    unmet_hard_requirements: list[str] = Field(default_factory=list)
    recommended_probes: list[str] = Field(default_factory=list)
    steps_summary: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)


class PlanResult(BaseModel):
    """Full planner output for a device profile + objective."""

    result_id: str = Field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1.0"
    catalog_version: str
    device_key: str
    objective: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    candidates: list[CandidatePlan] = Field(default_factory=list)
    preferred: CandidatePlan | None = None
    overall_status: PlanStatus = PlanStatus.UNSUPPORTED
    summary: str = ""
    unresolved_questions: list[str] = Field(default_factory=list)
    # Explicit: planning never authorizes or executes
    execution_authorized: bool = False
    side_effects: list[str] = Field(default_factory=lambda: [])
    extra: dict[str, Any] = Field(default_factory=dict)
