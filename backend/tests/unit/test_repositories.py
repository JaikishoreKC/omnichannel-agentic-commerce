import json
from copy import deepcopy
from typing import Any
from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.repositories.auth_repository import AuthRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.admin_activity_repository import AdminActivityRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.interaction_repository import InteractionRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.support_repository import SupportRepository
from app.store.in_memory import InMemoryStore
from app.services.session_service import SessionService

class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value

    def get(self, key: str) -> Any:
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def scan_iter(self, match: str = "*") -> Any:
        prefix = match.replace("*", "")
        for k in self.store:
            if k.startswith(prefix):
                yield k

    def flushall(self) -> None:
        self.store.clear()

class _FakeMongoCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    def find(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> Any:
        def match_doc(doc, f):
            if not f: return True
            for k, v in f.items():
                if k == "$or":
                    if not any(match_doc(doc, cond) for cond in v): return False
                elif k == "$and":
                    if not all(match_doc(doc, cond) for cond in v): return False
                else:
                    actual_val = None
                    exists = False
                    if "." in k:
                        parts = k.split(".")
                        curr = [doc]
                        for p in parts:
                            next_curr = []
                            for item in curr:
                                if isinstance(item, dict):
                                    if p in item:
                                        next_curr.append(item[p])
                                        exists = True
                                elif isinstance(item, list):
                                    for sub in item:
                                        if isinstance(sub, dict) and p in sub:
                                            next_curr.append(sub[p])
                                            exists = True
                            curr = next_curr
                        actual_val = curr
                    else:
                        actual_val = doc.get(k)
                        exists = k in doc
                    
                    if isinstance(v, dict) and "$exists" in v:
                        if v["$exists"] != exists: return False
                    elif isinstance(v, dict) and "$ne" in v:
                        if actual_val == v["$ne"]: return False
                    elif isinstance(v, dict) and "$regex" in v:
                        import re
                        if not re.search(str(v["$regex"]), str(actual_val)): return False
                    elif "." in k:
                        if v not in actual_val: return False
                    else:
                        if actual_val != v: return False
            return True

        results = [deepcopy(doc) for doc in self.docs if match_doc(doc, filter)]
        
        class FakeCursor(list):
            def sort(self, *args: Any, **kwargs: Any) -> "FakeCursor":
                if args:
                    if isinstance(args[0], list):
                        for field, direction in reversed(args[0]):
                            super().sort(key=lambda x: x.get(field), reverse=(direction == -1))
                    elif len(args) >= 2:
                        field, direction = args[0], args[1]
                        super().sort(key=lambda x: x.get(str(field)), reverse=(direction == -1))
                else:
                    super().sort(**kwargs)
                return self
            def limit(self, n: int) -> "FakeCursor":
                return FakeCursor(self[:n])
        return FakeCursor(results)

    def find_one(self, filter: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        if filter is None:
            filter = {}
        res = self.find(filter)
        sort = kwargs.get("sort")
        if sort:
            # Very basic sort for the fake
            for field, direction in reversed(sort):
                res.sort(key=lambda x: x.get(field), reverse=(direction == -1))
        return res[0] if res else None

    def update_one(self, filter: dict[str, Any], update: dict[str, Any], upsert: bool = False) -> Any:
        def match_doc(doc, f):
            if not f: return True
            for k, v in f.items():
                if "." in k:
                    parts = k.split(".")
                    curr = [doc]
                    for p in parts:
                        next_curr = []
                        for item in curr:
                            if isinstance(item, dict):
                                if p in item: next_curr.append(item[p])
                            elif isinstance(item, list):
                                for sub in item:
                                    if isinstance(sub, dict) and p in sub: next_curr.append(sub[p])
                        curr = next_curr
                    if v not in curr: return False
                elif doc.get(k) != v: return False
            return True

        matched_idx = -1
        for i, d in enumerate(self.docs):
            if match_doc(d, filter):
                matched_idx = i
                break
        
        if matched_idx == -1:
            if upsert:
                new_doc = {}
                for k, v in filter.items():
                    if not k.startswith("$") and "." not in k: new_doc[k] = v
                if "$set" in update: new_doc.update(deepcopy(update["$set"]))
                self.docs.append(new_doc)
                class Result: matched_count = 0; upserted_id = "new"
                return Result()
            class Result: matched_count = 0; upserted_id = None
            return Result()
            
        doc = self.docs[matched_idx]
        if "$set" in update:
            for k, v in update["$set"].items():
                if ".$.inStock" in k:
                    prefix = k.split(".$.")[0]
                    attr = k.split(".$.")[1]
                    var_id = filter.get("variants.id")
                    for var in doc.get(prefix, []):
                        if var.get("id") == var_id:
                            var[attr] = v
                            break
                elif "." in k:
                    parts = k.split(".")
                    curr = doc
                    for p in parts[:-1]:
                        if p not in curr: curr[p] = {}
                        curr = curr[p]
                    curr[parts[-1]] = v
                else:
                    doc[k] = v
        
        class Result: matched_count = 1; upserted_id = None
        return Result()

    def delete_one(self, filter: dict[str, Any]) -> Any:
        doc = self.find_one(filter)
        if doc:
            for i, d in enumerate(self.docs):
                if d == doc:
                    self.docs.pop(i)
                    break
        class Result: deleted_count = 1 if doc else 0
        return Result()

    def distinct(self, key: str) -> list[Any]:
        return list(set(d.get(key) for d in self.docs if d.get(key) is not None))

class _FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, _FakeMongoCollection] = {}

    def __getitem__(self, name: str) -> _FakeMongoCollection:
        if name not in self.collections:
            self.collections[name] = _FakeMongoCollection()
        return self.collections[name]

class _FakeMongoClient:
    def __init__(self) -> None:
        self.databases: dict[str, _FakeDatabase] = {}

    def get_default_database(self) -> _FakeDatabase:
        return self["commerce"]

    def __getitem__(self, name: str) -> _FakeDatabase:
        if name not in self.databases:
            self.databases[name] = _FakeDatabase()
        return self.databases[name]

def _disabled_managers() -> tuple[MongoClientManager, RedisClientManager]:
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=False)
    redis = RedisClientManager(url="redis://localhost:6379/0", enabled=False)
    return mongo, redis

