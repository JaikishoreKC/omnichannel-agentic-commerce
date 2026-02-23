from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.api.routes.voice_webhook_routes as voice_webhook_routes
from app.main import app


def test_voice_callback_rejects_when_signature_verification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    def _verify_fail(**_: object) -> None:
        raise ValueError("bad signature")

    monkeypatch.setattr(voice_webhook_routes.superu_client, "verify_webhook_signature", _verify_fail)

    response = client.post(
        "/v1/voice/superu/callback",
        headers={
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": "1700000000",
            "X-SuperU-Signature": "sig",
        },
        content=b'{"event":"x"}',
    )

    assert response.status_code == 401
    error = response.json()["error"]
    assert "bad signature" in str(error.get("message", ""))


def test_voice_callback_rejects_empty_payload_after_signature_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        voice_webhook_routes.superu_client,
        "verify_webhook_signature",
        lambda **_: None,
    )

    response = client.post(
        "/v1/voice/superu/callback",
        headers={
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": "1700000000",
            "X-SuperU-Signature": "sig",
        },
        content=b"",
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert "payload is required" in str(error.get("message", "")).lower()


def test_voice_callback_rejects_invalid_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        voice_webhook_routes.superu_client,
        "verify_webhook_signature",
        lambda **_: None,
    )

    response = client.post(
        "/v1/voice/superu/callback",
        headers={
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": "1700000000",
            "X-SuperU-Signature": "sig",
        },
        content=b"{not-json}",
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert "valid json" in str(error.get("message", "")).lower()


def test_voice_callback_rejects_non_object_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        voice_webhook_routes.superu_client,
        "verify_webhook_signature",
        lambda **_: None,
    )

    response = client.post(
        "/v1/voice/superu/callback",
        headers={
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": "1700000000",
            "X-SuperU-Signature": "sig",
        },
        content=b"[]",
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert "json object" in str(error.get("message", "")).lower()


def test_voice_callback_rejects_when_ingest_returns_not_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        voice_webhook_routes.superu_client,
        "verify_webhook_signature",
        lambda **_: None,
    )
    monkeypatch.setattr(
        voice_webhook_routes.voice_recovery_service,
        "ingest_provider_callback",
        lambda *, payload: {"accepted": False, "reason": "webhook rejected"},
    )

    response = client.post(
        "/v1/voice/superu/callback",
        headers={
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": "1700000000",
            "X-SuperU-Signature": "sig",
        },
        content=b"{}",
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert "webhook rejected" in str(error.get("message", "")).lower()


def test_voice_callback_returns_success_when_ingest_accepts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        voice_webhook_routes.superu_client,
        "verify_webhook_signature",
        lambda **_: None,
    )
    monkeypatch.setattr(
        voice_webhook_routes.voice_recovery_service,
        "ingest_provider_callback",
        lambda *, payload: {
            "accepted": True,
            "matched": True,
            "idempotent": False,
            "providerCallId": "call_123",
        },
    )

    response = client.post(
        "/v1/voice/superu/callback",
        headers={
            "Content-Type": "application/json",
            "X-SuperU-Timestamp": "1700000000",
            "X-SuperU-Signature": "sig",
        },
        content=b'{"call_id":"call_123"}',
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["received"] is True
    assert payload["accepted"] is True
    assert payload["providerCallId"] == "call_123"
