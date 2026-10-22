"""Gorgolath hash-native HTTP surface."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from daemonos.core.auth import AuthorizationError, CapabilityToken
from daemonos.gorgolath import (
    Envelope,
    EnvelopeKind,
    GorgolathDaemon,
    SKILL_ISSUE_DIGEST,
)
from daemonos.gorgolath.canonical import PROTOCOL_VERSION


class EnvelopeIn(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    kind: EnvelopeKind = EnvelopeKind.REQUEST
    message_id: str | None = None
    correlation_id: str | None = None
    nonce: str | None = None
    operation: str | None = None
    content_digest: str | None = None
    payload: dict[str, Any] | None = None
    envelope_digest: str | None = None
    auth_ref: str | None = None


class ResolveIn(BaseModel):
    digest: str


def build_gorgolath_router(
    daemon: GorgolathDaemon,
    resolve_token: Callable[[str | None], CapabilityToken | None],
) -> APIRouter:
    router = APIRouter(prefix="/v1/gorgolath", tags=["gorgolath"])

    @router.get("/meta")
    def meta() -> dict[str, Any]:
        return {
            "protocol": "gorgolath",
            "protocol_version": PROTOCOL_VERSION,
            "skill_issue_digest": SKILL_ISSUE_DIGEST,
            "supported_operations": sorted(GorgolathDaemon.SUPPORTED_OPS),
            "notes": [
                "Hashes are not reversible messages",
                "A valid digest is not authorization",
                "Integrity, authentication, validation, and authorization are separate checks",
            ],
        }

    @router.post("/envelope")
    def submit_envelope(
        body: EnvelopeIn,
        authorization: str | None = Header(default=None),
        x_gorgolath_debug: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = resolve_token(authorization)
        data = body.model_dump(exclude_none=True)
        # Strip client envelope_digest; HTTP intake re-seals after parse so
        # timestamp/null normalization cannot false-positive as tamper.
        # Content digests are still verified when both payload and content_digest present.
        client_content_digest = data.pop("content_digest", None)
        data.pop("envelope_digest", None)
        env = Envelope(**data)
        if env.payload is not None and client_content_digest:
            env.content_digest = client_content_digest
            if not env.verify_content():
                env = Envelope(
                    kind=EnvelopeKind.ERROR,
                    correlation_id=env.message_id,
                    operation=env.operation,
                    error_code=__import__(
                        "daemonos.gorgolath.envelope", fromlist=["ProtocolErrorCode"]
                    ).ProtocolErrorCode.TAMPERED,
                    error_digest=SKILL_ISSUE_DIGEST,
                ).seal()
                return {
                    "envelope": env.model_dump(mode="json"),
                    "result_digest": None,
                    "error_digest": SKILL_ISSUE_DIGEST,
                }
        env.seal()
        if x_gorgolath_debug == "1":
            daemon.include_debug = True
        resp = daemon.handle(env, token)
        out: dict[str, Any] = {
            "envelope": resp.envelope.model_dump(mode="json"),
            "result_digest": resp.result_digest,
            "error_digest": resp.error_digest,
        }
        if resp.debug is not None:
            out["debug"] = resp.debug
        return out

    @router.post("/resolve")
    def resolve_hash(
        body: ResolveIn,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = resolve_token(authorization)
        try:
            payload = daemon.resolve(body.digest, token)
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "unknown_hash",
                    "skill_issue": SKILL_ISSUE_DIGEST,
                },
            ) from None
        return {"digest": body.digest, "payload": payload}

    @router.get("/debug/explain/{digest}")
    def debug_explain(
        digest: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = resolve_token(authorization)
        try:
            payload = daemon.resolve(digest, token)
        except AuthorizationError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except KeyError:
            return {
                "digest": digest,
                "known": False,
                "explanation": "unknown hash",
                "skill_issue": SKILL_ISSUE_DIGEST,
            }
        return {
            "digest": digest,
            "known": True,
            "explanation": "resolved payload follows",
            "payload": payload,
        }

    return router
