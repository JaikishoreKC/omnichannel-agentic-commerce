from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.deps import (
    get_current_user,
    get_support_service,
    resolve_session_id,
)
from app.models.schemas import SupportTicketCreateRequest, SupportTicketCustomerUpdateRequest

router = APIRouter(prefix="/support", tags=["support"])
support_service = get_support_service()


@router.get("/tickets")
def list_my_tickets(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    tickets = support_service.list_tickets(
        user_id=str(user["id"]),
        session_id=None,
        status=status,
        limit=limit,
    )
    return {"tickets": tickets}


@router.post("/tickets", status_code=201)
def create_ticket(
    payload: SupportTicketCreateRequest,
    request: Request,
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    session_id = resolve_session_id(request=request, response=response)
    ticket = support_service.create_ticket(
        user_id=str(user["id"]),
        session_id=session_id,
        issue=payload.issue,
        priority=payload.priority,
        category=payload.category,
        channel=payload.channel,
    )
    return {"ticket": ticket}


@router.patch("/tickets/{ticket_id}")
def update_my_ticket(
    ticket_id: str,
    payload: SupportTicketCustomerUpdateRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        ticket = support_service.get_ticket(ticket_id=ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Support ticket not found") from exc

    if str(ticket.get("userId") or "") != str(user["id"]):
        raise HTTPException(status_code=403, detail="You do not have access to this ticket")

    status = payload.status
    if status is not None and str(status).strip().lower() not in {"open", "in_progress", "resolved", "closed"}:
        raise HTTPException(status_code=400, detail="Invalid support ticket status")

    updated = support_service.update_ticket(
        ticket_id=ticket_id,
        status=status,
        note=payload.note,
        actor="customer",
    )
    return {"ticket": updated}
