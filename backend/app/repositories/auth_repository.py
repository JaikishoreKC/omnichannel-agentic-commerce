from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager


class AuthRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def create_user(self, user: dict[str, Any]) -> dict[str, Any]:
        self._write_user_through(user)
        return deepcopy(user)

    def update_user(self, user: dict[str, Any]) -> dict[str, Any]:
        self._write_user_through(user)
        return deepcopy(user)

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        cached = self._read_user_from_redis_by_id(user_id)
        if cached is not None:
            return deepcopy(cached)

        persisted = self._read_user_from_mongo_by_id(user_id)
        if persisted is not None:
            self._write_user_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized = email.strip().lower()
        cached = self._read_user_from_redis_by_email(normalized)
        if cached is not None:
            return deepcopy(cached)

        persisted = self._read_user_from_mongo_by_email(normalized)
        if persisted is not None:
            self._write_user_to_redis(persisted)
            return deepcopy(persisted)
        return None

    def list_all_users(self, limit: int = 50) -> list[dict[str, Any]]:
        collection = self._mongo_users_collection()
        if collection is None:
            return []
        rows = list(collection.find({}).sort("createdAt", -1).limit(limit))
        users: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("userId", None)
            # Do not return hashed passwords to the API layer
            row.pop("passwordHash", None)
            if isinstance(row, dict):
                users.append(row)
        return users


    def set_refresh_token(self, token: str, payload: dict[str, Any]) -> None:
        self._write_refresh_to_redis(token, payload)
        self._write_refresh_to_mongo(token, payload)

    def get_refresh_token(self, token: str) -> dict[str, Any] | None:
        cached = self._read_refresh_from_redis(token)
        if cached is not None:
            return deepcopy(cached)

        persisted = self._read_refresh_from_mongo(token)
        if persisted is not None:
            self._write_refresh_to_redis(token, persisted)
            return deepcopy(persisted)
        return None

    def revoke_refresh_token(self, token: str) -> None:
        self._delete_refresh_from_redis(token)
        self._delete_refresh_from_mongo(token)

    def _write_user_through(self, user: dict[str, Any]) -> None:
        self._write_user_to_redis(user)
        self._write_user_to_mongo(user)

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_users_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["users"]

    def _mongo_refresh_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["refresh_tokens"]

    def _redis_user_id_key(self, user_id: str) -> str:
        return f"user:id:{user_id}"

    def _redis_user_email_key(self, email: str) -> str:
        return f"user:email:{email}"

    def _redis_refresh_key(self, token: str) -> str:
        return f"refresh:{token}"

    def _write_user_to_redis(self, user: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        payload = json.dumps(user)
        user_id = str(user.get("id", ""))
        email = str(user.get("email", "")).strip().lower()
        if not user_id or not email:
            return
        client.set(self._redis_user_id_key(user_id), payload, ex=60 * 60)
        client.set(self._redis_user_email_key(email), payload, ex=60 * 60)

    def _read_user_from_redis_by_id(self, user_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_user_id_key(user_id))
        return self._decode_dict_payload(payload)

    def _read_user_from_redis_by_email(self, email: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_user_email_key(email))
        return self._decode_dict_payload(payload)

    def _write_user_to_mongo(self, user: dict[str, Any]) -> None:
        collection = self._mongo_users_collection()
        if collection is None:
            return
        collection.update_one(
            {"userId": user["id"]},
            {"$set": {"userId": user["id"], **deepcopy(user)}},
            upsert=True,
        )

    def _read_user_from_mongo_by_id(self, user_id: str) -> dict[str, Any] | None:
        collection = self._mongo_users_collection()
        if collection is None:
            return None
        payload = collection.find_one({"userId": user_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("userId", None)
        return payload if isinstance(payload, dict) else None

    def _read_user_from_mongo_by_email(self, email: str) -> dict[str, Any] | None:
        collection = self._mongo_users_collection()
        if collection is None:
            return None
        payload = collection.find_one({"email": email})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("userId", None)
        return payload if isinstance(payload, dict) else None

    def _write_refresh_to_redis(self, token: str, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_refresh_key(token), json.dumps(payload), ex=7 * 24 * 60 * 60)

    def _read_refresh_from_redis(self, token: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_refresh_key(token))
        return self._decode_dict_payload(payload)

    def _delete_refresh_from_redis(self, token: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_refresh_key(token))

    def _write_refresh_to_mongo(self, token: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return
        collection.update_one(
            {"token": token},
            {"$set": {"token": token, **deepcopy(payload)}},
            upsert=True,
        )

    def _read_refresh_from_mongo(self, token: str) -> dict[str, Any] | None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return None
        payload = collection.find_one({"token": token})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("token", None)
        return payload if isinstance(payload, dict) else None

    def _delete_refresh_from_mongo(self, token: str) -> None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return
        collection.delete_one({"token": token})

    @staticmethod
    def _decode_dict_payload(payload: Any) -> dict[str, Any] | None:
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
