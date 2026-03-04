from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
class SessionRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _redis_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _redis_user_latest_key(self, user_id: str) -> str:
        return f"session:user_latest:{user_id}"

    def create(self, session: dict[str, Any]) -> dict[str, Any]:
        client = self._redis_client()
        if client:
            client.set(self._redis_key(session["id"]), json.dumps(session), ex=60 * 60)
            self._upsert_user_latest_index(client=client, session=session)
        return deepcopy(session)

    def get(self, session_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            return None
            
        payload = client.get(self._redis_key(session_id))
        if not payload:
            return None
            
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
            
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def update(self, session: dict[str, Any]) -> dict[str, Any]:
        return self.create(session)

    def delete(self, session_id: str) -> None:
        client = self._redis_client()
        if client:
            payload = client.get(self._redis_key(session_id))
            deleted_session = self._decode_dict_payload(payload)
            client.delete(self._redis_key(session_id))
            if isinstance(deleted_session, dict):
                user_id = str(deleted_session.get("userId", "")).strip()
                if user_id:
                    latest_key = self._redis_user_latest_key(user_id)
                    latest_id = client.get(latest_key)
                    if isinstance(latest_id, bytes):
                        latest_id = latest_id.decode("utf-8")
                    if str(latest_id or "").strip() == session_id:
                        client.delete(latest_key)

    def list_all(self) -> list[dict[str, Any]]:
        client = self._redis_client()
        if not client:
            return []
        sessions = []
        for key in client.scan_iter(match="session:*"):
            payload = client.get(key)
            if not payload:
                continue
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            try:
                sessions.append(json.loads(payload))
            except json.JSONDecodeError:
                continue
        return sessions

    def find_latest_for_user(self, user_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            return None

        latest_id = client.get(self._redis_user_latest_key(user_id))
        if isinstance(latest_id, bytes):
            latest_id = latest_id.decode("utf-8")
        latest_id = str(latest_id or "").strip()
        if latest_id:
            payload = client.get(self._redis_key(latest_id))
            indexed = self._decode_dict_payload(payload)
            if isinstance(indexed, dict) and str(indexed.get("userId", "")).strip() == user_id:
                return indexed
            
        # For Redis, finding the latest session by user is an O(N) scan.
        # In a real enterprise system, we would maintain a reverse index (Set of sessions per user_id).
        # For simplicity in this phase, we scan all active sessions.
        matching = []
        for key in client.scan_iter(match="session:*"):
            payload = client.get(key)
            if not payload:
                continue
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            try:
                session = json.loads(payload)
                if str(session.get("userId", "")) == user_id:
                    matching.append(session)
            except json.JSONDecodeError:
                continue
                
        if not matching:
            return None
            
        matching.sort(
            key=lambda session: (
                str(session.get("lastActivityAt", "")),
                str(session.get("lastActivity", "")),
                str(session.get("createdAt", "")),
            ),
            reverse=True,
        )
        latest = matching[0]
        self._upsert_user_latest_index(client=client, session=latest)
        return latest

    def count(self) -> int:
        client = self._redis_client()
        if not client:
            return 0
        total = 0
        for key in client.scan_iter(match="session:*"):
            normalized = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            if normalized.startswith("session:user_latest:"):
                continue
            total += 1
        return total

    def _upsert_user_latest_index(self, *, client: Any, session: dict[str, Any]) -> None:
        user_id = str(session.get("userId", "")).strip()
        session_id = str(session.get("id", "")).strip()
        if not user_id or not session_id:
            return
        latest_key = self._redis_user_latest_key(user_id)
        current_latest_id = client.get(latest_key)
        if isinstance(current_latest_id, bytes):
            current_latest_id = current_latest_id.decode("utf-8")
        current_latest_id = str(current_latest_id or "").strip()
        if not current_latest_id:
            client.set(latest_key, session_id, ex=60 * 60)
            return
        current_payload = client.get(self._redis_key(current_latest_id))
        current = self._decode_dict_payload(current_payload)
        if not isinstance(current, dict):
            client.set(latest_key, session_id, ex=60 * 60)
            return
        if self._activity_rank(session) >= self._activity_rank(current):
            client.set(latest_key, session_id, ex=60 * 60)

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

    @staticmethod
    def _activity_rank(session: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(session.get("lastActivityAt", "")),
            str(session.get("lastActivity", "")),
            str(session.get("createdAt", "")),
        )
