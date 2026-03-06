from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import HTTPException

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.inventory_service import InventoryService
from app.store.in_memory import InMemoryStore
from app.core.utils import iso_now


def test_inventory_reserve_concurrent_exceeds_available() -> None:
    store = InMemoryStore()
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=False)
    redis = RedisClientManager(url="redis://localhost:6379/0", enabled=False)
    inventory_repository = InventoryRepository(mongo_manager=mongo, redis_manager=redis, store=store)
    product_repository = ProductRepository(mongo_manager=mongo, redis_manager=redis, store=store)
    service = InventoryService(inventory_repository=inventory_repository, product_repository=product_repository)

    inventory_repository.upsert(
        {
            "variantId": "var_concurrency_1",
            "productId": "prod_concurrency_1",
            "totalQuantity": 5,
            "reservedQuantity": 0,
            "availableQuantity": 5,
            "updatedAt": iso_now(),
        }
    )

    def reserve_three() -> str:
        try:
            service.reserve_for_order([{"variantId": "var_concurrency_1", "quantity": 3}])
            return "ok"
        except HTTPException as exc:
            assert exc.status_code == 409
            return "blocked"

    results: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reserve_three) for _ in range(2)]
        for future in as_completed(futures):
            results.append(future.result())

    assert results.count("ok") == 1
    assert results.count("blocked") == 1

    stock = inventory_repository.get("var_concurrency_1")
    assert stock is not None
    assert int(stock["availableQuantity"]) == 2
    assert int(stock["reservedQuantity"]) == 3
