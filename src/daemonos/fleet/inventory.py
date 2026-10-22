"""Device inventory, capability discovery, health and connectivity."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from daemonos.core.capability import CapabilityManifest
from daemonos.provision.enrollment import EnrollmentState


class NodeHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    QUARANTINED = "quarantined"


class NodeRecord(BaseModel):
    node_id: str
    device_serial: str
    state: EnrollmentState = EnrollmentState.PENDING
    health: NodeHealth = NodeHealth.UNKNOWN
    last_seen: datetime | None = None
    software_version: str | None = None
    config_version: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    quarantine_reason: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class FleetInventory:
    """In-memory fleet view for the initial control-plane scaffold."""

    def __init__(self) -> None:
        self._nodes: dict[str, NodeRecord] = {}
        self._manifests: dict[str, CapabilityManifest] = {}

    def upsert(self, record: NodeRecord) -> NodeRecord:
        self._nodes[record.node_id] = record
        return record

    def get(self, node_id: str) -> NodeRecord | None:
        return self._nodes.get(node_id)

    def list_nodes(self) -> list[NodeRecord]:
        return list(self._nodes.values())

    def set_manifest(self, node_id: str, manifest: CapabilityManifest) -> None:
        self._manifests[node_id] = manifest

    def get_manifest(self, node_id: str) -> CapabilityManifest | None:
        return self._manifests.get(node_id)

    def mark_seen(self, node_id: str, health: NodeHealth = NodeHealth.HEALTHY) -> None:
        node = self._nodes.get(node_id)
        if node:
            node.last_seen = datetime.now(timezone.utc)
            node.health = health

    def quarantine(self, node_id: str, reason: str) -> NodeRecord:
        node = self._nodes[node_id]
        node.health = NodeHealth.QUARANTINED
        node.quarantine_reason = reason
        return node

    def revoke(self, node_id: str) -> NodeRecord:
        node = self._nodes[node_id]
        node.state = EnrollmentState.REVOKED
        node.health = NodeHealth.QUARANTINED
        node.quarantine_reason = "revoked"
        return node
