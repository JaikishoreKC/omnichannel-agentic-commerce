from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import get_product_service

router = APIRouter(prefix="/products", tags=["products"])
product_service = get_product_service()


@router.get("")
def list_products(
    query: str | None = Query(default=None),
    category: str | None = Query(default=None),
    brand: str | None = Query(default=None),
    minPrice: float | None = Query(default=None),
    maxPrice: float | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    return product_service.list_products(
        query=query,
        category=category,
        brand=brand,
        min_price=minPrice,
        max_price=maxPrice,
        page=page,
        limit=limit,
    )


@router.get("/{product_id}")
def get_product(product_id: str) -> dict[str, object]:
    result = product_service.get_product(product_id=product_id)
    product = result.get("product") if isinstance(result, dict) else None
    if isinstance(product, dict):
        return product
    return result


from app.models.schemas import AddProductReviewRequest
from app.api.deps import get_current_user
from fastapi import Depends

@router.post("/{product_id}/reviews", status_code=201)
def add_product_review(
    product_id: str,
    payload: AddProductReviewRequest,
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return product_service.add_review(
        product_id=product_id,
        user_id=str(user["id"]),
        rating=payload.rating,
        title=payload.title,
        comment=payload.comment,
    )
