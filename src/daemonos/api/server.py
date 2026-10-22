"""Versioned API: nodes, capabilities, health, tasks."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from daemonos.core.auth import AuthorizationError, CapabilityToken
from daemonos.core.task import TaskSpec
from daemonos.fleet.inventory import FleetInventory, NodeRecord, NodeHealth
from daemonos.provision.enrollment import (
    EnrollmentService,
    EnrollmentRequest,
    EnrollmentState,
)
from daemonos.runtime import TaskStore, SimulatedExecutor


class TaskCreateBody(BaseModel):
    capability: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    max_retries: int = 0
    node_id: str | None = None


class ErrorBody(BaseModel):
    error: str
    detail: str | None = None


def create_app(
    enrollment: EnrollmentService | None = None,
    fleet: FleetInventory | None = None,
    store: TaskStore | None = None,
    executor: SimulatedExecutor | None = None,
) -> FastAPI:
    enrollment = enrollment or EnrollmentService()
    fleet = fleet or FleetInventory()
    store = store or TaskStore()
    executor = executor or SimulatedExecutor(store, fleet, enrollment)

    app = FastAPI(
        title="DaemonOS API",
        version="1.0.0",
        description="Machine-native API for DaemonOS control plane",
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

    @app.get("/v1/nodes")
    def list_nodes(authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        token = resolve_token(authorization)
        # listing requires any valid token for now
        if token is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return [n.model_dump(mode="json") for n in fleet.list_nodes()]

    @app.get("/v1/nodes/{node_id}")
    def get_node(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = resolve_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="authentication required")
        node = fleet.get(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="node not found")
        return node.model_dump(mode="json")

    @app.get("/v1/nodes/{node_id}/capabilities")
    def get_capabilities(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = resolve_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="authentication required")
        manifest = fleet.get_manifest(node_id)
        if manifest is None:
            raise HTTPException(status_code=404, detail="capabilities not found")
        return manifest.model_dump(mode="json")

    @app.get("/v1/nodes/{node_id}/health")
    def get_health(node_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = resolve_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="authentication required")
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
            # auto-run in this scaffold for the simulated path
            task = executor.accept_and_run(task.id, token)
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return task.model_dump(mode="json")

    @app.get("/v1/tasks/{task_id}")
    def get_task(task_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = resolve_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="authentication required")
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

    # Bootstrap helpers for local/sim use (not production)
    @app.post("/v1/bootstrap/enroll")
    def bootstrap_enroll(req: EnrollmentRequest) -> dict[str, Any]:
        identity = enrollment.request_enrollment(req)
        enrollment.authorize(identity.node_id, req.requested_capabilities or ["task.submit", "task.execute", "task.cancel", "node.report"])
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

    # Attach services for testing
    app.state.enrollment = enrollment
    app.state.fleet = fleet
    app.state.store = store
    app.state.executor = executor
    return app
