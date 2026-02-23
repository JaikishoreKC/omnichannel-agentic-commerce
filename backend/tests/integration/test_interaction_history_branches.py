from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.routes.interaction_routes as interaction_routes
from app.main import app


def _create_session(client: TestClient) -> str:
    response = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert response.status_code == 201
    return str(response.json()["sessionId"])


def _register_user(client: TestClient, *, session_id: str) -> str:
    response = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": f"history-{uuid4().hex}@example.com",
            "password": "SecurePass123!",
            "name": "History User",
        },
    )
    assert response.status_code == 201
    return str(response.json()["accessToken"])


def test_authenticated_history_builds_fallback_from_memory_when_session_history_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    session_id = _create_session(client)
    token = _register_user(client, session_id=session_id)

    def _raise_link_identity(**_: object) -> dict[str, object]:
        raise RuntimeError("link failed in test")

    def _empty_history(*, session_id: str, limit: int) -> list[dict[str, object]]:
        assert session_id
        assert limit > 0
        return []

    def _memory_history(*, user_id: str, limit: int) -> dict[str, object]:
        assert user_id
        assert limit > 0
        return {
            "history": [
                "ignore-non-dict-row",
                {
                    "type": "save_preference",
                    "timestamp": "2026-02-23T00:00:00+00:00",
                    "summary": {
                        "query": "remember denim",
                        "response": "Saved your denim preference.",
                    },
                },
                {
                    "type": "save_preference",
                    "timestamp": "2026-02-23T00:00:01+00:00",
                    "summary": {},
                },
            ]
        }

    monkeypatch.setattr(interaction_routes.auth_service, "link_identity", _raise_link_identity)
    monkeypatch.setattr(interaction_routes.interaction_service, "history_for_session", _empty_history)
    monkeypatch.setattr(interaction_routes.memory_service, "get_history", _memory_history)

    response = client.get(
        "/v1/interactions/history?limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert str(payload["sessionId"]).startswith("session_")
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["message"] == "remember denim"
    assert payload["messages"][0]["response"]["agent"] == "memory"


def test_guest_history_requires_session_id() -> None:
    client = TestClient(app)
    response = client.get("/v1/interactions/history")
    assert response.status_code == 400
    error = response.json()["error"]
    assert "sessionId is required" in str(error.get("message", ""))


def test_process_message_creates_session_when_missing_and_handles_identity_link_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    seed_session_id = _create_session(client)
    token = _register_user(client, session_id=seed_session_id)

    def _raise_link_identity(**_: object) -> dict[str, object]:
        raise RuntimeError("link failed in test")

    monkeypatch.setattr(interaction_routes.auth_service, "link_identity", _raise_link_identity)

    response = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sessionId": "session_non_existent_for_branch_coverage",
            "content": "show me running shoes",
            "channel": "web",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "response"
    assert str(payload["sessionId"]).startswith("session_")
    assert payload["payload"]["agent"] in {"product", "orchestrator"}
