from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any

from fastapi import HTTPException

from app.repositories.category_repository import CategoryRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.core.utils import generate_id, iso_now


class ProductService:
    def __init__(
        self,
        product_repository: ProductRepository,
        category_repository: CategoryRepository,
        inventory_repository: InventoryRepository,
    ) -> None:
        self.product_repository = product_repository
        self.category_repository = category_repository
        self.inventory_repository = inventory_repository
        self._search_index_lock = Lock()
        self._search_index_cache: dict[str, Any] = {
            "key": None,
            "products": [],
            "corpus": [],
            "vectorizer": None,
            "matrix": None,
            "enabled": False,
        }

    def list_products(
        self,
        query: str | None,
        category: str | None,
        brand: str | None,
        min_price: float | None,
        max_price: float | None,
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        normalized_query = (query or "").strip().lower()
        normalized_category = (category or "").strip().lower()
        normalized_brand = (brand or "").strip().lower()
        safe_page = max(1, page)
        safe_limit = min(100, max(1, limit))

        products = self.product_repository.list_all()

        # Phase 1: Hard Filtering (Category, Brand, Price, Status)
        def hard_filter(item: dict[str, Any]) -> bool:
            status = str(item.get("status", "active")).strip().lower()
            if status not in {"active"}:
                return False
            if normalized_category and normalized_category != "all" and str(item["category"]).lower() != normalized_category:
                return False
            if normalized_brand and str(item.get("brand", "")).lower() != normalized_brand:
                return False
            if min_price is not None and item["price"] < min_price:
                return False
            if max_price is not None and item["price"] > max_price:
                return False
            return True

        candidates = [item for item in products if hard_filter(item)]

        if not candidates:
            return {
                "products": [],
                "pagination": {
                    "page": safe_page,
                    "limit": safe_limit,
                    "total": 0,
                    "pages": 0,
                },
            }

        # Phase 2: Search (Semantic vs Basic)
        if normalized_query:
            ranked = self._semantic_rank_products(query=normalized_query, products=candidates)
            if ranked is not None:
                filtered = ranked
            else:
                # Fallback to basic search if scikit-learn fails
                def basic_match(item: dict[str, Any]) -> bool:
                    haystack = f"{item['name']} {item.get('description', '')} {item.get('brand', '')}".lower()
                    return normalized_query in haystack
                filtered = [item for item in candidates if basic_match(item)]
        else:
            filtered = candidates

        total = len(filtered)
        start = (safe_page - 1) * safe_limit
        end = start + safe_limit
        page_items = filtered[start:end]

        return {
            "products": page_items,
            "pagination": {
                "page": safe_page,
                "limit": safe_limit,
                "total": total,
                "pages": (total + safe_limit - 1) // safe_limit if total else 0,
            },
        }

    def _semantic_rank_products(self, *, query: str, products: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except Exception:
            return None

        index = self._build_or_get_search_index(products=products, vectorizer_cls=TfidfVectorizer)
        if not index.get("enabled"):
            return None

        vectorizer = index.get("vectorizer")
        matrix = index.get("matrix")
        corpus = index.get("corpus", [])
        indexed_products = index.get("products", [])
        if vectorizer is None or matrix is None or not indexed_products:
            return None

        query_vec = vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, matrix).flatten()
        scored: list[tuple[float, dict[str, Any]]] = []
        for idx, score in enumerate(similarities):
            if idx >= len(indexed_products):
                continue
            if score > 0.0 or query in str(corpus[idx]):
                scored.append((float(score), indexed_products[idx]))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored]

    def _build_or_get_search_index(self, *, products: list[dict[str, Any]], vectorizer_cls: Any) -> dict[str, Any]:
        key = self._search_index_key(products)
        cached_key = self._search_index_cache.get("key")
        if cached_key == key:
            return self._search_index_cache

        with self._search_index_lock:
            cached_key = self._search_index_cache.get("key")
            if cached_key == key:
                return self._search_index_cache

            corpus = [self._search_text(item) for item in products]
            try:
                vectorizer = vectorizer_cls(stop_words="english")
                matrix = vectorizer.fit_transform(corpus)
                self._search_index_cache = {
                    "key": key,
                    "products": products,
                    "corpus": corpus,
                    "vectorizer": vectorizer,
                    "matrix": matrix,
                    "enabled": True,
                }
            except Exception:
                self._search_index_cache = {
                    "key": key,
                    "products": products,
                    "corpus": corpus,
                    "vectorizer": None,
                    "matrix": None,
                    "enabled": False,
                }
            return self._search_index_cache

    @staticmethod
    def _search_text(item: dict[str, Any]) -> str:
        tags = item.get("tags", [])
        features = item.get("features", [])
        tag_text = " ".join(str(token) for token in tags) if isinstance(tags, list) else ""
        feature_text = " ".join(str(token) for token in features) if isinstance(features, list) else ""
        return f"{item['name']} {item['description']} {item.get('brand', '')} {tag_text} {feature_text}".lower()

    @staticmethod
    def _search_index_key(products: list[dict[str, Any]]) -> tuple[int, tuple[tuple[str, str], ...]]:
        signature = tuple(
            sorted(
                (
                    str(item.get("id", "")),
                    str(item.get("updatedAt", "")),
                )
                for item in products
            )
        )
        return (len(products), signature)

    def get_product(self, product_id: str) -> dict[str, Any]:
        product = self.product_repository.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"product": product}

    def add_review(
        self, product_id: str, user_id: str, rating: int, title: str | None, comment: str | None
    ) -> dict[str, Any]:
        product = self.product_repository.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
            
        review = {
            "id": generate_id("review"),
            "userId": user_id,
            "rating": rating,
            "title": title,
            "comment": comment,
            "createdAt": iso_now(),
        }
        
        reviews = product.get("reviews", [])
        reviews.append(review)
        product["reviews"] = reviews
        
        total_rating = sum(r["rating"] for r in reviews)
        new_rating = total_rating / len(reviews)
        new_review_count = len(reviews)
        
        # Depending on if update takes partial dict or full dict. Assuming memory repo uses merge or full replace.
        # We will pass full product
        product["rating"] = new_rating
        product["reviewCount"] = new_review_count
        product["updatedAt"] = iso_now()
        
        self.product_repository.update(product)
        
        return {"review": review, "product": product}

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        product_id = payload.get("id") or generate_id("prod")
        if self.product_repository.get(product_id):
            raise HTTPException(status_code=409, detail="Product ID already exists")
        category = str(payload["category"]).strip().lower()
        self._assert_active_category(category)

        product = {
            "id": product_id,
            "name": payload["name"],
            "description": payload.get("description", ""),
            "category": category,
            "subcategory": str(payload.get("subcategory", "")).strip().lower(),
            "brand": str(payload.get("brand", "Generic")).strip(),
            "price": float(payload["price"]),
            "currency": payload.get("currency", "USD"),
            "images": list(payload.get("images", [])),
            "variants": deepcopy(payload.get("variants", [])),
            "rating": float(payload.get("rating", 0.0)),
            "reviewCount": int(payload.get("reviewCount", 0)),
            "tags": list(payload.get("tags", [])),
            "features": list(payload.get("features", [])),
            "specifications": deepcopy(payload.get("specifications", {})),
            "status": str(payload.get("status", "active")).strip().lower(),
            "createdAt": iso_now(),
            "updatedAt": iso_now(),
        }
        if product["status"] not in {"active", "draft", "archived"}:
            raise HTTPException(status_code=400, detail="Invalid product status")
        self._sync_variant_inventory(product_id=product_id, variants=product["variants"], replace_existing=False)
        self.product_repository.create(product)

        return deepcopy(product)

    def update_product(self, product_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        product = self.product_repository.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        for key in (
            "name",
            "description",
            "category",
            "subcategory",
            "brand",
            "price",
            "currency",
            "images",
            "rating",
            "reviewCount",
            "tags",
            "features",
            "specifications",
            "status",
        ):
            if key in patch and patch[key] is not None:
                value = patch[key]
                if key == "price":
                    value = float(value)
                elif key == "reviewCount":
                    value = int(value)
                elif key == "rating":
                    value = float(value)
                elif key == "images":
                    value = list(value)
                elif key in {"tags", "features"}:
                    value = list(value)
                elif key == "category":
                    value = str(value).strip().lower()
                    self._assert_active_category(value)
                elif key == "subcategory":
                    value = str(value).strip().lower()
                elif key == "status":
                    value = str(value).strip().lower()
                    if value not in {"active", "draft", "archived"}:
                        raise HTTPException(status_code=400, detail="Invalid product status")
                product[key] = value
        if "variants" in patch and patch["variants"] is not None:
            product["variants"] = deepcopy(patch["variants"])
            self._sync_variant_inventory(
                product_id=product_id,
                variants=product["variants"],
                replace_existing=True,
            )
        product["updatedAt"] = iso_now()
        self.product_repository.update(product)
        return deepcopy(product)

    def delete_product(self, product_id: str) -> None:
        product = self.product_repository.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        for variant in product.get("variants", []):
            variant_id = str(variant.get("id", ""))
            if variant_id:
                self.inventory_repository.delete(variant_id)
        self.product_repository.delete(product_id)

    def list_categories(self) -> dict[str, Any]:
        rows = self.category_repository.list_all()
        categories = sorted(
            {
                str(row.get("slug", "")).strip().lower()
                for row in rows
                if str(row.get("status", "active")).strip().lower() == "active"
            }
        )
        if not categories:
            categories = self.product_repository.list_categories()
        return {"categories": categories}

    def _sync_variant_inventory(
        self,
        *,
        product_id: str,
        variants: list[dict[str, Any]],
        replace_existing: bool,
    ) -> None:
        incoming_ids = {variant["id"] for variant in variants}
        if replace_existing:
            existing_rows = self.inventory_repository.list_by_product(product_id)
            to_delete = [str(stock["variantId"]) for stock in existing_rows if stock["variantId"] not in incoming_ids]
            for variant_id in to_delete:
                self.inventory_repository.delete(variant_id)

        for variant in variants:
            variant_id = variant["id"]
            inventory = variant.get("inventory") or {}
            existing = self.inventory_repository.get(variant_id)
            if existing:
                total_quantity = int(inventory.get("totalQuantity", existing["totalQuantity"]))
                available_quantity = int(
                    inventory.get("availableQuantity", existing["availableQuantity"])
                )
                reserved_quantity = int(existing.get("reservedQuantity", 0))
            else:
                available_quantity = int(inventory.get("availableQuantity", 10))
                total_quantity = int(inventory.get("totalQuantity", available_quantity))
                reserved_quantity = 0
            total_quantity = max(0, total_quantity)
            reserved_quantity = max(0, min(reserved_quantity, total_quantity))
            available_quantity = max(0, min(available_quantity, total_quantity - reserved_quantity))

            self.inventory_repository.upsert(
                {
                    "variantId": variant_id,
                    "productId": product_id,
                    "totalQuantity": total_quantity,
                    "reservedQuantity": reserved_quantity,
                    "availableQuantity": available_quantity,
                    "updatedAt": iso_now(),
                }
            )
            variant["inStock"] = available_quantity > 0

    def _assert_active_category(self, category_slug: str) -> None:
        category = self.category_repository.get(category_slug)
        if not category:
            raise HTTPException(status_code=400, detail=f"Unknown category: {category_slug}")
        status = str(category.get("status", "active")).strip().lower()
        if status != "active":
            raise HTTPException(status_code=409, detail=f"Category is not active: {category_slug}")
