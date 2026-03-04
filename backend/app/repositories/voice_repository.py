from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager

class VoiceRepository:
    def __init__(
        self,
        *,
        mongo_manager: MongoClientManager,
    ) -> None:
        self.mongo_manager = mongo_manager

    def get_settings(self) -> dict[str, Any] | None:
        collection = self._mongo_db()["voice_settings"]
        row = collection.find_one({"id": "global_settings"})
        if row:
            row.pop("_id", None)
            row.pop("id", None)
            return row
        return None

    def upsert_settings(self, settings: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_settings"]
        collection.update_one(
            {"id": "global_settings"},
            {"$set": deepcopy(settings)},
            upsert=True,
        )

    def upsert_job(self, job: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_jobs"]
        collection.update_one(
            {"id": job["id"]},
            {"$set": deepcopy(job)},
            upsert=True,
        )
        self._upsert_job_in_memory(job)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        mirrored = self._get_job_in_memory(job_id)
        if mirrored is not None:
            return mirrored
        collection = self._mongo_db()["voice_jobs"]
        row = collection.find_one({"id": job_id})
        if row:
            row.pop("_id", None)
            return row
        return None

    def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        mirrored = self._list_jobs_in_memory(status=status, limit=limit)
        if mirrored:
            return mirrored
        collection = self._mongo_db()["voice_jobs"]
        query = {}
        if status:
            query["status"] = status
        rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
        for row in rows:
            row.pop("_id", None)
        return rows

    def upsert_call(self, call: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_calls"]
        collection.update_one(
            {"id": call["id"]},
            {"$set": deepcopy(call)},
            upsert=True,
        )
        self._upsert_call_in_memory(call)

    def get_call(self, call_id: str) -> dict[str, Any] | None:
        mirrored = self._get_call_in_memory(call_id)
        if mirrored is not None:
            return mirrored
        collection = self._mongo_db()["voice_calls"]
        row = collection.find_one({"id": call_id})
        if row:
            row.pop("_id", None)
            return row
        return None

    def find_call_by_provider_id(self, provider_call_id: str) -> dict[str, Any] | None:
        calls = self._list_calls_in_memory(status=None, limit=5000)
        for call in calls:
            if str(call.get("providerCallId", "")).strip() == provider_call_id:
                return call
        collection = self._mongo_db()["voice_calls"]
        row = collection.find_one({"providerCallId": provider_call_id})
        if row:
            row.pop("_id", None)
            return row
        return None

    def list_calls(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        mirrored = self._list_calls_in_memory(status=status, limit=limit)
        if mirrored:
            return mirrored
        collection = self._mongo_db()["voice_calls"]
        query = {}
        if status:
            query["status"] = status
        rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
        for row in rows:
            row.pop("_id", None)
        return rows

    def add_alert(self, alert: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_alerts"]
        collection.insert_one(deepcopy(alert))

    def list_alerts(self, *, severity: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        collection = self._mongo_db()["voice_alerts"]
        query = {}
        if severity:
            query["severity"] = severity
        rows = list(collection.find(query).sort("createdAt", -1).limit(limit))
        for row in rows:
            row.pop("_id", None)
        return rows

    def upsert_suppression(self, user_id: str, payload: dict[str, Any]) -> None:
        collection = self._mongo_db()["voice_suppressions"]
        collection.update_one(
            {"userId": user_id},
            {"$set": deepcopy(payload)},
            upsert=True,
        )
        self._upsert_suppression_in_memory(user_id, payload)

    def delete_suppression(self, user_id: str) -> None:
        collection = self._mongo_db()["voice_suppressions"]
        collection.delete_one({"userId": user_id})
        self._delete_suppression_in_memory(user_id)

    def list_suppressions(self) -> list[dict[str, Any]]:
        mirrored = self._list_suppressions_in_memory()
        if mirrored:
            return mirrored
        collection = self._mongo_db()["voice_suppressions"]
        rows = list(collection.find({}).sort("createdAt", -1))
        for row in rows:
            row.pop("_id", None)
        return rows

    def is_suppressed(self, user_id: str) -> bool:
        collection = self._mongo_db()["voice_suppressions"]
        return collection.find_one({"userId": user_id}) is not None

    def get_suppressed_user_ids(self) -> set[str]:
        collection = self._mongo_db()["voice_suppressions"]
        rows = list(collection.find({}, {"userId": 1}))
        return {str(row["userId"]) for row in rows}

    def _upsert_job_in_memory(self, job: dict[str, Any]) -> None:
        try:
            from app.container import store

            with store.lock:
                store.voice_jobs_by_id[str(job["id"])] = deepcopy(job)
        except Exception:
            return

    def _get_job_in_memory(self, job_id: str) -> dict[str, Any] | None:
        try:
            from app.container import store

            with store.lock:
                row = store.voice_jobs_by_id.get(job_id)
                return deepcopy(row) if isinstance(row, dict) else None
        except Exception:
            return None

    def _list_jobs_in_memory(self, *, status: str | None, limit: int) -> list[dict[str, Any]]:
        try:
            from app.container import store

            with store.lock:
                rows = list(store.voice_jobs_by_id.values())
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
        except Exception:
            return []

    def _upsert_call_in_memory(self, call: dict[str, Any]) -> None:
        try:
            from app.container import store

            with store.lock:
                store.voice_calls_by_id[str(call["id"])] = deepcopy(call)
        except Exception:
            return

    def _get_call_in_memory(self, call_id: str) -> dict[str, Any] | None:
        try:
            from app.container import store

            with store.lock:
                row = store.voice_calls_by_id.get(call_id)
                return deepcopy(row) if isinstance(row, dict) else None
        except Exception:
            return None

    def _list_calls_in_memory(self, *, status: str | None, limit: int) -> list[dict[str, Any]]:
        try:
            from app.container import store

            with store.lock:
                rows = list(store.voice_calls_by_id.values())
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
        except Exception:
            return []

    def _upsert_suppression_in_memory(self, user_id: str, payload: dict[str, Any]) -> None:
        try:
            from app.container import store

            with store.lock:
                store.voice_suppressions_by_user[user_id] = deepcopy(payload)
        except Exception:
            return

    def _delete_suppression_in_memory(self, user_id: str) -> None:
        try:
            from app.container import store

            with store.lock:
                store.voice_suppressions_by_user.pop(user_id, None)
        except Exception:
            return

    def _list_suppressions_in_memory(self) -> list[dict[str, Any]]:
        try:
            from app.container import store

            with store.lock:
                rows = list(store.voice_suppressions_by_user.values())
            output = [deepcopy(row) for row in rows if isinstance(row, dict)]
            output.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
            return output
        except Exception:
            return []

    def _mongo_db(self) -> Any:
        client = self.mongo_manager.client
        if client is None:
            raise RuntimeError("Mongo client not connected")
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database
