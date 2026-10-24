"""Cryptographically linked evidence records for Gorgolath.

Each record carries digests of inputs, configuration, operation identity,
result, provenance, timestamps, and parent-record digests. Verification
detects modified records and broken parent links. Missing referenced
content is reported as a limitation, never claimed as successful verification.

A hash does not prove device identity, result correctness, or authorization.
Those claims require their own independent evidence mechanisms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .canonical import content_digest
from .binary import BINARY_PROTOCOL_VERSION


def _ts(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(dt.microsecond / 1000):03d}Z"


@dataclass
class EvidenceRecord:
    """Canonical evidence record."""

    evidence_id: str
    protocol_version: int
    operation: str
    device_id: str | None
    task_id: str | None
    input_digest: str
    config_digest: str
    result_digest: str
    parent_digests: list[str]
    provenance: str
    timestamp: str
    record_digest: str = ""

    def to_payload(self) -> dict[str, Any]:
        """Fields that participate in record_digest (excluding record_digest itself)."""
        return {
            "evidence_id": self.evidence_id,
            "protocol_version": self.protocol_version,
            "operation": self.operation,
            "device_id": self.device_id,
            "task_id": self.task_id,
            "input_digest": self.input_digest,
            "config_digest": self.config_digest,
            "result_digest": self.result_digest,
            "parent_digests": list(self.parent_digests),
            "provenance": self.provenance,
            "timestamp": self.timestamp,
        }

    def seal(self) -> "EvidenceRecord":
        body = self.to_payload()
        self.record_digest = content_digest(body)
        return self

    def verify_self(self) -> bool:
        if not self.record_digest:
            return False
        return self.record_digest == content_digest(self.to_payload())

    def as_dict(self) -> dict[str, Any]:
        d = self.to_payload()
        d["record_digest"] = self.record_digest
        return d


@dataclass
class VerificationResult:
    ok: bool
    record_intact: bool
    parents_intact: bool
    missing_parents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "record_intact": self.record_intact,
            "parents_intact": self.parents_intact,
            "missing_parents": list(self.missing_parents),
            "notes": list(self.notes),
        }


class EvidenceStore:
    """In-memory store of sealed evidence records, keyed by evidence_id and digest."""

    def __init__(self) -> None:
        self._by_id: dict[str, EvidenceRecord] = {}
        self._by_digest: dict[str, EvidenceRecord] = {}

    def put(self, record: EvidenceRecord) -> EvidenceRecord:
        if not record.record_digest:
            record.seal()
        self._by_id[record.evidence_id] = record
        self._by_digest[record.record_digest] = record
        return record

    def get_by_id(self, evidence_id: str) -> EvidenceRecord | None:
        return self._by_id.get(evidence_id)

    def get_by_digest(self, digest: str) -> EvidenceRecord | None:
        return self._by_digest.get(digest)

    def create(
        self,
        *,
        operation: str,
        input_digest: str,
        config_digest: str = "",
        result_digest: str = "",
        parent_digests: list[str] | None = None,
        device_id: str | None = None,
        task_id: str | None = None,
        provenance: str = "daemonos-gorgolath",
        protocol_version: int = BINARY_PROTOCOL_VERSION,
    ) -> EvidenceRecord:
        rec = EvidenceRecord(
            evidence_id=str(uuid4()),
            protocol_version=protocol_version,
            operation=operation,
            device_id=device_id,
            task_id=task_id,
            input_digest=input_digest or content_digest({}),
            config_digest=config_digest or content_digest({}),
            result_digest=result_digest or content_digest({}),
            parent_digests=list(parent_digests or []),
            provenance=provenance,
            timestamp=_ts(),
        )
        return self.put(rec.seal())

    def verify(self, record: EvidenceRecord) -> VerificationResult:
        notes: list[str] = []
        record_intact = record.verify_self()
        if not record_intact:
            notes.append("record_digest does not match canonical content")

        missing: list[str] = []
        parents_intact = True
        for parent_d in record.parent_digests:
            parent = self.get_by_digest(parent_d)
            if parent is None:
                missing.append(parent_d)
                parents_intact = False
                notes.append(
                    f"parent digest {parent_d[:16]}… unavailable; "
                    "cannot claim successful chain verification"
                )
            else:
                if not parent.verify_self():
                    parents_intact = False
                    notes.append(f"parent {parent_d[:16]}… failed self-verification")

        ok = record_intact and parents_intact and not missing
        if missing:
            ok = False

        return VerificationResult(
            ok=ok,
            record_intact=record_intact,
            parents_intact=parents_intact and not missing,
            missing_parents=missing,
            notes=notes,
        )
