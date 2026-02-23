from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.container import session_service
from app.models.schemas import CreateSessionRequest

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201)
def create_session(payload: CreateSessionRequest, request: Request) -> dict[str, object]:
    session = session_service.create_session(
        channel=payload.channel,
        initial_context=payload.initialContext,
        anonymous_id=request.headers.get("X-Anonymous-Id"),
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        metadata={
            "source": "session_api",
            "referrer": request.headers.get("referer", ""),
        },
    )
    return {
        "sessionId": session["id"],
        "anonymousId": session.get("anonymousId"),
        "expiresAt": session["expiresAt"],
    }


@router.get("/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    return session_service.get_session(session_id=session_id)


@router.delete("/{session_id}", status_code=204, response_class=Response)
def delete_session(session_id: str) -> Response:
    session_service.delete_session(session_id=session_id)
    return Response(status_code=204)
