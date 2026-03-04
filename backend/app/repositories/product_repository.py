from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
class ProductRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def list_all(self) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({}).sort("name", 1))
        products: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("productId", None)
            if isinstance(row, dict):
                products.append(row)
                self._write_to_redis(row)
        return products

    def get(self, product_id: str) -> dict[str, Any] | None:
        cached = self._read_from_redis(product_id)
        if cached is not None:
            return cached

        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one({"productId": product_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("productId", None)
        if not isinstance(payload, dict):
            return None
        self._write_to_redis(payload)
        return payload

    # Alias for get_by_id - used by product_service
    def get_by_id(self, product_id: str) -> dict[str, Any] | None:
        return self.get(product_id)

    def create(self, product: dict[str, Any]) -> dict[str, Any]:
        self._write_to_redis(product)
        self._write_to_mongo(product)
        return deepcopy(product)

    def update(self, *args: Any) -> dict[str, Any]:
        if len(args) == 1 and isinstance(args[0], dict):
            product = args[0]
        elif len(args) == 2 and isinstance(args[1], dict):
            product = args[1]
        else:
            raise TypeError("update expects update(product) or update(product_id, product)")
        self._write_to_redis(product)
        self._write_to_mongo(product)
        return deepcopy(product)

    def delete(self, product_id: str) -> None:
        self._delete_from_redis(product_id)
        self._delete_from_mongo(product_id)

    def list_categories(self) -> list[str]:
        collection = self._mongo_collection()
        if collection is None:
            return []
        categories = sorted(collection.distinct("category"))
        return [str(c).strip() for c in categories if c]

    def set_variant_stock_flag(self, *, variant_id: str, in_stock: bool) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
            
        # Update in Mongo
        result = collection.update_one(
            {"variants.id": variant_id},
            {"$set": {"variants.$.inStock": in_stock}}
        )
        
        if result.matched_count > 0:
            # Refresh Redis cache for this product
            updated_product = collection.find_one({"variants.id": variant_id})
            if updated_product:
                updated_product.pop("_id", None)
                updated_product.pop("productId", None)
                self._write_to_redis(updated_product)

    def name_map(self) -> dict[str, str]:
        products = self.list_all()
        return {str(product["id"]): str(product.get("name", "Unknown")) for product in products if product.get("id")}

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["products"]

    def _redis_key(self, product_id: str) -> str:
        return f"product:{product_id}"

    def _write_to_redis(self, product: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(str(product["id"])), json.dumps(product), ex=60 * 60)

    def _read_from_redis(self, product_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(product_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _delete_from_redis(self, product_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(product_id))

    def _write_to_mongo(self, product: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"productId": product["id"]},
            {"$set": {"productId": product["id"], **deepcopy(product)}},
            upsert=True,
        )

    def _delete_from_mongo(self, product_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"productId": product_id})
