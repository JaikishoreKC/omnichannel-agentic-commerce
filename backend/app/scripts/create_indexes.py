from __future__ import annotations

import argparse
import json
import time
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.infrastructure.mongo_indexes import ensure_mongo_indexes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create MongoDB indexes for commerce collections.")
    parser.add_argument("--mongo-uri", default=None, help="MongoDB connection URI (defaults to MONGODB_URI env).")
    parser.add_argument("--database", default=None, help="Mongo database name override.")
    parser.add_argument("--retries", type=int, default=12, help="Retry attempts if Mongo is not ready.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Delay in seconds between retries.")
    parser.add_argument("--timeout-ms", type=int, default=2500, help="Mongo server selection timeout (ms).")
    return parser


def _connect_with_retry(*, uri: str, retries: int, retry_delay: float, timeout_ms: int) -> MongoClient:
    last_error: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        try:
            client.admin.command("ping")
            return client
        except (PyMongoError, RuntimeError) as exc:  # pragma: no cover - exercised in runtime environments
            last_error = exc
            client.close()
            if attempt >= retries:
                break
            time.sleep(max(0.0, retry_delay))

    if last_error is None:
        raise RuntimeError("Mongo connection failed for unknown reason.")
    raise RuntimeError(f"Mongo connection failed after {retries} attempts: {last_error}") from last_error


def run(*, mongo_uri: str | None, database: str | None, retries: int, retry_delay: float, timeout_ms: int) -> dict[str, Any]:
    settings = Settings.from_env()
    uri = mongo_uri or settings.mongodb_uri
    client = _connect_with_retry(
        uri=uri,
        retries=retries,
        retry_delay=retry_delay,
        timeout_ms=timeout_ms,
    )
    try:
        created = ensure_mongo_indexes(client=client, database_name=database)
    finally:
        client.close()

    return {
        "mongoUri": uri,
        "database": database or "default-from-uri-or-commerce",
        "collections": len(created),
        "indexes": created,
    }


def main() -> int:
    args = _parser().parse_args()
    summary = run(
        mongo_uri=args.mongo_uri,
        database=args.database,
        retries=args.retries,
        retry_delay=args.retry_delay,
        timeout_ms=args.timeout_ms,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
