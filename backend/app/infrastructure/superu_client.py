from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings


class SuperUClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.superu_enabled and bool(self.settings.superu_api_key.strip())

    def start_outbound_call(
        self,
        *,
        to_phone_number: str,
        assistant_id: str | None = None,
        from_phone_number: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("SuperU is not configured")

        resolved_assistant = assistant_id or self.settings.superu_assistant_id
        resolved_from_number = from_phone_number or self.settings.superu_from_phone_number
        if not str(resolved_assistant).strip():
            raise RuntimeError("SuperU assistant_id is required")
        if not str(resolved_from_number).strip():
            raise RuntimeError("SuperU from_phone_number is required")

        payload = {
            "assistant_id": resolved_assistant,
            "phone_number": to_phone_number,
            "from_phone_number": resolved_from_number,
        }
        if metadata:
            payload["metadata"] = metadata
        response = self._request(
            method="POST",
            path="/api/v1/call/outbound-call",
            json_payload=payload,
        )
        if not isinstance(response, dict):
            raise RuntimeError("SuperU call response is not a JSON object")
        return response

    def fetch_call_logs(self, *, call_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        params: dict[str, Any] = {"limit": max(1, min(limit, 200))}
        if call_id:
            params["call_id"] = call_id
        payload = self._request(method="GET", path="/api/v1/call/logs", params=params)
        return self._extract_rows(payload)

    def _request(
        self,
        *,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.settings.superu_api_url.rstrip('/')}{path}"
        try:
            response = httpx.request(
                method=method.upper(),
                url=url,
                headers={
                    "superU-Api-Key": self.settings.superu_api_key,
                    "Content-Type": "application/json",
                },
                params=params,
                json=json_payload,
                timeout=12.0,
            )
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"SuperU request failed: {exc}") from exc
        try:
            return response.json()
        except Exception as exc:
            raise RuntimeError("SuperU response is not valid JSON") from exc

    def _extract_rows(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("data", "results", "logs", "items", "calls"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return [payload]
