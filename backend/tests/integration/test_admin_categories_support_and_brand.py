from fastapi.testclient import TestClient

from app.main import app


def _admin_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_admin_category_crud_and_activity_logging() -> None:
    client = TestClient(app)
    headers = _admin_headers(client)

    create = client.post(
        "/v1/admin/categories",
        headers=headers,
        json={"id": "fitness-gear", "name": "Fitness Gear", "description": "Workout essentials"},
    )
    assert create.status_code == 201
    created = create.json()["category"]
    assert created["slug"] == "fitness-gear"

    categories = client.get("/v1/admin/categories", headers=headers)
    assert categories.status_code == 200
    assert "fitness-gear" in categories.json()["categories"]

    update = client.put(
        "/v1/admin/categories/fitness-gear",
        headers=headers,
        json={"slug": "fitness-core", "name": "Fitness Core"},
    )
    assert update.status_code == 200
    assert update.json()["category"]["slug"] == "fitness-core"

    records = client.get("/v1/admin/categories/records?status=active", headers=headers)
    assert records.status_code == 200
    slugs = [row["slug"] for row in records.json()["categories"]]
    assert "fitness-core" in slugs

    delete = client.delete("/v1/admin/categories/fitness-core", headers=headers)
    assert delete.status_code == 204

    activity = client.get("/v1/admin/activity?limit=30", headers=headers)
    assert activity.status_code == 200
    rows = activity.json()["logs"]
    actions = [row["action"] for row in rows]
    assert "category_create" in actions
    assert "category_update" in actions
    assert "category_delete" in actions


def test_support_ticket_lifecycle_via_chat_and_admin() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    open_ticket = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "I need a human agent for a payment issue",
            "channel": "web",
        },
    )
    assert open_ticket.status_code == 200
    payload = open_ticket.json()["payload"]
    assert payload["agent"] == "support"
    ticket_id = payload["data"]["ticket"]["id"]
    assert payload["data"]["ticket"]["status"] == "open"

    status = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "ticket status", "channel": "web"},
    )
    assert status.status_code == 200
    assert status.json()["payload"]["agent"] == "support"

    admin_update = client.patch(
        f"/v1/admin/support/tickets/{ticket_id}",
        headers=_admin_headers(client),
        json={"status": "in_progress", "note": "Assigned to specialist"},
    )
    assert admin_update.status_code == 200
    assert admin_update.json()["ticket"]["status"] == "in_progress"

    close_ticket = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": f"close ticket {ticket_id}",
            "channel": "web",
        },
    )
    assert close_ticket.status_code == 200
    assert close_ticket.json()["payload"]["data"]["ticket"]["status"] == "resolved"


def test_product_brand_filter_and_brand_search() -> None:
    client = TestClient(app)

    by_brand = client.get("/v1/products?brand=AeroThread")
    assert by_brand.status_code == 200
    products = by_brand.json()["products"]
    assert len(products) >= 1
    assert all(str(product.get("brand", "")).lower() == "aerothread" for product in products)

    session = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]
    search = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "show me aerothread products",
            "channel": "web",
        },
    )
    assert search.status_code == 200
    payload = search.json()["payload"]
    assert payload["agent"] == "product"
    returned = payload["data"]["products"]
    assert len(returned) >= 1
    assert all(str(product.get("brand", "")).lower() == "aerothread" for product in returned)
