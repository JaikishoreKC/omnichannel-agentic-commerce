from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.core.utils import iso_now


class InventoryService:
    def __init__(
        self,
        inventory_repository: InventoryRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.inventory_repository = inventory_repository
        self.product_repository = product_repository

    def get_variant_inventory(self, variant_id: str) -> dict[str, Any]:
        stock = self.inventory_repository.get(variant_id)
        if not stock:
            raise HTTPException(status_code=404, detail="Inventory variant not found")
        return dict(stock)

    def update_variant_inventory(
        self,
        *,
        variant_id: str,
        total_quantity: int | None = None,
        available_quantity: int | None = None,
    ) -> dict[str, Any]:
        stock = self.inventory_repository.get(variant_id)
        if not stock:
            raise HTTPException(status_code=404, detail="Inventory variant not found")

        if total_quantity is not None:
            stock["totalQuantity"] = max(0, int(total_quantity))
        if available_quantity is not None:
            stock["availableQuantity"] = max(0, int(available_quantity))

        # Keep reservations coherent with totals.
        max_reserved = max(0, stock["totalQuantity"] - stock["availableQuantity"])
        stock["reservedQuantity"] = min(stock["reservedQuantity"], max_reserved)
        stock["updatedAt"] = iso_now()
        self.inventory_repository.upsert(stock)
        self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])
        return dict(stock)

    def reserve_for_order(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Reserve inventory for order creation.

        Returns reservation snapshots used to rollback on payment failure.
        """
        reservations: list[dict[str, Any]] = []
        # Validate all items first.
        for item in items:
            variant_id = item["variantId"]
            quantity = int(item["quantity"])
            stock = self.inventory_repository.get(variant_id)
            if not stock:
                raise HTTPException(
                    status_code=409,
                    detail=f"Inventory not found for variant {variant_id}",
                )
            if stock["availableQuantity"] < quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient inventory for variant {variant_id}",
                )

        # Reserve quantities.
        for item in items:
            variant_id = item["variantId"]
            quantity = int(item["quantity"])
            stock = self.inventory_repository.get(variant_id)
            if not stock:
                raise HTTPException(
                    status_code=409,
                    detail=f"Inventory not found for variant {variant_id}",
                )
            snapshot = {
                "variantId": variant_id,
                "reservedQuantity": stock["reservedQuantity"],
                "availableQuantity": stock["availableQuantity"],
            }
            reservations.append(snapshot)
            stock["reservedQuantity"] += quantity
            stock["availableQuantity"] -= quantity
            stock["updatedAt"] = iso_now()
            self.inventory_repository.upsert(stock)
            self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])

        return reservations

    def commit_reservation(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            variant_id = item["variantId"]
            quantity = int(item["quantity"])
            stock = self.inventory_repository.get(variant_id)
            if not stock:
                continue
            stock["reservedQuantity"] = max(0, stock["reservedQuantity"] - quantity)
            stock["totalQuantity"] = max(0, stock["totalQuantity"] - quantity)
            stock["updatedAt"] = iso_now()
            self.inventory_repository.upsert(stock)
            self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])

    def rollback_reservation(self, snapshots: list[dict[str, Any]]) -> None:
        for snapshot in snapshots:
            variant_id = snapshot["variantId"]
            stock = self.inventory_repository.get(variant_id)
            if not stock:
                continue
            stock["reservedQuantity"] = snapshot["reservedQuantity"]
            stock["availableQuantity"] = snapshot["availableQuantity"]
            stock["updatedAt"] = iso_now()
            self.inventory_repository.upsert(stock)
            self._sync_variant_stock_flag(variant_id=variant_id, available=stock["availableQuantity"])

    def _sync_variant_stock_flag(self, *, variant_id: str, available: int) -> None:
        self.product_repository.set_variant_stock_flag(variant_id=variant_id, in_stock=available > 0)
