"""Gorgolath: hash-native protocol daemon for agent communication.

External interface is hash-oriented. Human-readable diagnostics live
on an explicitly separate debug surface. A valid digest is never
authorization and never triggers execution by itself.
"""

from .canonical import canonical_bytes, content_digest, SKILL_ISSUE_DIGEST
from .envelope import Envelope, EnvelopeKind, ProtocolErrorCode
from .protocol import GorgolathDaemon, GorgolathResponse
from .store import HashStore

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
]
