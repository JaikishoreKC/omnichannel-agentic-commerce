from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.repositories.cart_repository import CartRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.order_repository import OrderRepository
from app.store.in_memory import InMemoryStore


def _disabled_managers() -> tuple[MongoClientManager, RedisClientManager]:
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=False)
    redis = RedisClientManager(url="redis://localhost:6379/0", enabled=False)
    return mongo, redis


def test_cart_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _disabled_managers()
    repo = CartRepository(store=store, mongo_manager=mongo_manager, redis_manager=redis_manager)

    cart = {
        "id": "cart_test_1",
        "userId": None,
        "sessionId": "session_test_1",
        "items": [],
        "subtotal": 0.0,
        "tax": 0.0,
        "shipping": 0.0,
        "discount": 0.0,
        "total": 0.0,
        "itemCount": 0,
        "currency": "USD",
        "appliedDiscount": None,
        "createdAt": store.iso_now(),
        "updatedAt": store.iso_now(),
    }

    repo.create(cart)
    loaded = repo.get_for_user_or_session(user_id=None, session_id="session_test_1")
    assert loaded is not None
    assert loaded["id"] == "cart_test_1"

    loaded["userId"] = "user_test_1"
    repo.update(loaded)
    by_user = repo.get_for_user_or_session(user_id="user_test_1", session_id="")
    assert by_user is not None
    assert by_user["id"] == "cart_test_1"


def test_order_repository_roundtrip_and_idempotency() -> None:
    store = InMemoryStore()
    mongo_manager, _ = _disabled_managers()
    repo = OrderRepository(store=store, mongo_manager=mongo_manager)

    order = {
        "id": "order_test_1",
        "userId": "user_test_1",
        "status": "confirmed",
        "items": [],
        "subtotal": 0.0,
        "tax": 0.0,
        "shipping": 0.0,
        "discount": 0.0,
        "total": 0.0,
        "shippingAddress": {},
        "payment": {},
        "timeline": [],
        "tracking": {"updates": []},
        "estimatedDelivery": store.iso_now(),
        "createdAt": store.iso_now(),
        "updatedAt": store.iso_now(),
    }

    repo.create(order)
    loaded = repo.get("order_test_1")
    assert loaded is not None
    assert loaded["userId"] == "user_test_1"

    listed = repo.list_by_user("user_test_1")
    assert len(listed) == 1
    assert listed[0]["id"] == "order_test_1"

    repo.set_idempotent(key="user_test_1:key_1", order_id="order_test_1")
    assert repo.get_idempotent("user_test_1:key_1") == "order_test_1"


def test_memory_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _disabled_managers()
    repo = MemoryRepository(store=store, mongo_manager=mongo_manager, redis_manager=redis_manager)

    payload = {
        "preferences": {"size": "M", "brandPreferences": ["Nike"], "categories": ["shoes"], "priceRange": {"min": 50, "max": 200}},
        "interactionHistory": [],
        "productAffinities": {"categories": {"shoes": 2}, "products": {"prod_001": 1}},
        "updatedAt": store.iso_now(),
    }
    repo.upsert("user_test_2", payload)

    loaded = repo.get("user_test_2")
    assert loaded is not None
    assert loaded["preferences"]["size"] == "M"
    assert loaded["productAffinities"]["categories"]["shoes"] == 2
