"""daemon-core: foundational execution model."""

from .capability import Capability, CapabilityManifest
from .task import Task, TaskState, TaskResult, TaskSpec
from .lifecycle import TaskLifecycle, InvalidTransitionError
from .auth import CapabilityToken, AuthorizationError, check_capability
from .evidence import ExecutionEvidence, AuditEvent

__all__ = [
    "Capability",
    "CapabilityManifest",
    "Task",
    "TaskState",
    "TaskResult",
    "TaskSpec",
    "TaskLifecycle",
    "InvalidTransitionError",
    "CapabilityToken",
    "AuthorizationError",
    "check_capability",
    "ExecutionEvidence",
    "AuditEvent",
]
