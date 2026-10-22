"""Explicit task lifecycle and state transitions."""

from __future__ import annotations

from datetime import datetime, timezone

from .task import Task, TaskState, TaskResult


class InvalidTransitionError(Exception):
    """Raised when a state transition is not permitted."""

    def __init__(self, task_id: str, from_state: TaskState, to_state: TaskState):
        self.task_id = task_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Task {task_id}: invalid transition {from_state.value} -> {to_state.value}")


# Allowed transitions: from -> set of allowed to
_ALLOWED: dict[TaskState, set[TaskState]] = {
    TaskState.PENDING: {TaskState.ACCEPTED, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.ACCEPTED: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED, TaskState.TIMED_OUT},
    TaskState.RUNNING: {
        TaskState.SUCCEEDED,
        TaskState.FAILED,
        TaskState.CANCELLED,
        TaskState.TIMED_OUT,
        TaskState.PENDING,  # for retry/resume
    },
    TaskState.SUCCEEDED: set(),
    TaskState.FAILED: {TaskState.PENDING},  # retry
    TaskState.CANCELLED: set(),
    TaskState.TIMED_OUT: {TaskState.PENDING},  # retry
}


class TaskLifecycle:
    """Enforces valid state transitions and records timestamps."""

    @staticmethod
    def can_transition(task: Task, to_state: TaskState) -> bool:
        return to_state in _ALLOWED.get(task.state, set())

    @staticmethod
    def transition(task: Task, to_state: TaskState, *, result: TaskResult | None = None, error: str | None = None) -> Task:
        if not TaskLifecycle.can_transition(task, to_state):
            raise InvalidTransitionError(task.id, task.state, to_state)

        prev = task.state
        now = datetime.now(timezone.utc)
        task.state = to_state
        task.touch()

        if to_state == TaskState.ACCEPTED:
            task.accepted_at = now
        elif to_state == TaskState.RUNNING:
            task.started_at = now
        elif to_state in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED, TaskState.TIMED_OUT):
            task.completed_at = now
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error
        elif to_state == TaskState.PENDING and prev != TaskState.PENDING:
            # retry path
            task.retry_count += 1
            task.result = None
            task.error = None
            task.started_at = None
            task.completed_at = None

        return task
