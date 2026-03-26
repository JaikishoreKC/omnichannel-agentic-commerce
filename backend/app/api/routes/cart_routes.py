from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_cart_service, get_optional_user, resolve_session_id
from app.models.schemas import (
    AddCartItemRequest,
    ApplyDiscountRequest,
    UpdateCartItemRequest,
)

router = APIRouter(prefix="/cart", tags=["cart"])
cart_service = get_cart_service()


@router.get("")
def get_cart(
    response: Response,
    user: dict[str, object] | None = Depends(get_optional_user),
    session_id: str = Depends(resolve_session_id),
) -> dict[str, object]:
    user_id = str(user["id"]) if user else None
    return cart_service.get_cart(user_id=user_id, session_id=session_id)


@router.post("/items", status_code=201)
def add_cart_item(
    payload: AddCartItemRequest,
    response: Response,
    user: dict[str, object] | None = Depends(get_optional_user),
    session_id: str = Depends(resolve_session_id),
) -> dict[str, object]:
    user_id = str(user["id"]) if user else None
    cart = cart_service.add_item(
        user_id=user_id,
        session_id=session_id,
        product_id=payload.productId,
        variant_id=payload.variantId,
        quantity=payload.quantity,
    )
    return cart


@router.put("/items/{item_id}")
def update_cart_item(
    item_id: str,
    payload: UpdateCartItemRequest,
    response: Response,
    user: dict[str, object] | None = Depends(get_optional_user),
    session_id: str = Depends(resolve_session_id),
) -> dict[str, object]:
    user_id = str(user["id"]) if user else None
    cart = cart_service.update_item(
        user_id=user_id,
        session_id=session_id,
        item_id=item_id,
        quantity=payload.quantity,
    )
    return cart


@router.delete("/items/{item_id}", status_code=204)
def delete_cart_item(
    item_id: str,
    _: Response,
    user: dict[str, object] | None = Depends(get_optional_user),
    session_id: str = Depends(resolve_session_id),
) -> Response:
    user_id = str(user["id"]) if user else None
    cart_service.remove_item(user_id=user_id, session_id=session_id, item_id=item_id)
    return Response(status_code=204)


@router.post("/apply-discount")
def apply_discount(
    payload: ApplyDiscountRequest,
    response: Response,
    user: dict[str, object] | None = Depends(get_optional_user),
    session_id: str = Depends(resolve_session_id),
) -> dict[str, object]:
    user_id = str(user["id"]) if user else None
    cart = cart_service.apply_discount(
        user_id=user_id,
        session_id=session_id,
        discount_code=payload.code,
    )
    return cart
