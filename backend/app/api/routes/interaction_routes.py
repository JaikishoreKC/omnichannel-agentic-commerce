from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi import HTTPException

from app.api.deps import get_optional_user
from app.container import (
    auth_service,
    cart_service,
    interaction_service,
    memory_service,
    orchestrator,
    session_service,
)
from app.models.schemas import InteractionMessageRequest

router = APIRouter(prefix="/interactions", tags=["interactions"])
logger = logging.getLogger(__name__)


@router.post("/message")
async def process_message(
    payload: InteractionMessageRequest,
    request: Request,
    user: dict[str, object] | None = Depends(get_optional_user),
) -> dict[str, object]:
    try:
        session = session_service.get_session(payload.sessionId)
    except HTTPException:
        session = session_service.create_session(
            channel=payload.channel,
            initial_context={},
            anonymous_id=request.headers.get("X-Anonymous-Id"),
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.client.host if request.client else None,
            metadata={
                "source": "interactions_message",
                "referrer": request.headers.get("referer", ""),
            },
        )

    user_id = str(user["id"]) if user else session.get("userId")
    if user_id:
        anonymous_id = str(session.get("anonymousId", "")).strip() or None
        if payload.sessionId:
            cart_service.merge_guest_cart_into_user(session_id=payload.sessionId, user_id=str(user_id))
        session = session_service.resolve_user_session(
            user_id=str(user_id),
            preferred_session_id=session.get("id"),
            channel=payload.channel,
            anonymous_id=anonymous_id,
            user_agent=request.headers.get("User-Agent"),
            ip_address=request.client.host if request.client else None,
            metadata={
                "source": "interactions_message",
                "referrer": request.headers.get("referer", ""),
            },
        )
        try:
            auth_service.link_identity(
                user_id=str(user_id),
                channel=payload.channel,
                external_id=str(session["id"]),
                anonymous_id=str(session.get("anonymousId", "")) or None,
            )
        except Exception as exc:
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
        except Exception as exc:
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

    if not session_id:
        raise HTTPException(status_code=400, detail="sessionId is required for guest history retrieval")
    session = session_service.get_session(session_id)
    history = interaction_service.history_for_session(session_id=str(session["id"]), limit=limit)
    return {"sessionId": str(session["id"]), "messages": history}
