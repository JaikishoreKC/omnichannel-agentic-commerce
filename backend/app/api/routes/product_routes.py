from __future__ import annotations

from fastapi import APIRouter, Query

from app.container import product_service

router = APIRouter(prefix="/products", tags=["products"])


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
    return product_service.get_product(product_id=product_id)
