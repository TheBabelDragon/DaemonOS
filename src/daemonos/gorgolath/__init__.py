"""Gorgolath: hash-native + canonical binary protocol for agent communication.

External interfaces:
  - JSON hash-oriented envelopes (existing)
  - Canonical binary wire format (v1)

Human-readable diagnostics live on an explicitly separate debug surface.
A valid digest is never authorization and never triggers execution by itself.
"""

from .canonical import canonical_bytes, content_digest, SKILL_ISSUE_DIGEST
from .envelope import Envelope, EnvelopeKind, ProtocolErrorCode
from .protocol import GorgolathDaemon, GorgolathResponse
from .store import HashStore
from .binary import (
    BINARY_PROTOCOL_VERSION,
    BinaryProtocolError,
    MessageType,
    encode_message,
    decode_message,
    verify_message,
    compute_payload_digest,
)
from .binary_runtime import BinaryGorgolathRuntime
from .operations import OperationRegistry, OperationSpec, BUILTIN_OPERATIONS
from .evidence_chain import EvidenceRecord, EvidenceStore, VerificationResult

__all__ = [
    "canonical_bytes",
    "content_digest",
    "SKILL_ISSUE_DIGEST",
    "Envelope",
    "EnvelopeKind",
    "ProtocolErrorCode",
    "GorgolathDaemon",
    "GorgolathResponse",
    "HashStore",
    "BINARY_PROTOCOL_VERSION",
    "BinaryProtocolError",
    "MessageType",
    "encode_message",
    "decode_message",
    "verify_message",
    "compute_payload_digest",
    "BinaryGorgolathRuntime",
    "OperationRegistry",
    "OperationSpec",
    "BUILTIN_OPERATIONS",
    "EvidenceRecord",
    "EvidenceStore",
    "VerificationResult",
]
