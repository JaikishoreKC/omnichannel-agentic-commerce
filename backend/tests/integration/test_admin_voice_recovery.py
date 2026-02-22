from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.container import store, voice_recovery_service
from app.main import app


class _FakeSuperUClient:
    def __init__(self) -> None:
        self.enabled = True
        self.calls: list[dict[str, Any]] = []

    def start_outbound_call(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"call_id": "superu_call_001", "status": "queued"}

    def fetch_call_logs(self, **_kwargs: Any) -> list[dict[str, Any]]:
        return []


def _admin_headers(client: TestClient) -> dict[str, str]:
    admin_login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert admin_login.status_code == 200
    token = admin_login.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_voice_recovery_endpoints_and_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    admin_headers = _admin_headers(client)

    customer = client.post(
        "/v1/auth/register",
        json={
            "email": "voice-recovery-customer@example.com",
            "password": "SecurePass123!",
            "name": "Voice Customer",
            "phone": "+15551234567",
            "timezone": "UTC",
        },
    )
    assert customer.status_code == 201
    customer_token = customer.json()["accessToken"]

    add_item = client.post(
        "/v1/cart/items",
        headers={"Authorization": f"Bearer {customer_token}"},
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201
    cart_id = add_item.json()["cartId"]

    with store.lock:
        cart = dict(store.carts_by_id[cart_id])
        cart["updatedAt"] = (store.utc_now() - timedelta(minutes=45)).isoformat()
        store.carts_by_id[cart_id] = cart

    fake_superu = _FakeSuperUClient()
    monkeypatch.setattr(voice_recovery_service, "superu_client", fake_superu)

    update_settings = client.put(
        "/v1/admin/voice/settings",
        headers=admin_headers,
        json={
            "enabled": True,
            "abandonmentMinutes": 30,
            "assistantId": "assistant_test_001",
            "fromPhoneNumber": "+15559876543",
            "maxAttemptsPerCart": 2,
            "maxCallsPerUserPerDay": 3,
            "maxCallsPerDay": 20,
            "dailyBudgetUsd": 50,
            "quietHoursStart": 0,
            "quietHoursEnd": 0,
        },
    )
    assert update_settings.status_code == 200
    assert update_settings.json()["settings"]["enabled"] is True

    process = client.post("/v1/admin/voice/process", headers=admin_headers)
    assert process.status_code == 200
    result = process.json()["result"]
    assert result["enqueued"] >= 1
    assert int(result["processed"]["completed"]) >= 1

    calls = client.get("/v1/admin/voice/calls", headers=admin_headers)
    assert calls.status_code == 200
    call_rows = calls.json()["calls"]
    assert len(call_rows) >= 1
    assert call_rows[0]["status"] in {"initiated", "ringing", "in_progress", "completed"}

    jobs = client.get("/v1/admin/voice/jobs?status=completed", headers=admin_headers)
    assert jobs.status_code == 200
    assert len(jobs.json()["jobs"]) >= 1

    stats = client.get("/v1/admin/voice/stats", headers=admin_headers)
    assert stats.status_code == 200
    assert int(stats.json()["stats"]["callsToday"]) >= 1

    suppress = client.post(
        "/v1/admin/voice/suppressions",
        headers=admin_headers,
        json={"userId": customer.json()["user"]["id"], "reason": "manual_dnc"},
    )
    assert suppress.status_code == 200

    suppressions = client.get("/v1/admin/voice/suppressions", headers=admin_headers)
    assert suppressions.status_code == 200
    assert any(row["userId"] == customer.json()["user"]["id"] for row in suppressions.json()["suppressions"])

    delete = client.delete(
        f"/v1/admin/voice/suppressions/{customer.json()['user']['id']}",
        headers=admin_headers,
    )
    assert delete.status_code == 204
