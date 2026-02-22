from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import require_admin
from app.container import admin_service, inventory_service, product_service, voice_recovery_service
from app.models.schemas import (
    InventoryUpdateRequest,
    ProductWriteRequest,
    VoiceSettingsUpdateRequest,
    VoiceSuppressionRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return admin_service.stats()


@router.get("/categories")
def categories(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return product_service.list_categories()


@router.post("/products", status_code=201)
def create_product(
    payload: ProductWriteRequest,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    product = product_service.create_product(payload.model_dump())
    return {"product": product}


@router.put("/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductWriteRequest,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    product = product_service.update_product(product_id=product_id, patch=payload.model_dump())
    return {"product": product}


@router.delete("/products/{product_id}", status_code=204, response_class=Response)
def delete_product(product_id: str, _: dict[str, object] = Depends(require_admin)) -> Response:
    product_service.delete_product(product_id=product_id)
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
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    if payload.totalQuantity is None and payload.availableQuantity is None:
        raise HTTPException(status_code=400, detail="Provide at least one inventory field")
    inventory = inventory_service.update_variant_inventory(
        variant_id=variant_id,
        total_quantity=payload.totalQuantity,
        available_quantity=payload.availableQuantity,
    )
    return {"inventory": inventory}


@router.get("/voice/settings")
def get_voice_settings(_: dict[str, object] = Depends(require_admin)) -> dict[str, Any]:
    return {"settings": voice_recovery_service.get_settings()}


@router.put("/voice/settings")
def update_voice_settings(
    payload: VoiceSettingsUpdateRequest,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    updates = payload.model_dump(exclude_none=True)
    return {"settings": voice_recovery_service.update_settings(updates)}


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
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, Any]:
    row = voice_recovery_service.suppress_user(user_id=payload.userId, reason=payload.reason)
    return {"suppression": row}


@router.delete("/voice/suppressions/{user_id}", status_code=204, response_class=Response)
def delete_voice_suppression(
    user_id: str,
    _: dict[str, object] = Depends(require_admin),
) -> Response:
    voice_recovery_service.unsuppress_user(user_id=user_id)
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