def _fake_managers() -> tuple[MongoClientManager, RedisClientManager]:
    mongo = MongoClientManager(uri="mongodb://localhost:27017/commerce", enabled=True)
    mongo._client = _FakeMongoClient()
    redis = RedisClientManager(url="redis://localhost:6379/0", enabled=True)
    redis._client = _FakeRedisClient()
    return mongo, redis


def test_cart_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = CartRepository(mongo_manager=mongo_manager, redis_manager=redis_manager)

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
    mongo_manager, _ = _fake_managers()
    repo = OrderRepository(mongo_manager=mongo_manager)

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

    all_orders = repo.list_all()
    assert len(all_orders) == 1
    assert all_orders[0]["id"] == "order_test_1"

    repo.set_idempotent(key="user_test_1:key_1", order_id="order_test_1")
    assert repo.get_idempotent("user_test_1:key_1") == "order_test_1"


def test_memory_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = MemoryRepository(mongo_manager=mongo_manager, redis_manager=redis_manager)

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


def test_auth_repository_roundtrip_user_and_refresh() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = AuthRepository(
        mongo_manager=mongo_manager,
        redis_manager=redis_manager,
    )

    user = {
        "id": "user_test_9",
        "email": "repo-auth@example.com",
        "name": "Repo Auth",
        "passwordHash": "hash",
        "role": "customer",
        "createdAt": store.iso_now(),
        "updatedAt": store.iso_now(),
        "lastLoginAt": store.iso_now(),
    }
    repo.create_user(user)

    by_id = repo.get_user_by_id("user_test_9")
    assert by_id is not None
    assert by_id["email"] == "repo-auth@example.com"

    by_email = repo.get_user_by_email("repo-auth@example.com")
    assert by_email is not None
    assert by_email["id"] == "user_test_9"

    repo.set_refresh_token("refresh_token_1", {"userId": "user_test_9", "createdAt": store.iso_now()})
    token = repo.get_refresh_token("refresh_token_1")
    assert token is not None
    assert token["userId"] == "user_test_9"

    repo.revoke_refresh_token("refresh_token_1")
    assert repo.get_refresh_token("refresh_token_1") is None


