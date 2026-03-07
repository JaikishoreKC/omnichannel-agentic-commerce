from fastapi.testclient import TestClient

from app.main import app


def test_admin_stats_requires_admin_role() -> None:
    client = TestClient(app)

    customer = client.post(
        "/v1/auth/register",
        json={
            "email": "customer-stats@example.com",
            "password": "SecurePass123!",
            "name": "Customer Stats",
        },
    )
    assert customer.status_code == 201
    customer_token = customer.json()["accessToken"]

    forbidden = client.get(
        "/v1/admin/stats",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    assert forbidden.status_code == 403

    admin = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert admin.status_code == 200
    admin_token = admin.json()["accessToken"]

    stats = client.get(
        "/v1/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert stats.status_code == 200
    payload = stats.json()
    assert "totalRevenue" in payload
    assert "activeUsers" in payload
    assert "pendingOrders" in payload
    assert "totalProducts" in payload
    assert "activeSessions" in payload
    assert "topProducts" in payload
    assert "messagesToday" in payload
    assert "agentPerformance" in payload
