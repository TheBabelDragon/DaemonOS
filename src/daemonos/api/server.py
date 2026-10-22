"""Versioned API: nodes, tasks, discovery, planning, operations."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from daemonos.core.auth import AuthorizationError, CapabilityToken, check_capability
from daemonos.core.task import TaskSpec, TaskState
from daemonos.fleet.inventory import FleetInventory, NodeRecord, NodeHealth
from daemonos.provision.enrollment import (
    EnrollmentService,
    EnrollmentRequest,
    EnrollmentState,
)
from daemonos.runtime import TaskStore, SimulatedExecutor
from daemonos.discovery.service import DiscoveryService
from daemonos.planner.planner import DeploymentPlanner
from daemonos.catalog.loader import load_builtin_catalog


class TaskCreateBody(BaseModel):
    capability: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    max_retries: int = 0
    node_id: str | None = None


class DiscoverBody(BaseModel):
    provider: str = "mock"
    device_key: str
    probe_ids: list[str] | None = None


class PlanBody(BaseModel):
    provider: str = "mock"
    device_key: str
    objective: str = "run_agent"
    probe_ids: list[str] | None = None


def create_app(
    enrollment: EnrollmentService | None = None,
    fleet: FleetInventory | None = None,
    store: TaskStore | None = None,
    executor: SimulatedExecutor | None = None,
    discovery: DiscoveryService | None = None,
    planner: DeploymentPlanner | None = None,
) -> FastAPI:
    enrollment = enrollment or EnrollmentService()
    fleet = fleet or FleetInventory()
    store = store or TaskStore()
    executor = executor or SimulatedExecutor(store, fleet, enrollment)
    discovery = discovery or DiscoveryService()
    planner = planner or DeploymentPlanner()

    app = FastAPI(
        title="DaemonOS API",
        version="1.1.0",
        description=(
            "Machine-native API for DaemonOS control plane, "
            "hardware discovery, and deployment planning"
        ),
    )

    def resolve_token(authorization: str | None) -> CapabilityToken | None:
        if not authorization:
            return None
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="invalid authorization scheme")
        token_id = authorization[7:].strip()
        token = enrollment.get_token(token_id)
        if token is None or not token.is_valid():
            raise HTTPException(status_code=401, detail="invalid or expired token")
        return token

    def require_token(authorization: str | None) -> CapabilityToken:
        token = resolve_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return token

    # ---- Self-describing operations (agent discovery) ----

    @app.get("/v1/operations")
    def list_operations() -> dict[str, Any]:
        """Machine-readable list of available operations and schemas."""
        return {
            "api_version": "1.1.0",
            "operations": [
                {
                    "id": "list_operations",
                    "method": "GET",
                    "path": "/v1/operations",
                    "auth": False,
                    "description": "List available API operations",
                },
                {
                    "id": "list_discovery_providers",
                    "method": "GET",
                    "path": "/v1/discovery/providers",
                    "auth": True,
                    "capability": "discover",
                },
                {
                    "id": "list_devices",
                    "method": "GET",
                    "path": "/v1/discovery/devices",
                    "auth": True,
                    "capability": "discover",
                },
                {
                    "id": "list_probes",
                    "method": "GET",
                    "path": "/v1/discovery/devices/{provider}/{device_key}/probes",
                    "auth": True,
                    "capability": "discover",
                },
                {
                    "id": "discover_device",
                    "method": "POST",
                    "path": "/v1/discovery/profile",
                    "auth": True,
                    "capability": "discover",
                    "body_schema": {
                        "provider": "string",
                        "device_key": "string",
                        "probe_ids": "string[] | null",
                    },
                    "side_effects": False,
                    "modifies_device": False,
                },
                {
                    "id": "list_catalog_targets",
                    "method": "GET",
                    "path": "/v1/catalog/targets",
                    "auth": True,
                    "capability": "discover",
                },
                {
                    "id": "plan_deployment",
                    "method": "POST",
                    "path": "/v1/plan",
                    "auth": True,
                    "capability": "plan",
                    "body_schema": {
                        "provider": "string",
                        "device_key": "string",
                        "objective": "string",
                        "probe_ids": "string[] | null",
                    },
                    "side_effects": False,
                    "modifies_device": False,
                    "executes_plan": False,
                },
                {
                    "id": "list_nodes",
                    "method": "GET",
                    "path": "/v1/nodes",
                    "auth": True,
                },
                {
                    "id": "create_task",
                    "method": "POST",
                    "path": "/v1/tasks",
                    "auth": True,
                    "capability": "task.submit",
                },
            ],
        }

    # ---- Discovery (read-only) ----

    @app.get("/v1/discovery/providers")
    def discovery_providers(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = require_token(authorization)
        try:
            check_capability(token, "discover")
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return {"providers": discovery.list_providers()}

    @app.get("/v1/discovery/devices")
    def discovery_devices(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = require_token(authorization)
        try:
            check_capability(token, "discover")
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return {"devices": discovery.list_devices()}

    @app.get("/v1/discovery/devices/{provider}/{device_key}/probes")
    def discovery_probes(
        provider: str,
        device_key: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = require_token(authorization)
        try:
            check_capability(token, "discover")
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        try:
            probes = discovery.list_probes(provider, device_key)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return {"probes": [p.model_dump(mode="json") for p in probes]}

    @app.post("/v1/discovery/profile")
    def discover_profile(
        body: DiscoverBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = require_token(authorization)
        try:
            check_capability(token, "discover")
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        try:
            profile = discovery.discover(body.provider, body.device_key, body.probe_ids)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return profile.model_dump(mode="json")

    # ---- Catalog ----

    @app.get("/v1/catalog/targets")
    def catalog_targets(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = require_token(authorization)
        try:
            check_capability(token, "discover")
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        cat = load_builtin_catalog()
        return {
            "catalog_version": cat.catalog_version,
            "targets": [t.model_dump(mode="json") for t in cat.targets],
            "strategies": [s.model_dump(mode="json") for s in cat.strategies],
        }

    # ---- Planning (never executes) ----

    @app.post("/v1/plan")
    def plan_deployment(
        body: PlanBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = require_token(authorization)
        try:
            check_capability(token, "plan")
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        try:
            profile = discovery.discover(body.provider, body.device_key, body.probe_ids)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        result = planner.plan(profile, objective=body.objective)
        # Hard guarantee in response
        assert result.execution_authorized is False
        assert result.side_effects == []
        return result.model_dump(mode="json")

    # ---- Existing fleet / task endpoints ----

    @app.get("/v1/nodes")
    def list_nodes(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        require_token(authorization)
        return [n.model_dump(mode="json") for n in fleet.list_nodes()]

    @app.get("/v1/nodes/{node_id}")
    def get_node(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_token(authorization)
        node = fleet.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        return node.model_dump(mode="json")

    @app.get("/v1/nodes/{node_id}/capabilities")
    def get_capabilities(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_token(authorization)
        manifest = fleet.get_manifest(node_id)
        if manifest is None:
            raise HTTPException(status_code=404, detail="capabilities not found")
        return manifest.model_dump(mode="json")

    @app.get("/v1/nodes/{node_id}/health")
    def get_health(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_token(authorization)
        node = fleet.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        return {
            "node_id": node.node_id,
            "health": node.health.value,
            "last_seen": node.last_seen.isoformat() if node.last_seen else None,
            "quarantine_reason": node.quarantine_reason,
        }

    @app.post("/v1/tasks", status_code=status.HTTP_201_CREATED)
    def create_task(
        body: TaskCreateBody,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = resolve_token(authorization)
        spec = TaskSpec(
            capability=body.capability,
            parameters=body.parameters,
            idempotency_key=body.idempotency_key,
            max_retries=body.max_retries,
            node_id=body.node_id,
        )
        try:
            task = executor.submit(spec, token)
            if task.state == TaskState.PENDING:
                task = executor.accept_and_run(task.id, token)
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return task.model_dump(mode="json")

    @app.get("/v1/tasks/{task_id}")
    def get_task(task_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_token(authorization)
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task.model_dump(mode="json")

    @app.post("/v1/tasks/{task_id}/cancel")
    def cancel_task(task_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = resolve_token(authorization)
        try:
            task = executor.cancel(task_id, token)
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found") from None
        except Exception as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return task.model_dump(mode="json")

    @app.post("/v1/bootstrap/enroll")
    def bootstrap_enroll(req: EnrollmentRequest) -> dict[str, Any]:
        caps = req.requested_capabilities or [
            "task.submit",
            "task.execute",
            "task.cancel",
            "node.report",
            "discover",
            "plan",
        ]
        identity = enrollment.request_enrollment(req)
        enrollment.authorize(identity.node_id, caps)
        node, token = enrollment.complete_enrollment(identity.node_id)
        record = NodeRecord(
            node_id=node.node_id,
            device_serial=node.device_serial,
            state=EnrollmentState.ENROLLED,
            health=NodeHealth.HEALTHY,
            capabilities=node.capabilities,
        )
        fleet.upsert(record)
        fleet.set_manifest(node.node_id, enrollment.build_manifest(node.node_id))
        fleet.mark_seen(node.node_id)
        return {
            "node": node.model_dump(mode="json"),
            "token_id": token.token_id,
            "expires_at": token.expires_at.isoformat(),
        }

    app.state.enrollment = enrollment
    app.state.fleet = fleet
    app.state.store = store
    app.state.executor = executor
    app.state.discovery = discovery
    app.state.planner = planner
    return app
