from __future__ import annotations
import asyncio
from app.infrastructure.logging import get_logger

from fastapi import APIRouter, Depends, Query, Request
from fastapi import HTTPException

from app.api.deps import (
    get_auth_service,
    get_cart_service,
    get_interaction_service,
    get_memory_service,
    get_optional_user,
    get_orchestrator,
    get_session_service,
)
from app.application.session_workflows import (
    get_or_create_session,
    resolve_user_session_and_link_identity,
)
from app.models.schemas import InteractionMessageRequest

router = APIRouter(prefix="/interactions", tags=["interactions"])
logger = get_logger(__name__)
auth_service = get_auth_service()
cart_service = get_cart_service()
interaction_service = get_interaction_service()
memory_service = get_memory_service()
orchestrator = get_orchestrator()
session_service = get_session_service()


def _resolve_request_session_id(
    *,
    request: Request,
    explicit_session_id: str | None,
    source: str,
) -> str:
    requested_session_id = str(explicit_session_id or "").strip()
    cookie_session_id = str(request.cookies.get("session_id") or "").strip()

    if requested_session_id and cookie_session_id and requested_session_id != cookie_session_id:
        logger.warning(
            "Session mismatch detected; keeping explicit session id",
            source=source,
            requested_session_id=requested_session_id,
            cookie_session_id=cookie_session_id,
        )

    if requested_session_id:
        return requested_session_id
    return cookie_session_id


@router.post("/message")
async def process_message(
    payload: InteractionMessageRequest,
    request: Request,
    user: dict[str, object] | None = Depends(get_optional_user),
) -> dict[str, object]:
    resolved_session_id = _resolve_request_session_id(
        request=request,
        explicit_session_id=payload.sessionId,
        source="interactions_message",
    )

    session = await get_or_create_session(
        session_service=session_service,
        session_id=resolved_session_id or None,
        channel=payload.channel,
        anonymous_id=request.headers.get("X-Anonymous-Id"),
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        source="interactions_message",
        referrer=request.headers.get("referer", ""),
    )

    user_id = str(user["id"]) if user else session.get("userId")
    if user_id:
        try:
            session = await resolve_user_session_and_link_identity(
                session_service=session_service,
                cart_service=cart_service,
                auth_service=auth_service,
                user_id=str(user_id),
                session=session,
                preferred_session_id=resolved_session_id or None,
                channel=payload.channel,
                user_agent=request.headers.get("User-Agent"),
                ip_address=request.client.host if request.client else None,
                source="interactions_message",
                referrer=request.headers.get("referer", ""),
            )
        except (HTTPException, LookupError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            logger.warning("Identity link failed for interaction message", exc_info=exc)
    response = await orchestrator.process_message(
        message=payload.content,
        session_id=session["id"],
        user_id=str(user_id) if user_id else None,
        channel=payload.channel,
    )
    return {"type": "response", "sessionId": session["id"], "payload": response}


@router.get("/history")
def get_history(
    request: Request,
    session_id: str | None = Query(default=None, alias="sessionId"),
    limit: int = Query(default=40, ge=1, le=200),
    user: dict[str, object] | None = Depends(get_optional_user),
) -> dict[str, object]:
    if user:
        user_id = str(user["id"])
        resolved = session_service.resolve_user_session(
            user_id=user_id,
            preferred_session_id=session_id,
            channel="web",
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.client.host if request.client else None,
            metadata={
                "source": "interactions_history",
                "referrer": request.headers.get("referer", ""),
            },
        )
        try:
            auth_service.link_identity(
                user_id=user_id,
                channel="web",
                external_id=str(resolved["id"]),
                anonymous_id=str(resolved.get("anonymousId", "")) or None,
            )
        except (HTTPException, LookupError, KeyError, TypeError, ValueError, RuntimeError) as exc:
            logger.warning("Identity link failed for interaction history", exc_info=exc)
        history = interaction_service.history_for_session(session_id=str(resolved["id"]), limit=limit)
        if not history:
            fallback = memory_service.get_history(user_id=user_id, limit=limit).get("history", [])
            synthesized = []
            for row in fallback:
                if not isinstance(row, dict):
                    continue
                summary = row.get("summary", {}) if isinstance(row.get("summary"), dict) else {}
                query = str(summary.get("query", "")).strip()
                response = str(summary.get("response", "")).strip()
                if not query and not response:
                    continue
                synthesized.append(
                    {
                        "id": f"memory_{len(synthesized)+1}",
                        "sessionId": str(resolved["id"]),
                        "userId": user_id,
                        "message": query,
                        "intent": str(row.get("type", "")),
                        "agent": "memory",
                        "response": {"message": response, "agent": "memory"},
                        "timestamp": str(row.get("timestamp", "")),
                    }
                )
            history = synthesized
        return {"sessionId": str(resolved["id"]), "messages": history}

    resolved_session_id = _resolve_request_session_id(
        request=request,
        explicit_session_id=session_id,
        source="interactions_history",
    )

    if not resolved_session_id:
        raise HTTPException(status_code=400, detail="sessionId is required for guest history retrieval")
    session = session_service.get_session(resolved_session_id)
    history = interaction_service.history_for_session(session_id=str(session["id"]), limit=limit)
    return {"sessionId": str(session["id"]), "messages": history}
