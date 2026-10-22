"""Tests for task lifecycle, idempotency, and authorization."""

from datetime import datetime, timedelta, timezone

import pytest

from daemonos.core.auth import CapabilityToken, AuthorizationError, check_capability
from daemonos.core.lifecycle import TaskLifecycle, InvalidTransitionError
from daemonos.core.task import Task, TaskSpec, TaskState, TaskResult
from daemonos.runtime import TaskStore, SimulatedExecutor
from daemonos.fleet.inventory import FleetInventory, NodeRecord, NodeHealth
from daemonos.provision.enrollment import EnrollmentService, EnrollmentRequest, EnrollmentState


def make_token(caps: list[str], *, revoked: bool = False, expired: bool = False) -> CapabilityToken:
    now = datetime.now(timezone.utc)
    return CapabilityToken(
        token_id="tok-test",
        subject="test-node",
        capabilities=caps,
        issued_at=now,
        expires_at=now - timedelta(hours=1) if expired else now + timedelta(hours=1),
        revoked=revoked,
    )


def test_valid_lifecycle_transitions():
    task = Task(spec=TaskSpec(capability="echo"))
    assert task.state == TaskState.PENDING
    TaskLifecycle.transition(task, TaskState.ACCEPTED)
    assert task.state == TaskState.ACCEPTED
    assert task.accepted_at is not None
    TaskLifecycle.transition(task, TaskState.RUNNING)
    assert task.state == TaskState.RUNNING
    TaskLifecycle.transition(task, TaskState.SUCCEEDED, result=TaskResult(success=True, verified=True))
    assert task.state == TaskState.SUCCEEDED
    assert task.result is not None and task.result.verified


def test_invalid_transition_raises():
    task = Task(spec=TaskSpec(capability="echo"))
    TaskLifecycle.transition(task, TaskState.ACCEPTED)
    TaskLifecycle.transition(task, TaskState.RUNNING)
    TaskLifecycle.transition(task, TaskState.SUCCEEDED, result=TaskResult(success=True))
    with pytest.raises(InvalidTransitionError):
        TaskLifecycle.transition(task, TaskState.RUNNING)


def test_idempotency():
    store = TaskStore()
    spec = TaskSpec(capability="echo", parameters={"message": "hi"}, idempotency_key="k1")
    t1 = store.create(spec)
    t2 = store.create(spec)
    assert t1.id == t2.id


def test_authorization_default_deny():
    with pytest.raises(AuthorizationError):
        check_capability(None, "task.submit")
    tok = make_token(["task.submit"])
    check_capability(tok, "task.submit")
    with pytest.raises(AuthorizationError):
        check_capability(tok, "task.execute")


def test_expired_token_denied():
    tok = make_token(["*"], expired=True)
    with pytest.raises(AuthorizationError):
        check_capability(tok, "task.submit")


def test_revoked_token_denied():
    tok = make_token(["*"], revoked=True)
    with pytest.raises(AuthorizationError):
        check_capability(tok, "task.submit")


def test_simulated_echo_task():
    enrollment = EnrollmentService()
    fleet = FleetInventory()
    store = TaskStore()
    executor = SimulatedExecutor(store, fleet, enrollment)

    req = EnrollmentRequest(device_serial="sim-001", requested_capabilities=["task.submit", "task.execute", "task.cancel"])
    identity = enrollment.request_enrollment(req)
    enrollment.authorize(identity.node_id)
    node, token = enrollment.complete_enrollment(identity.node_id)
    fleet.upsert(
        NodeRecord(
            node_id=node.node_id,
            device_serial=node.device_serial,
            state=EnrollmentState.ENROLLED,
            health=NodeHealth.HEALTHY,
            capabilities=node.capabilities,
        )
    )

    task = executor.submit(TaskSpec(capability="echo", parameters={"message": "hello"}), token)
    task = executor.accept_and_run(task.id, token)
    assert task.state == TaskState.SUCCEEDED
    assert task.result is not None
    assert task.result.stdout == "hello"
    assert task.result.verified is True


def test_failed_task_retry():
    enrollment = EnrollmentService()
    fleet = FleetInventory()
    store = TaskStore()
    executor = SimulatedExecutor(store, fleet, enrollment)

    req = EnrollmentRequest(device_serial="sim-002", requested_capabilities=["task.submit", "task.execute"])
    identity = enrollment.request_enrollment(req)
    enrollment.authorize(identity.node_id)
    node, token = enrollment.complete_enrollment(identity.node_id)
    fleet.upsert(
        NodeRecord(
            node_id=node.node_id,
            device_serial=node.device_serial,
            state=EnrollmentState.ENROLLED,
            health=NodeHealth.HEALTHY,
            capabilities=node.capabilities,
        )
    )

    task = executor.submit(TaskSpec(capability="fail", max_retries=1), token)
    task = executor.accept_and_run(task.id, token)
    assert task.state == TaskState.FAILED
    task = executor.retry(task.id, token)
    # still fails, but retry count incremented
    assert task.retry_count >= 1
