from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from app.repositories.category_repository import CategoryRepository
from app.repositories.product_repository import ProductRepository
from app.store.in_memory import InMemoryStore


class CategoryService:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        category_repository: CategoryRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.store = store
        self.category_repository = category_repository
        self.product_repository = product_repository

    def list_categories(self) -> dict[str, Any]:
        rows = self.category_repository.list_all()
        active = sorted(
            {
                str(row.get("slug", "")).strip().lower()
                for row in rows
                if str(row.get("status", "active")).strip().lower() == "active"
                and str(row.get("slug", "")).strip()
            }
        )
        return {"categories": active}

    def list_category_records(self, *, status: str | None = None) -> dict[str, Any]:
        rows = self.category_repository.list_all()
        filtered = rows
        if status is not None:
            normalized = status.strip().lower()
            filtered = [
                row
                for row in rows
                if str(row.get("status", "active")).strip().lower() == normalized
            ]
        filtered.sort(key=lambda row: str(row.get("name", "")).lower())
        return {"categories": deepcopy(filtered)}

    def get_category(self, category_id: str) -> dict[str, Any]:
        row = self.category_repository.get(category_id)
        if not row:
            raise HTTPException(status_code=404, detail="Category not found")
        return deepcopy(row)

    def create_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = self.store.iso_now()
        requested_slug = payload.get("slug") or payload.get("id") or payload.get("name")
        slug = self._slugify(requested_slug)
        if not slug:
            raise HTTPException(status_code=400, detail="Category slug is required")
        if self.category_repository.get(slug):
            raise HTTPException(status_code=409, detail="Category already exists")

        row = {
            "id": str(payload.get("id") or slug).strip(),
            "slug": slug,
            "name": str(payload.get("name") or slug.replace("-", " ").title()).strip(),
            "description": str(payload.get("description", "")).strip(),
            "status": self._normalize_status(payload.get("status"), default="active"),
            "createdAt": now,
            "updatedAt": now,
        }
        self.category_repository.create(row)
        return deepcopy(row)

    def update_category(self, category_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        existing = self.category_repository.get(category_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Category not found")

        next_slug = self._slugify(patch.get("slug") or existing["slug"])
        if not next_slug:
            raise HTTPException(status_code=400, detail="Category slug is required")
        if next_slug != str(existing.get("slug", "")):
            collision = self.category_repository.get(next_slug)
            if collision:
                raise HTTPException(status_code=409, detail="Category slug already exists")

        if next_slug != str(existing.get("slug", "")):
            active_products = [
                product
                for product in self.product_repository.list_all()
                if str(product.get("category", "")).strip().lower()
                == str(existing.get("slug", "")).strip().lower()
            ]
            for product in active_products:
                product["category"] = next_slug
                self.product_repository.update(product)

        if patch.get("name") is not None:
            existing["name"] = str(patch["name"]).strip() or existing["name"]
        if patch.get("description") is not None:
            existing["description"] = str(patch["description"]).strip()
        if patch.get("status") is not None:
            existing["status"] = self._normalize_status(patch["status"], default=existing["status"])
        existing["slug"] = next_slug
        existing["updatedAt"] = self.store.iso_now()
        self.category_repository.update(existing)
        return deepcopy(existing)

    def delete_category(self, category_id: str) -> None:
        existing = self.category_repository.get(category_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Category not found")
        slug = str(existing.get("slug", "")).strip().lower()
        in_use = [
            product
            for product in self.product_repository.list_all()
            if str(product.get("category", "")).strip().lower() == slug
        ]
        if in_use:
            raise HTTPException(
                status_code=409,
                detail="Category is still referenced by products",
            )
        self.category_repository.delete(slug or category_id)

    def assert_category_active(self, category_slug: str) -> None:
        normalized = self._slugify(category_slug)
        if not normalized:
            raise HTTPException(status_code=400, detail="Category is required")
        row = self.category_repository.get(normalized)
        if not row:
            raise HTTPException(status_code=400, detail=f"Unknown category: {normalized}")
        status = str(row.get("status", "active")).strip().lower()
        if status != "active":
            raise HTTPException(status_code=409, detail=f"Category is not active: {normalized}")

    @staticmethod
    def _normalize_status(value: Any, *, default: str) -> str:
        normalized = str(value or default).strip().lower()
        if normalized not in {"active", "draft", "archived"}:
            raise HTTPException(status_code=400, detail="Invalid category status")
        return normalized

    @staticmethod
    def _slugify(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"\s+", "-", text)
        text = re.sub(r"-{2,}", "-", text)
        return text.strip("-")
