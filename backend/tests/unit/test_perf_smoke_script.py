from __future__ import annotations

from typing import Any

import pytest

from app.scripts import perf_smoke


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeWebSocket:
    def __enter__(self) -> "_FakeWebSocket":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def send_json(self, _payload: dict[str, Any]) -> None:
        return None

    def receive_json(self) -> dict[str, Any]:
        return {"type": "response", "payload": {"agent": "product"}}


class _FakeClient:
    def post(self, path: str, **_kwargs: Any) -> _FakeResponse:
        if path == "/v1/sessions":
            return _FakeResponse(201, {"sessionId": "session_test"})
        if path == "/v1/interactions/message":
            return _FakeResponse(200, {"type": "response"})
        return _FakeResponse(404, {})

    def get(self, path: str, **_kwargs: Any) -> _FakeResponse:
        if path.startswith("/v1/products"):
            return _FakeResponse(200, {"products": []})
        return _FakeResponse(404, {})

    def websocket_connect(self, _path: str) -> _FakeWebSocket:
        return _FakeWebSocket()


def test_percentile_helper() -> None:
    assert perf_smoke._percentile([], 95.0) == 0.0
    assert perf_smoke._percentile([10.0, 20.0, 30.0], 95.0) == 30.0
    assert perf_smoke._percentile([10.0, 20.0, 30.0], 50.0) == 20.0


def test_perf_smoke_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(perf_smoke, "TestClient", lambda _app: _FakeClient())
    summary = perf_smoke.run(
        iterations=6,
        ws_iterations=5,
        products_p95_ms=500.0,
        interactions_p95_ms=500.0,
        ws_roundtrip_p95_ms=200.0,
    )
    assert summary["pass"] is True
    assert summary["products"]["pass"] is True
    assert summary["interactions"]["pass"] is True
    assert summary["websocketRoundtrip"]["pass"] is True


def test_perf_smoke_run_fails_when_session_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BadClient(_FakeClient):
        def post(self, path: str, **kwargs: Any) -> _FakeResponse:
            if path == "/v1/sessions":
                return _FakeResponse(500, {})
            return super().post(path, **kwargs)

    monkeypatch.setattr(perf_smoke, "TestClient", lambda _app: _BadClient())
    with pytest.raises(RuntimeError):
        perf_smoke.run(
            iterations=5,
            ws_iterations=5,
            products_p95_ms=500.0,
            interactions_p95_ms=500.0,
            ws_roundtrip_p95_ms=200.0,
        )
