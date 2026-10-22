"""In-memory task store and simulated execution backend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from daemonos.core.auth import CapabilityToken, check_capability, AuthorizationError
from daemonos.core.evidence import AuditEvent, AuditEventType, ExecutionEvidence
from daemonos.core.lifecycle import TaskLifecycle, InvalidTransitionError
from daemonos.core.task import Task, TaskSpec, TaskState, TaskResult
from daemonos.fleet.inventory import FleetInventory, NodeHealth
from daemonos.provision.enrollment import EnrollmentService


class TaskStore:
    """Durable (in-memory for scaffold) task persistence with idempotency."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._by_idempotency: dict[str, str] = {}

    def create(self, spec: TaskSpec) -> Task:
        if spec.idempotency_key:
            existing_id = self._by_idempotency.get(spec.idempotency_key)
            if existing_id:
                return self._tasks[existing_id]
        task = Task(spec=spec)
        self._tasks[task.id] = task
        if spec.idempotency_key:
            self._by_idempotency[spec.idempotency_key] = task.id
        return task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def save(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task


class SimulatedExecutor:
    """Executes tasks against simulated node capabilities."""

    def __init__(
        self,
        store: TaskStore,
        fleet: FleetInventory,
        enrollment: EnrollmentService,
    ) -> None:
        self.store = store
        self.fleet = fleet
        self.enrollment = enrollment
        self.audit: list[AuditEvent] = []
        self.evidence: dict[str, ExecutionEvidence] = {}

    def submit(self, spec: TaskSpec, token: CapabilityToken | None = None) -> Task:
        check_capability(token, "task.submit")
        task = self.store.create(spec)
        self._audit(AuditEventType.TASK_SUBMITTED, subject=task.id, actor=token.subject if token else None)
        return task

    def accept_and_run(self, task_id: str, token: CapabilityToken | None = None) -> Task:
        check_capability(token, "task.execute")
        task = self.store.get(task_id)
        if task is None:
            raise KeyError(task_id)

        TaskLifecycle.transition(task, TaskState.ACCEPTED)
        self.store.save(task)
        self._audit(AuditEventType.TASK_ACCEPTED, subject=task.id)

        # Assign node if requested or pick any enrolled healthy node
        node_id = task.spec.node_id
        if node_id is None:
            for n in self.fleet.list_nodes():
                if n.health == NodeHealth.HEALTHY and "task.execute" in n.capabilities:
                    node_id = n.node_id
                    break
        if node_id is None:
            TaskLifecycle.transition(
                task,
                TaskState.FAILED,
                error="no healthy node available",
                result=TaskResult(success=False, message="no healthy node"),
            )
            self.store.save(task)
            return task

        task.assigned_node_id = node_id
        TaskLifecycle.transition(task, TaskState.RUNNING)
        self.store.save(task)
        self._audit(AuditEventType.TASK_STARTED, subject=task.id, details={"node_id": node_id})

        # Simulated execution
        result, evidence = self._simulate(task)
        task.evidence_ids.append(evidence.id)
        self.evidence[evidence.id] = evidence

        if result.success:
            TaskLifecycle.transition(task, TaskState.SUCCEEDED, result=result)
            self._audit(AuditEventType.TASK_COMPLETED, subject=task.id)
        else:
            TaskLifecycle.transition(task, TaskState.FAILED, result=result, error=result.message)
            self._audit(AuditEventType.TASK_FAILED, subject=task.id)

        self.store.save(task)
        self.fleet.mark_seen(node_id)
        return task

    def cancel(self, task_id: str, token: CapabilityToken | None = None) -> Task:
        check_capability(token, "task.cancel")
        task = self.store.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.state in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED):
            raise InvalidTransitionError(task.id, task.state, TaskState.CANCELLED)
        TaskLifecycle.transition(task, TaskState.CANCELLED, error="cancelled by request")
        self.store.save(task)
        self._audit(AuditEventType.TASK_CANCELLED, subject=task.id)
        return task

    def retry(self, task_id: str, token: CapabilityToken | None = None) -> Task:
        check_capability(token, "task.execute")
        task = self.store.get(task_id)
        if task is None:
            raise KeyError(task_id)
        if task.retry_count >= task.spec.max_retries:
            raise ValueError("max retries exceeded")
        TaskLifecycle.transition(task, TaskState.PENDING)
        self.store.save(task)
        return self.accept_and_run(task_id, token)

    def _simulate(self, task: Task) -> tuple[TaskResult, ExecutionEvidence]:
        # Deterministic simulated outcome based on capability name
        cap = task.spec.capability
        params = task.spec.parameters

        if cap == "echo":
            msg = str(params.get("message", ""))
            result = TaskResult(
                success=True,
                exit_code=0,
                stdout=msg,
                verified=True,
                verification_method="echo-roundtrip",
                message="echo completed",
            )
        elif cap == "fail":
            result = TaskResult(
                success=False,
                exit_code=1,
                stderr="simulated failure",
                verified=False,
                message="intentional failure",
            )
        else:
            result = TaskResult(
                success=True,
                exit_code=0,
                stdout=f"executed {cap}",
                verified=False,  # not independently verified
                message=f"simulated execution of {cap}",
            )

        evidence = ExecutionEvidence(
            task_id=task.id,
            source="simulated-backend",
            kind="execution-log",
            payload={
                "capability": cap,
                "parameters": params,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            verified=result.verified,
            verification_notes=result.verification_method or "",
        )
        return result, evidence

    def _audit(
        self,
        event_type: AuditEventType,
        subject: str | None = None,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit.append(
            AuditEvent(
                event_type=event_type,
                subject=subject,
                actor=actor,
                details=details or {},
            )
        )
