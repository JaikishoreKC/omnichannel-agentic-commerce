from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING

IndexSpec = tuple[list[tuple[str, int]], dict[str, Any]]


MONGO_INDEX_SPECS: dict[str, list[IndexSpec]] = {
    "runtime_state": [
        ([("updatedAt", DESCENDING)], {"name": "runtime_state_updated_at_desc"}),
    ],
    "users": [
        ([("userId", ASCENDING)], {"name": "users_user_id_unique", "unique": True}),
        ([("email", ASCENDING)], {"name": "users_email_unique", "unique": True}),
    ],
    "refresh_tokens": [
        ([("token", ASCENDING)], {"name": "refresh_tokens_token_unique", "unique": True}),
        ([("userId", ASCENDING), ("createdAt", DESCENDING)], {"name": "refresh_tokens_user_created_desc"}),
    ],
    "sessions": [
        ([("sessionId", ASCENDING)], {"name": "sessions_session_id_unique", "unique": True}),
        ([("userId", ASCENDING), ("lastActivity", DESCENDING)], {"name": "sessions_user_last_activity_desc"}),
        ([("anonymousId", ASCENDING)], {"name": "sessions_anonymous_id_asc"}),
        ([("expiresAt", ASCENDING)], {"name": "sessions_expires_at_asc"}),
    ],
    "carts": [
        ([("cartId", ASCENDING)], {"name": "carts_cart_id_unique", "unique": True}),
        ([("userId", ASCENDING), ("updatedAt", DESCENDING)], {"name": "carts_user_updated_desc"}),
        ([("sessionId", ASCENDING), ("userId", ASCENDING), ("updatedAt", DESCENDING)], {"name": "carts_session_user_updated_desc"}),
        ([("status", ASCENDING), ("updatedAt", DESCENDING)], {"name": "carts_status_updated_desc"}),
        ([("expiresAt", ASCENDING)], {"name": "carts_expires_at_asc"}),
    ],
    "orders": [
        ([("orderId", ASCENDING)], {"name": "orders_order_id_unique", "unique": True}),
        ([("userId", ASCENDING), ("createdAt", DESCENDING)], {"name": "orders_user_created_desc"}),
        ([("createdAt", DESCENDING)], {"name": "orders_created_desc"}),
    ],
    "idempotency_keys": [
        ([("key", ASCENDING)], {"name": "idempotency_key_unique", "unique": True}),
    ],
    "memories": [
        ([("userId", ASCENDING)], {"name": "memories_user_id_unique", "unique": True}),
    ],
    "interactions": [
        ([("messageId", ASCENDING)], {"name": "interactions_message_id_unique", "unique": True}),
        ([("sessionId", ASCENDING), ("timestamp", ASCENDING)], {"name": "interactions_session_timestamp_asc"}),
        ([("timestamp", ASCENDING)], {"name": "interactions_timestamp_asc"}),
    ],
    "support_tickets": [
        ([("ticketId", ASCENDING)], {"name": "support_tickets_ticket_id_unique", "unique": True}),
        ([("status", ASCENDING), ("createdAt", DESCENDING)], {"name": "support_tickets_status_created_desc"}),
    ],
    "products": [
        ([("productId", ASCENDING)], {"name": "products_product_id_unique", "unique": True}),
        ([("name", ASCENDING)], {"name": "products_name_asc"}),
        ([("category", ASCENDING), ("price", ASCENDING)], {"name": "products_category_price_asc"}),
        ([("brand", ASCENDING), ("price", ASCENDING)], {"name": "products_brand_price_asc"}),
        ([("status", ASCENDING), ("updatedAt", DESCENDING)], {"name": "products_status_updated_desc"}),
    ],
    "categories": [
        ([("categoryId", ASCENDING)], {"name": "categories_category_id_unique", "unique": True}),
        ([("slug", ASCENDING)], {"name": "categories_slug_unique", "unique": True}),
        ([("status", ASCENDING), ("name", ASCENDING)], {"name": "categories_status_name_asc"}),
    ],
    "inventory": [
        ([("variantId", ASCENDING)], {"name": "inventory_variant_id_unique", "unique": True}),
        ([("productId", ASCENDING), ("variantId", ASCENDING)], {"name": "inventory_product_variant_asc"}),
    ],
    "notifications": [
        ([("notificationId", ASCENDING)], {"name": "notifications_notification_id_unique", "unique": True}),
        ([("userId", ASCENDING), ("createdAt", DESCENDING)], {"name": "notifications_user_created_desc"}),
    ],
    "admin_activity_logs": [
        ([("id", ASCENDING)], {"name": "admin_activity_logs_id_unique", "unique": True}),
        ([("adminId", ASCENDING), ("timestamp", DESCENDING)], {"name": "admin_activity_logs_admin_time_desc"}),
        ([("resource", ASCENDING), ("resourceId", ASCENDING)], {"name": "admin_activity_logs_resource_resource_id"}),
        ([("timestamp", DESCENDING)], {"name": "admin_activity_logs_timestamp_desc"}),
    ],
}


def resolve_database(client: Any, database_name: str | None = None) -> Any:
    if database_name:
        return client[database_name]
    default_database = client.get_default_database()
    if default_database is not None:
        return default_database
    return client["commerce"]


def ensure_mongo_indexes(*, client: Any, database_name: str | None = None) -> dict[str, list[str]]:
    database = resolve_database(client, database_name)
    created: dict[str, list[str]] = {}
    for collection_name, specs in MONGO_INDEX_SPECS.items():
        collection = database[collection_name]
        names: list[str] = []
        for keys, options in specs:
            names.append(str(collection.create_index(keys, **options)))
        created[collection_name] = names
    return created
