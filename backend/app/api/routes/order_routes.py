from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.deps import get_current_user, get_order_service
from app.models.schemas import (
    CancelOrderRequest,
    CreateOrderRequest,
    RefundOrderRequest,
    UpdateOrderAddressRequest,
)

router = APIRouter(prefix="/orders", tags=["orders"])
order_service = get_order_service()


@router.post("", status_code=201)
def create_order(
    payload: CreateOrderRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")
    order = order_service.create_order(
        user_id=str(user["id"]),
        shipping_address=payload.shippingAddress.model_dump(),
        payment_method=payload.paymentMethod.model_dump(),
        idempotency_key=idempotency_key,
    )
    return {"order": order}


@router.get("")
def list_orders(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return order_service.list_orders(user_id=str(user["id"]))


@router.get("/{order_id}")
def get_order(
    order_id: str, user: dict[str, object] = Depends(get_current_user)
) -> dict[str, object]:
    return order_service.get_order(user_id=str(user["id"]), order_id=order_id)


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: str,
    payload: CancelOrderRequest,
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return order_service.cancel_order(
        user_id=str(user["id"]),
        order_id=order_id,
        reason=payload.reason,
    )


@router.post("/{order_id}/refund")
def refund_order(
    order_id: str,
    payload: RefundOrderRequest,
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return order_service.request_refund(
        user_id=str(user["id"]),
        order_id=order_id,
        reason=payload.reason,
    )


@router.put("/{order_id}/shipping-address")
def update_order_shipping_address(
    order_id: str,
    payload: UpdateOrderAddressRequest,
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return order_service.update_shipping_address(
        user_id=str(user["id"]),
        order_id=order_id,
        shipping_address=payload.shippingAddress.model_dump(),
    )
