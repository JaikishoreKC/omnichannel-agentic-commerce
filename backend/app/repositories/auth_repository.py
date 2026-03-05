from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class AuthRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
        store: InMemoryStore | None = None,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager
        self.store = store
        self._password_reset_tokens: dict[str, dict[str, Any]] = {}

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

        mirrored = self._read_user_from_in_memory_by_id(user_id)
        if mirrored is not None:
            return deepcopy(mirrored)
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

        mirrored = self._read_user_from_in_memory_by_email(normalized)
        if mirrored is not None:
            return deepcopy(mirrored)
        return None

    def list_all_users(self, limit: int = 50) -> list[dict[str, Any]]:
        if self.store is not None:
            with self.store.lock:
                users = [
                    deepcopy(user)
                    for user in self.store.users_by_id.values()
                ]
            users.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
            for user in users:
                user.pop("passwordHash", None)
            return users[: max(0, int(limit))]

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
        token_hash = self._token_hash(token)
        self._write_refresh_to_redis(token_hash, payload)
        self._write_refresh_to_mongo(token_hash, payload)
        self._write_refresh_to_in_memory(token_hash, payload)

    def get_refresh_token(self, token: str) -> dict[str, Any] | None:
        token_hash = self._token_hash(token)
        cached = self._read_refresh_from_redis(token_hash)
        if cached is not None:
            return deepcopy(cached)

        persisted = self._read_refresh_from_mongo(token_hash)
        if persisted is not None:
            self._write_refresh_to_redis(token_hash, persisted)
            return deepcopy(persisted)

        mirrored = self._read_refresh_from_in_memory(token_hash)
        if mirrored is not None:
            return deepcopy(mirrored)
        return None

    def revoke_refresh_token(self, token: str) -> None:
        token_hash = self._token_hash(token)
        self._delete_refresh_from_redis(token_hash)
        self._delete_refresh_from_mongo(token_hash)
        self._delete_refresh_from_in_memory(token_hash)

    def set_password_reset_token(self, token_hash: str, payload: dict[str, Any]) -> None:
        self._write_password_reset_to_redis(token_hash, payload)
        self._write_password_reset_to_mongo(token_hash, payload)
        self._write_password_reset_to_in_memory(token_hash, payload)

    def get_password_reset_token(self, token_hash: str) -> dict[str, Any] | None:
        cached = self._read_password_reset_from_redis(token_hash)
        if cached is not None:
            return deepcopy(cached)

        persisted = self._read_password_reset_from_mongo(token_hash)
        if persisted is not None:
            self._write_password_reset_to_redis(token_hash, persisted)
            return deepcopy(persisted)

        mirrored = self._read_password_reset_from_in_memory(token_hash)
        if mirrored is not None:
            return deepcopy(mirrored)
        return None

    def delete_password_reset_token(self, token_hash: str) -> None:
        self._delete_password_reset_from_redis(token_hash)
        self._delete_password_reset_from_mongo(token_hash)
        self._delete_password_reset_from_in_memory(token_hash)

    def _write_user_through(self, user: dict[str, Any]) -> None:
        self._write_user_to_redis(user)
        self._write_user_to_mongo(user)
        self._write_user_to_in_memory(user)

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

    def _redis_refresh_key(self, token_hash: str) -> str:
        return f"refresh:{token_hash}"

    def _redis_password_reset_key(self, token_hash: str) -> str:
        return f"password_reset:{token_hash}"

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
        user_id = str(user.get("id", "")).strip()
        email = str(user.get("email", "")).strip().lower()
        if not user_id or not email:
            return
        collection.update_one(
            {"userId": user_id},
            {"$set": {"userId": user_id, **deepcopy(user)}},
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

    def _write_user_to_in_memory(self, user: dict[str, Any]) -> None:
        if self.store is None:
            return
        user_id = str(user.get("id", "")).strip()
        email = str(user.get("email", "")).strip().lower()
        if not user_id or not email:
            return
        with self.store.lock:
            self.store.users_by_id[user_id] = deepcopy(user)
            self.store.user_ids_by_email[email] = user_id

    def _read_user_from_in_memory_by_id(self, user_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            payload = self.store.users_by_id.get(user_id)
            return deepcopy(payload) if isinstance(payload, dict) else None

    def _read_user_from_in_memory_by_email(self, email: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        normalized = email.strip().lower()
        with self.store.lock:
            user_id = self.store.user_ids_by_email.get(normalized)
            if not user_id:
                return None
            payload = self.store.users_by_id.get(user_id)
            return deepcopy(payload) if isinstance(payload, dict) else None

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

    def _write_refresh_to_redis(self, token_hash: str, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_refresh_key(token_hash), json.dumps(payload), ex=7 * 24 * 60 * 60)

    def _write_refresh_to_in_memory(self, token_hash: str, payload: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.refresh_tokens[token_hash] = deepcopy(payload)

    def _read_refresh_from_redis(self, token_hash: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_refresh_key(token_hash))
        return self._decode_dict_payload(payload)

    def _read_refresh_from_in_memory(self, token_hash: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            payload = self.store.refresh_tokens.get(token_hash)
            return deepcopy(payload) if isinstance(payload, dict) else None

    def _delete_refresh_from_redis(self, token_hash: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_refresh_key(token_hash))

    def _delete_refresh_from_in_memory(self, token_hash: str) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.refresh_tokens.pop(token_hash, None)

    def _write_refresh_to_mongo(self, token_hash: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return
        collection.update_one(
            {"tokenHash": token_hash},
            {"$set": {"tokenHash": token_hash, **deepcopy(payload)}},
            upsert=True,
        )

    def _read_refresh_from_mongo(self, token_hash: str) -> dict[str, Any] | None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return None
        payload = collection.find_one({"tokenHash": token_hash})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("tokenHash", None)
        return payload if isinstance(payload, dict) else None

    def _delete_refresh_from_mongo(self, token_hash: str) -> None:
        collection = self._mongo_refresh_collection()
        if collection is None:
            return
        collection.delete_one({"tokenHash": token_hash})

    def _mongo_password_reset_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["password_reset_tokens"]

    def _write_password_reset_to_redis(self, token_hash: str, payload: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        ttl_seconds = max(60, int(float(payload.get("expiresAt", 0)) - time.time()))
        client.set(self._redis_password_reset_key(token_hash), json.dumps(payload), ex=ttl_seconds)

    def _write_password_reset_to_in_memory(self, token_hash: str, payload: dict[str, Any]) -> None:
        self._password_reset_tokens[token_hash] = deepcopy(payload)

    def _read_password_reset_from_redis(self, token_hash: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_password_reset_key(token_hash))
        return self._decode_dict_payload(payload)

    def _read_password_reset_from_in_memory(self, token_hash: str) -> dict[str, Any] | None:
        payload = self._password_reset_tokens.get(token_hash)
        return deepcopy(payload) if isinstance(payload, dict) else None

    def _delete_password_reset_from_redis(self, token_hash: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_password_reset_key(token_hash))

    def _delete_password_reset_from_in_memory(self, token_hash: str) -> None:
        self._password_reset_tokens.pop(token_hash, None)

    def _write_password_reset_to_mongo(self, token_hash: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_password_reset_collection()
        if collection is None:
            return
        collection.update_one(
            {"tokenHash": token_hash},
            {"$set": {"tokenHash": token_hash, **deepcopy(payload)}},
            upsert=True,
        )

    def _read_password_reset_from_mongo(self, token_hash: str) -> dict[str, Any] | None:
        collection = self._mongo_password_reset_collection()
        if collection is None:
            return None
        payload = collection.find_one({"tokenHash": token_hash})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("tokenHash", None)
        return payload if isinstance(payload, dict) else None

    def _delete_password_reset_from_mongo(self, token_hash: str) -> None:
        collection = self._mongo_password_reset_collection()
        if collection is None:
            return
        collection.delete_one({"tokenHash": token_hash})

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

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
