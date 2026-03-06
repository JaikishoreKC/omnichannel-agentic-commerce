from __future__ import annotations

import json
from copy import deepcopy
from threading import Lock
from typing import Any

from app.infrastructure.logging import get_logger
from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager


logger = get_logger(__name__)
SESSION_TTL_SECONDS = 60 * 60


class SessionRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager
        self._fallback_lock = Lock()
        self._fallback_sessions: dict[str, dict[str, Any]] = {}
        self._fallback_user_latest: dict[str, str] = {}

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _redis_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _redis_user_latest_key(self, user_id: str) -> str:
        return f"session:user_latest:{user_id}"

    def create(self, session: dict[str, Any]) -> dict[str, Any]:
        session_id = str(session.get("id", "")).strip()
        if session_id:
            with self._fallback_lock:
                self._fallback_sessions[session_id] = deepcopy(session)
                user_id = str(session.get("userId", "")).strip()
                if user_id:
                    current_latest_id = self._fallback_user_latest.get(user_id)
                    current_latest = (
                        deepcopy(self._fallback_sessions.get(current_latest_id, {}))
                        if current_latest_id
                        else None
                    )
                    if not isinstance(current_latest, dict) or self._activity_rank(session) >= self._activity_rank(current_latest):
                        self._fallback_user_latest[user_id] = session_id

        client = self._redis_client()
        if client:
            client.set(self._redis_key(session["id"]), json.dumps(session), ex=SESSION_TTL_SECONDS)
            self._upsert_user_latest_index(client=client, session=session)
        return deepcopy(session)

    def get(self, session_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            with self._fallback_lock:
                payload = self._fallback_sessions.get(session_id)
                return deepcopy(payload) if isinstance(payload, dict) else None
            
        payload = client.get(self._redis_key(session_id))
        if not payload:
            with self._fallback_lock:
                fallback = self._fallback_sessions.get(session_id)
                if isinstance(fallback, dict):
                    return deepcopy(fallback)
            return None
            
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
            
        try:
            decoded = json.loads(payload)
            if isinstance(decoded, dict):
                with self._fallback_lock:
                    self._fallback_sessions[session_id] = deepcopy(decoded)
                return decoded
            return None
        except json.JSONDecodeError:
            with self._fallback_lock:
                fallback = self._fallback_sessions.get(session_id)
                return deepcopy(fallback) if isinstance(fallback, dict) else None

    def update(self, session: dict[str, Any]) -> dict[str, Any]:
        return self.create(session)

    def delete(self, session_id: str) -> None:
        with self._fallback_lock:
            deleted = self._fallback_sessions.pop(session_id, None)
            if isinstance(deleted, dict):
                user_id = str(deleted.get("userId", "")).strip()
                if user_id and self._fallback_user_latest.get(user_id) == session_id:
                    self._fallback_user_latest.pop(user_id, None)

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
            with self._fallback_lock:
                return [deepcopy(row) for row in self._fallback_sessions.values()]
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
        with self._fallback_lock:
            for session in sessions:
                if isinstance(session, dict):
                    sid = str(session.get("id", "")).strip()
                    if sid:
                        self._fallback_sessions[sid] = deepcopy(session)
        return sessions

    def find_latest_for_user(self, user_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if not client:
            with self._fallback_lock:
                latest_id = self._fallback_user_latest.get(user_id)
                if latest_id:
                    payload = self._fallback_sessions.get(latest_id)
                    if isinstance(payload, dict):
                        return deepcopy(payload)
                matching = [
                    deepcopy(session)
                    for session in self._fallback_sessions.values()
                    if isinstance(session, dict) and str(session.get("userId", "")).strip() == user_id
                ]
            if not matching:
                return None
            matching.sort(key=self._activity_rank, reverse=True)
            latest = matching[0]
            with self._fallback_lock:
                sid = str(latest.get("id", "")).strip()
                if sid:
                    self._fallback_user_latest[user_id] = sid
            return latest

        latest_id = client.get(self._redis_user_latest_key(user_id))
        if isinstance(latest_id, bytes):
            latest_id = latest_id.decode("utf-8")
        latest_id = str(latest_id or "").strip()
        if latest_id:
            payload = client.get(self._redis_key(latest_id))
            indexed = self._decode_dict_payload(payload)
            if isinstance(indexed, dict) and str(indexed.get("userId", "")).strip() == user_id:
                client.set(self._redis_user_latest_key(user_id), latest_id, ex=SESSION_TTL_SECONDS)
                return indexed
            logger.info(
                "session_repository.latest_index_stale",
                user_id=user_id,
                latest_id=latest_id,
            )
            
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
            logger.info("session_repository.latest_scan_empty", user_id=user_id)
            return None

        logger.info(
            "session_repository.latest_scan_fallback",
            user_id=user_id,
            candidates=len(matching),
        )
            
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
            with self._fallback_lock:
                return len(self._fallback_sessions)
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
            client.set(latest_key, session_id, ex=SESSION_TTL_SECONDS)
            return
        current_payload = client.get(self._redis_key(current_latest_id))
        current = self._decode_dict_payload(current_payload)
        if not isinstance(current, dict):
            client.set(latest_key, session_id, ex=SESSION_TTL_SECONDS)
            return
        if self._activity_rank(session) >= self._activity_rank(current):
            client.set(latest_key, session_id, ex=SESSION_TTL_SECONDS)

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