def test_interaction_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = InteractionRepository(
        mongo_manager=mongo_manager,
        redis_manager=redis_manager,
    )

    message = {
        "id": "msg_test_1",
        "sessionId": "session_test_5",
        "userId": None,
        "message": "show me shoes",
        "intent": "search_product",
        "agent": "product",
        "response": {"message": "ok", "metadata": {"success": True}},
        "timestamp": store.iso_now(),
    }
    repo.create(message)

    recent = repo.recent(session_id="session_test_5", limit=5)
    assert len(recent) == 1
    assert recent[0]["id"] == "msg_test_1"

    day = str(message["timestamp"])[:10]
    today = repo.list_by_date(date_prefix=day)
    assert len(today) == 1
    assert today[0]["agent"] == "product"


def test_support_repository_roundtrip_open_tickets() -> None:
    store = InMemoryStore()
    mongo_manager, _ = _fake_managers()
    repo = SupportRepository(mongo_manager=mongo_manager)

    ticket = {
        "id": "ticket_test_1",
        "userId": "user_test_3",
        "sessionId": "session_test_7",
        "issue": "Need help",
        "priority": "normal",
        "status": "open",
        "createdAt": store.iso_now(),
        "updatedAt": store.iso_now(),
    }
    repo.create(ticket)

    open_tickets = repo.list_open()
    assert len(open_tickets) == 1
    assert open_tickets[0]["id"] == "ticket_test_1"


def test_session_repository_count_cached() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = SessionRepository(mongo_manager=mongo_manager, redis_manager=redis_manager)

    assert repo.count() == 0
    repo.create(
        {
            "id": "session_test_10",
            "userId": None,
            "channel": "web",
            "createdAt": store.iso_now(),
            "lastActivity": store.iso_now(),
            "expiresAt": store.iso_now(),
            "context": {},
        }
    )
    assert repo.count() == 1


def test_session_repository_find_latest_for_user() -> None:
    from datetime import timedelta
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = SessionRepository(mongo_manager=mongo_manager, redis_manager=redis_manager)
    now = store.utc_now()

    repo.create(
        {
            "id": "session_user_old",
            "userId": "user_test_42",
            "channel": "web",
            "createdAt": (now - timedelta(minutes=20)).isoformat(),
            "lastActivity": (now - timedelta(minutes=10)).isoformat(),
            "expiresAt": (now + timedelta(minutes=20)).isoformat(),
            "context": {},
        }
    )
    repo.create(
        {
            "id": "session_user_new",
            "userId": "user_test_42",
            "channel": "web",
            "createdAt": (now - timedelta(minutes=5)).isoformat(),
            "lastActivity": now.isoformat(),
            "expiresAt": (now + timedelta(minutes=30)).isoformat(),
            "context": {},
        }
    )

    latest = repo.find_latest_for_user("user_test_42")
    assert latest is not None
    assert latest["id"] == "session_user_new"


def test_session_repository_cleanup_expired_sessions() -> None:
    from datetime import timedelta
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = SessionRepository(mongo_manager=mongo_manager, redis_manager=redis_manager)
    service = SessionService(session_repository=repo)

    expired_id = "session_expired_1"
    active_id = "session_active_1"
    now = store.utc_now()
    repo.create(
        {
            "id": expired_id,
            "userId": None,
            "channel": "web",
            "createdAt": now.isoformat(),
            "lastActivity": now.isoformat(),
            "expiresAt": (now - timedelta(minutes=1)).isoformat(),
            "context": {},
        }
    )
    repo.create(
        {
            "id": active_id,
            "userId": None,
            "channel": "web",
            "createdAt": now.isoformat(),
            "lastActivity": now.isoformat(),
            "expiresAt": (now + timedelta(minutes=10)).isoformat(),
            "context": {},
        }
    )

    removed = service.cleanup_expired()
    assert removed == 1
    assert repo.get(expired_id) is None
    assert repo.get(active_id) is not None


