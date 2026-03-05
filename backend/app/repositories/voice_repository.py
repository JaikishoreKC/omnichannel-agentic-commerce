from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager
from app.store.in_memory import InMemoryStore

class VoiceRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
        store: InMemoryStore | None = None,
    ) -> None:
        self.mongo_manager = mongo_manager
        self.store = store

    def get_settings(self) -> dict[str, Any] | None:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_settings"]
            row = collection.find_one({"id": "global_settings"})
            if row:
                row.pop("_id", None)
                row.pop("id", None)
                return row
        return self._get_settings_in_memory()

    def upsert_settings(self, settings: dict[str, Any]) -> None:
        database = self._mongo_db()
        use_in_memory_fallback = database is None
        if database is not None:
            collection = database["voice_settings"]
            collection.update_one(
                {"id": "global_settings"},
                {"$set": deepcopy(settings)},
                upsert=True,
            )
        if use_in_memory_fallback:
            self._upsert_settings_in_memory(settings)

    def upsert_job(self, job: dict[str, Any]) -> None:
        database = self._mongo_db()
        use_in_memory_fallback = database is None
        if database is not None:
            collection = database["voice_jobs"]
            collection.update_one(
                {"id": job["id"]},
                {"$set": deepcopy(job)},
                upsert=True,
            )
        if use_in_memory_fallback:
            self._upsert_job_in_memory(job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_jobs"]
            row = collection.find_one({"id": job_id})
            if row:
                row.pop("_id", None)
                return row
        return self._get_job_in_memory(job_id)

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_jobs"]
            query = {}
            if status:
                query["status"] = status
            rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
            for row in rows:
                row.pop("_id", None)
            return rows
        return self._list_jobs_in_memory(status=status, limit=limit)

    def upsert_call(self, call: dict[str, Any]) -> None:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_calls"]
            collection.update_one(
                {"id": call["id"]},
                {"$set": deepcopy(call)},
                upsert=True,
            )
        if self.store is not None:
            # Keep the in-memory mirror in sync for in-process consumers and tests.
            self._upsert_call_in_memory(call)

    def get_call(self, call_id: str) -> dict[str, Any] | None:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_calls"]
            row = collection.find_one({"id": call_id})
            if row:
                row.pop("_id", None)
                return row
        return self._get_call_in_memory(call_id)

    def find_call_by_provider_id(self, provider_call_id: str) -> dict[str, Any] | None:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_calls"]
            row = collection.find_one({"providerCallId": provider_call_id})
            if row:
                row.pop("_id", None)
                return row
        calls = self._list_calls_in_memory(status=None, limit=5000)
        for call in calls:
            if str(call.get("providerCallId", "")).strip() == provider_call_id:
                return call
        return None

    def list_calls(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_calls"]
            query = {}
            if status:
                query["status"] = status
            rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
            for row in rows:
                row.pop("_id", None)
            return rows
        return self._list_calls_in_memory(status=status, limit=limit)

    def add_alert(self, alert: dict[str, Any]) -> None:
        database = self._mongo_db()
        use_in_memory_fallback = database is None
        if database is not None:
            collection = database["voice_alerts"]
            collection.insert_one(deepcopy(alert))
        if use_in_memory_fallback:
            self._add_alert_in_memory(alert)

    def list_alerts(self, *, severity: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_alerts"]
            query = {}
            if severity:
                query["severity"] = severity
            rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
            for row in rows:
                row.pop("_id", None)
            return rows
        return self._list_alerts_in_memory(severity=severity, limit=limit)

    def upsert_suppression(self, user_id: str, payload: dict[str, Any]) -> None:
        database = self._mongo_db()
        use_in_memory_fallback = database is None
        if database is not None:
            collection = database["voice_suppressions"]
            collection.update_one(
                {"userId": user_id},
                {"$set": deepcopy(payload)},
                upsert=True,
            )
        if use_in_memory_fallback:
            self._upsert_suppression_in_memory(user_id, payload)

    def delete_suppression(self, user_id: str) -> None:
        database = self._mongo_db()
        use_in_memory_fallback = database is None
        if database is not None:
            collection = database["voice_suppressions"]
            collection.delete_one({"userId": user_id})
        if use_in_memory_fallback:
            self._delete_suppression_in_memory(user_id)

    def list_suppressions(self) -> list[dict[str, Any]]:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_suppressions"]
            rows = list(collection.find({}).sort("createdAt", -1))
            for row in rows:
                row.pop("_id", None)
            return rows
        return self._list_suppressions_in_memory()

    def is_suppressed(self, user_id: str) -> bool:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_suppressions"]
            return collection.find_one({"userId": user_id}) is not None
        return self._is_suppressed_in_memory(user_id)

    def get_suppressed_user_ids(self) -> set[str]:
        database = self._mongo_db()
        if database is not None:
            collection = database["voice_suppressions"]
            rows = list(collection.find({}, {"userId": 1}))
            return {str(row["userId"]) for row in rows}
        return self._suppressed_user_ids_in_memory()

    def _upsert_settings_in_memory(self, settings: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.voice_settings = deepcopy(settings)

    def _get_settings_in_memory(self) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            return deepcopy(self.store.voice_settings)

    def _upsert_job_in_memory(self, job: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.voice_jobs_by_id[str(job["id"])] = deepcopy(job)

    def _get_job_in_memory(self, job_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            row = self.store.voice_jobs_by_id.get(job_id)
            return deepcopy(row) if isinstance(row, dict) else None

    def _list_jobs_in_memory(self, *, status: str | None, limit: int) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = list(self.store.voice_jobs_by_id.values())
        normalized_status = str(status).strip().lower() if status else ""
        output: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if normalized_status and str(row.get("status", "")).strip().lower() != normalized_status:
                continue
            output.append(deepcopy(row))
        output.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return output[: max(1, limit)]

    def _upsert_call_in_memory(self, call: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.voice_calls_by_id[str(call["id"])] = deepcopy(call)

    def _get_call_in_memory(self, call_id: str) -> dict[str, Any] | None:
        if self.store is None:
            return None
        with self.store.lock:
            row = self.store.voice_calls_by_id.get(call_id)
            return deepcopy(row) if isinstance(row, dict) else None

    def _list_calls_in_memory(self, *, status: str | None, limit: int) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = list(self.store.voice_calls_by_id.values())
        normalized_status = str(status).strip().lower() if status else ""
        output: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if normalized_status and str(row.get("status", "")).strip().lower() != normalized_status:
                continue
            output.append(deepcopy(row))
        output.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return output[: max(1, limit)]

    def _upsert_suppression_in_memory(self, user_id: str, payload: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.voice_suppressions_by_user[user_id] = deepcopy(payload)

    def _delete_suppression_in_memory(self, user_id: str) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.voice_suppressions_by_user.pop(user_id, None)

    def _list_suppressions_in_memory(self) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = list(self.store.voice_suppressions_by_user.values())
        output = [deepcopy(row) for row in rows if isinstance(row, dict)]
        output.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return output

    def _add_alert_in_memory(self, alert: dict[str, Any]) -> None:
        if self.store is None:
            return
        with self.store.lock:
            self.store.voice_alerts.append(deepcopy(alert))

    def _list_alerts_in_memory(self, *, severity: str | None, limit: int) -> list[dict[str, Any]]:
        if self.store is None:
            return []
        with self.store.lock:
            rows = [deepcopy(row) for row in self.store.voice_alerts if isinstance(row, dict)]
        normalized_severity = str(severity).strip().lower() if severity else ""
        if normalized_severity:
            rows = [
                row
                for row in rows
                if str(row.get("severity", "")).strip().lower() == normalized_severity
            ]
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return rows[: max(1, limit)]

    def _is_suppressed_in_memory(self, user_id: str) -> bool:
        if self.store is None:
            return False
        with self.store.lock:
            return user_id in self.store.voice_suppressions_by_user

    def _suppressed_user_ids_in_memory(self) -> set[str]:
        if self.store is None:
            return set()
        with self.store.lock:
            return {str(user_id) for user_id in self.store.voice_suppressions_by_user.keys()}

    def _mongo_db(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database
