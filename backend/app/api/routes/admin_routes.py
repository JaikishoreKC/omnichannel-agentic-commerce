from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.deps import require_admin
from app.container import (
    admin_activity_service,
    admin_service,
    category_service,
    inventory_service,
    product_service,
    support_service,
    voice_recovery_service,
)
from app.models.schemas import (
    CategoryUpdateRequest,
    CategoryWriteRequest,
    InventoryUpdateRequest,
    ProductWriteRequest,
    SupportTicketUpdateRequest,
    VoiceSettingsUpdateRequest,
    VoiceSuppressionRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return admin_service.stats()


@router.get("/categories")
def categories(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return category_service.list_categories()


@router.get("/categories/records")
def category_records(
    status: str | None = Query(default=None),
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    return category_service.list_category_records(status=status)


@router.post("/categories", status_code=201)
def create_category(
    payload: CategoryWriteRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    category = category_service.create_category(payload.model_dump(exclude_none=True))
    _log_admin_action(
        request=request,
        admin=admin,
        action="category_create",
        resource="category",
        resource_id=str(category["id"]),
        before=None,
        after=category,
    )
    return {"category": category}


@router.put("/categories/{category_id}")
def update_category(
    category_id: str,
    payload: CategoryUpdateRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    before = category_service.get_category(category_id)
    category = category_service.update_category(category_id=category_id, patch=payload.model_dump(exclude_none=True))
    _log_admin_action(
        request=request,
        admin=admin,
        action="category_update",
        resource="category",
        resource_id=str(category["id"]),
        before=before,
        after=category,
    )
    return {"category": category}


@router.delete("/categories/{category_id}", status_code=204, response_class=Response)
def delete_category(
    category_id: str,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> Response:
    before = category_service.get_category(category_id)
    category_service.delete_category(category_id=category_id)
    _log_admin_action(
        request=request,
        admin=admin,
        action="category_delete",
        resource="category",
        resource_id=str(before.get("id", category_id)),
        before=before,
        after=None,
    )
    return Response(status_code=204)


@router.post("/products", status_code=201)
def create_product(
    payload: ProductWriteRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    product = product_service.create_product(payload.model_dump())
    _log_admin_action(
        request=request,
        admin=admin,
        action="product_create",
        resource="product",
        resource_id=str(product["id"]),
        before=None,
        after=product,
    )
    return {"product": product}


@router.put("/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductWriteRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    before = product_service.get_product(product_id=product_id)
    product = product_service.update_product(product_id=product_id, patch=payload.model_dump())
    _log_admin_action(
        request=request,
        admin=admin,
        action="product_update",
        resource="product",
        resource_id=product_id,
        before=before,
        after=product,
    )
    return {"product": product}


@router.delete("/products/{product_id}", status_code=204, response_class=Response)
def delete_product(
    product_id: str,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> Response:
    before = product_service.get_product(product_id=product_id)
    product_service.delete_product(product_id=product_id)
    _log_admin_action(
        request=request,
        admin=admin,
        action="product_delete",
        resource="product",
        resource_id=product_id,
        before=before,
        after=None,
    )
    return Response(status_code=204)


@router.get("/inventory/{variant_id}")
def get_inventory(
    variant_id: str,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    return {"inventory": inventory_service.get_variant_inventory(variant_id=variant_id)}


@router.put("/inventory/{variant_id}")
def update_inventory(
    variant_id: str,
    payload: InventoryUpdateRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    if payload.totalQuantity is None and payload.availableQuantity is None:
        raise HTTPException(status_code=400, detail="Provide at least one inventory field")
    before = inventory_service.get_variant_inventory(variant_id=variant_id)
    inventory = inventory_service.update_variant_inventory(
        variant_id=variant_id,
        total_quantity=payload.totalQuantity,
        available_quantity=payload.availableQuantity,
    )
    _log_admin_action(
        request=request,
        admin=admin,
        action="inventory_update",
        resource="inventory",
        resource_id=variant_id,
        before=before,
        after=inventory,
    )
    return {"inventory": inventory}


@router.get("/support/tickets")
def list_support_tickets(
    status: str | None = Query(default=None),
    userId: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    tickets = support_service.list_tickets(
        user_id=userId,
        session_id=None,
        status=status,
        limit=limit,
    )
    return {"tickets": tickets}


@router.patch("/support/tickets/{ticket_id}")
def update_support_ticket(
    ticket_id: str,
    payload: SupportTicketUpdateRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    try:
        before = support_service.get_ticket(ticket_id=ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Support ticket not found") from exc

    try:
        ticket = support_service.update_ticket(
            ticket_id=ticket_id,
            status=payload.status,
            priority=payload.priority,
            note=payload.note,
            actor="admin",
        )
    except ValueError as exc:
        code = str(exc)
        if code == "ticket_not_found":
            raise HTTPException(status_code=404, detail="Support ticket not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _log_admin_action(
        request=request,
        admin=admin,
        action="support_ticket_update",
        resource="support_ticket",
        resource_id=ticket_id,
        before=before,
        after=ticket,
    )
    return {"ticket": ticket}


@router.get("/activity")
def list_admin_activity(
    limit: int = Query(default=100, ge=1, le=500),
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    return admin_activity_service.list_recent(limit=limit)


@router.get("/voice/settings")
def get_voice_settings(_: dict[str, object] = Depends(require_admin)) -> dict[str, Any]:
    return {"settings": voice_recovery_service.get_settings()}


@router.put("/voice/settings")
def update_voice_settings(
    payload: VoiceSettingsUpdateRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_none=True)
    before = voice_recovery_service.get_settings()
    settings = voice_recovery_service.update_settings(updates)
    _log_admin_action(
        request=request,
        admin=admin,
        action="voice_settings_update",
        resource="voice_settings",
        resource_id="singleton",
        before=before,
        after=settings,
    )
    return {"settings": settings}


@router.post("/voice/process")
def run_voice_recovery_now(_: dict[str, object] = Depends(require_admin)) -> dict[str, Any]:
    return {"result": voice_recovery_service.process_due_work()}


@router.get("/voice/calls")
def list_voice_calls(
    limit: int = 100,
    status: str | None = None,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    return {"calls": voice_recovery_service.list_calls(limit=limit, status=status)}


@router.get("/voice/jobs")
def list_voice_jobs(
    limit: int = 100,
    status: str | None = None,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    return {"jobs": voice_recovery_service.list_jobs(limit=limit, status=status)}


@router.get("/voice/suppressions")
def list_voice_suppressions(_: dict[str, object] = Depends(require_admin)) -> dict[str, Any]:
    return {"suppressions": voice_recovery_service.list_suppressions()}


@router.post("/voice/suppressions")
def create_voice_suppression(
    payload: VoiceSuppressionRequest,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    row = voice_recovery_service.suppress_user(user_id=payload.userId, reason=payload.reason)
    _log_admin_action(
        request=request,
        admin=admin,
        action="voice_suppression_create",
        resource="voice_suppression",
        resource_id=str(payload.userId),
        before=None,
        after=row,
    )
    return {"suppression": row}


@router.delete("/voice/suppressions/{user_id}", status_code=204, response_class=Response)
def delete_voice_suppression(
    user_id: str,
    request: Request,
    admin: dict[str, object] = Depends(require_admin),
) -> Response:
    before = {"userId": user_id}
    voice_recovery_service.unsuppress_user(user_id=user_id)
    _log_admin_action(
        request=request,
        admin=admin,
        action="voice_suppression_delete",
        resource="voice_suppression",
        resource_id=user_id,
        before=before,
        after=None,
    )
    return Response(status_code=204)


@router.get("/voice/alerts")
def list_voice_alerts(
    limit: int = 50,
    severity: str | None = None,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    return {"alerts": voice_recovery_service.list_alerts(limit=limit, severity=severity)}


@router.get("/voice/stats")
def voice_stats(_: dict[str, object] = Depends(require_admin)) -> dict[str, Any]:
    return {"stats": voice_recovery_service.stats()}


def _log_admin_action(
    *,
    request: Request,
    admin: dict[str, object],
    action: str,
    resource: str,
    resource_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    admin_activity_service.record(
        admin_user=admin,
        action=action,
        resource=resource,
        resource_id=resource_id,
        before=before,
        after=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
