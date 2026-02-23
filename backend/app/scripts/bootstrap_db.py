from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from pymongo import MongoClient

from app.core.config import Settings
from app.infrastructure.mongo_indexes import ensure_mongo_indexes, resolve_database
from app.scripts.create_indexes import _connect_with_retry
from app.store.in_memory import InMemoryStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap MongoDB with initial commerce data and indexes.")
    parser.add_argument("--mongo-uri", default=None, help="MongoDB connection URI (defaults to MONGODB_URI env).")
    parser.add_argument("--database", default=None, help="Mongo database name override.")
    parser.add_argument("--retries", type=int, default=12, help="Retry attempts if Mongo is not ready.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Delay in seconds between retries.")
    parser.add_argument("--timeout-ms", type=int, default=2500, help="Mongo server selection timeout (ms).")
    parser.add_argument(
        "--seed-runtime-state",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist runtime_state singleton snapshot.",
    )
    return parser


def _upsert_map(*, collection: Any, key_field: str, rows: dict[str, dict[str, Any]]) -> int:
    count = 0
    for row in rows.values():
        if not isinstance(row, dict):
            continue
        key_value = row.get(key_field) or row.get("id") or row.get("variantId")
        if not key_value:
            continue
        payload = dict(row)
        payload[key_field] = key_value
        collection.update_one({key_field: key_value}, {"$set": payload}, upsert=True)
        count += 1
    return count


def _upsert_list(
    *,
    collection: Any,
    unique_field: str,
    rows: list[dict[str, Any]],
    key_mapper: Callable[[dict[str, Any]], Any],
) -> int:
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        key_value = key_mapper(row)
        if not key_value:
            continue
        payload = dict(row)
        payload[unique_field] = key_value
        collection.update_one({unique_field: key_value}, {"$set": payload}, upsert=True)
        count += 1
    return count


def run(
    *,
    mongo_uri: str | None,
    database: str | None,
    retries: int,
    retry_delay: float,
    timeout_ms: int,
    seed_runtime_state: bool,
) -> dict[str, Any]:
    settings = Settings.from_env()
    uri = mongo_uri or settings.mongodb_uri
    store = InMemoryStore()
    state = store.export_state()
    client: MongoClient = _connect_with_retry(
        uri=uri,
        retries=retries,
        retry_delay=retry_delay,
        timeout_ms=timeout_ms,
    )
    try:
        created_indexes = ensure_mongo_indexes(client=client, database_name=database)
        db = resolve_database(client, database)

        seeded: dict[str, int] = {}
        seeded["users"] = _upsert_map(
            collection=db["users"],
            key_field="userId",
            rows=state.get("users_by_id", {}),
        )
        seeded["products"] = _upsert_map(
            collection=db["products"],
            key_field="productId",
            rows=state.get("products_by_id", {}),
        )
        seeded["categories"] = _upsert_map(
            collection=db["categories"],
            key_field="categoryId",
            rows=state.get("categories_by_id", {}),
        )
        seeded["inventory"] = _upsert_map(
            collection=db["inventory"],
            key_field="variantId",
            rows=state.get("inventory_by_variant", {}),
        )
        seeded["sessions"] = _upsert_map(
            collection=db["sessions"],
            key_field="sessionId",
            rows=state.get("sessions_by_id", {}),
        )
        seeded["carts"] = _upsert_map(
            collection=db["carts"],
            key_field="cartId",
            rows=state.get("carts_by_id", {}),
        )
        seeded["orders"] = _upsert_map(
            collection=db["orders"],
            key_field="orderId",
            rows=state.get("orders_by_id", {}),
        )
        seeded["memories"] = _upsert_map(
            collection=db["memories"],
            key_field="userId",
            rows=state.get("memories_by_user_id", {}),
        )

        refresh_tokens: dict[str, dict[str, Any]] = state.get("refresh_tokens", {})
        seeded["refresh_tokens"] = 0
        for token, payload in refresh_tokens.items():
            if not isinstance(payload, dict):
                continue
            row = {"token": token, **payload}
            db["refresh_tokens"].update_one({"token": token}, {"$set": row}, upsert=True)
            seeded["refresh_tokens"] += 1

        idempotency_keys: dict[str, str] = state.get("idempotency_keys", {})
        seeded["idempotency_keys"] = 0
        for key, order_id in idempotency_keys.items():
            db["idempotency_keys"].update_one(
                {"key": key},
                {"$set": {"key": key, "orderId": str(order_id)}},
                upsert=True,
            )
            seeded["idempotency_keys"] += 1

        interaction_rows: list[dict[str, Any]] = []
        for rows in state.get("messages_by_session", {}).values():
            if isinstance(rows, list):
                interaction_rows.extend([row for row in rows if isinstance(row, dict)])
        seeded["interactions"] = _upsert_list(
            collection=db["interactions"],
            unique_field="messageId",
            rows=interaction_rows,
            key_mapper=lambda row: row.get("id"),
        )

        support_rows = state.get("support_tickets", [])
        seeded["support_tickets"] = _upsert_list(
            collection=db["support_tickets"],
            unique_field="ticketId",
            rows=support_rows if isinstance(support_rows, list) else [],
            key_mapper=lambda row: row.get("id"),
        )

        notification_rows = state.get("notifications", [])
        seeded["notifications"] = _upsert_list(
            collection=db["notifications"],
            unique_field="notificationId",
            rows=notification_rows if isinstance(notification_rows, list) else [],
            key_mapper=lambda row: row.get("id"),
        )

        activity_rows = state.get("admin_activity_logs", [])
        seeded["admin_activity_logs"] = _upsert_list(
            collection=db["admin_activity_logs"],
            unique_field="id",
            rows=activity_rows if isinstance(activity_rows, list) else [],
            key_mapper=lambda row: row.get("id"),
        )

        if seed_runtime_state:
            db["runtime_state"].update_one(
                {"_id": "singleton"},
                {"$set": {"state": state, "updatedAt": store.iso_now()}},
                upsert=True,
            )

    finally:
        client.close()

    return {
        "mongoUri": uri,
        "database": database or "default-from-uri-or-commerce",
        "seedRuntimeState": seed_runtime_state,
        "seeded": seeded,
        "collections": len(created_indexes),
        "indexes": created_indexes,
    }


def main() -> int:
    args = _parser().parse_args()
    summary = run(
        mongo_uri=args.mongo_uri,
        database=args.database,
        retries=args.retries,
        retry_delay=args.retry_delay,
        timeout_ms=args.timeout_ms,
        seed_runtime_state=args.seed_runtime_state,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
