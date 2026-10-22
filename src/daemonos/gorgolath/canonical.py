"""Canonical serialization and deterministic content digests.

Equivalent payloads with different key order or whitespace normalize
to the same digest. Hashes are not reversible messages.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

PROTOCOL_VERSION = "1.0"

# Canonical representation of the concept "skill issue" as SHA-256.
# This is a protocol personality constant, not semantic recovery of the phrase.
SKILL_ISSUE_DIGEST = hashlib.sha256(b"skill issue").hexdigest()


def _normalize(obj: Any) -> Any:
    """Recursively normalize for canonical JSON."""
    if isinstance(obj, dict):
        return {str(k): _normalize(obj[k]) for k in sorted(obj.keys(), key=lambda x: str(x))}
    if isinstance(obj, (list, tuple)):
        return [_normalize(x) for x in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        # Reject NaN/Inf for determinism
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError("non-finite floats are not canonical")
        return obj
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    # Fallback: string representation (should be rare)
    return str(obj)


def canonical_bytes(payload: Any) -> bytes:
    """Serialize payload to canonical UTF-8 JSON bytes (sorted keys, no extra space)."""
    normalized = _normalize(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def content_digest(payload: Any) -> str:
    """SHA-256 hex digest of canonical serialization."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
