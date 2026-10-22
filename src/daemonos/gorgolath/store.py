"""In-memory hash → payload mapping.

Hashes are not publicly enumerable. Resolution requires an authorized
caller; unknown hashes return a structured error. Sensitive payloads
are not exposed through guessable lookups without auth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .canonical import content_digest


@dataclass
class StoredObject:
    digest: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sensitive: bool = False
    owner_ref: str | None = None  # auth subject that stored it


class HashStore:
    def __init__(self) -> None:
        self._objects: dict[str, StoredObject] = {}

    def put(
        self,
        payload: dict[str, Any],
        *,
        sensitive: bool = False,
        owner_ref: str | None = None,
    ) -> str:
        digest = content_digest(payload)
        self._objects[digest] = StoredObject(
            digest=digest,
            payload=payload,
            sensitive=sensitive,
            owner_ref=owner_ref,
        )
        return digest

    def get(self, digest: str) -> StoredObject | None:
        return self._objects.get(digest)

    def contains(self, digest: str) -> bool:
        return digest in self._objects