def test_product_and_inventory_repositories_roundtrip() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    product_repo = ProductRepository(
        mongo_manager=mongo_manager,
        redis_manager=redis_manager,
    )
    inventory_repo = InventoryRepository(
        mongo_manager=mongo_manager,
        redis_manager=redis_manager,
    )

    product = {
        "id": "prod_test_100",
        "name": "Repo Product",
        "description": "Created in repository test",
        "category": "gear",
        "price": 19.99,
        "currency": "USD",
        "images": [],
        "variants": [{"id": "var_test_100", "size": "M", "color": "black", "inStock": True}],
        "rating": 0.0,
        "reviewCount": 0,
    }
    product_repo.create(product)

    loaded = product_repo.get("prod_test_100")
    assert loaded is not None
    assert loaded["name"] == "Repo Product"

    categories = product_repo.list_categories()
    assert "gear" in categories

    stock = {
        "variantId": "var_test_100",
        "productId": "prod_test_100",
        "totalQuantity": 8,
        "reservedQuantity": 0,
        "availableQuantity": 8,
        "updatedAt": store.iso_now(),
    }
    inventory_repo.upsert(stock)
    loaded_stock = inventory_repo.get("var_test_100")
    assert loaded_stock is not None
    assert loaded_stock["availableQuantity"] == 8

    product_repo.set_variant_stock_flag(variant_id="var_test_100", in_stock=False)
    updated = product_repo.get("prod_test_100")
    assert updated is not None
    variant = next(item for item in updated["variants"] if item["id"] == "var_test_100")
    assert variant["inStock"] is False

    inventory_repo.delete("var_test_100")
    assert inventory_repo.get("var_test_100") is None
    product_repo.delete("prod_test_100")
    assert product_repo.get("prod_test_100") is None


def test_notification_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, _ = _fake_managers()
    repo = NotificationRepository(mongo_manager=mongo_manager)

    notification = {
        "id": "notif_test_1",
        "type": "order_confirmation",
        "userId": "user_test_7",
        "orderId": "order_test_7",
        "message": "Order confirmed",
        "createdAt": store.iso_now(),
    }
    repo.create(notification)

    for_user = repo.list_for_user("user_test_7", limit=20)
    assert len(for_user) == 1
    assert for_user[0]["id"] == "notif_test_1"


def test_category_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, redis_manager = _fake_managers()
    repo = CategoryRepository(
        mongo_manager=mongo_manager,
        redis_manager=redis_manager,
    )

    category = {
        "id": "fitness",
        "slug": "fitness",
        "name": "Fitness",
        "description": "Fitness products",
        "status": "active",
        "createdAt": store.iso_now(),
        "updatedAt": store.iso_now(),
    }
    repo.create(category)

    by_id = repo.get("fitness")
    assert by_id is not None
    assert by_id["name"] == "Fitness"

    listed = repo.list_all()
    slugs = [row["slug"] for row in listed]
    assert "fitness" in slugs
    assert "fitness" in repo.active_slugs()

    category["status"] = "archived"
    repo.update(category)
    assert "fitness" not in repo.active_slugs()

    repo.delete("fitness")
    assert repo.get("fitness") is None


def test_admin_activity_repository_roundtrip_in_memory() -> None:
    store = InMemoryStore()
    mongo_manager, _redis_manager = _fake_managers()
    repo = AdminActivityRepository(mongo_manager=mongo_manager)

    payload = {
        "id": "admin_log_test_1",
        "adminId": "user_1",
        "adminEmail": "admin@example.com",
        "action": "product_update",
        "resource": "product",
        "resourceId": "prod_1",
        "changes": {"before": {"name": "A"}, "after": {"name": "B"}},
        "ipAddress": "127.0.0.1",
        "userAgent": "pytest",
        "timestamp": store.iso_now(),
    }
    repo.create(payload)

    rows = repo.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "product_update"
