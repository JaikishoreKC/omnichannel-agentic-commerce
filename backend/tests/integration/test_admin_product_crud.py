from fastapi.testclient import TestClient

from app.main import app


def test_admin_can_manage_products() -> None:
    client = TestClient(app)

    admin_login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["accessToken"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    create = client.post(
        "/v1/admin/products",
        headers=headers,
        json={
            "id": "prod_900001",
            "name": "Admin Managed Tee",
            "description": "Created through admin API",
            "category": "clothing",
            "price": 44.99,
            "currency": "USD",
            "images": [],
            "variants": [
                {"id": "var_900001", "size": "M", "color": "black", "inStock": True}
            ],
            "rating": 0,
            "reviewCount": 0,
        },
    )
    assert create.status_code == 201
    assert create.json()["product"]["id"] == "prod_900001"

    update = client.put(
        "/v1/admin/products/prod_900001",
        headers=headers,
        json={
            "name": "Admin Managed Tee v2",
            "price": 49.99,
            "status": "draft",
        },
    )
    assert update.status_code == 200
    assert update.json()["product"]["name"] == "Admin Managed Tee v2"
    assert update.json()["product"]["price"] == 49.99
    assert update.json()["product"]["status"] == "draft"
    # Omitted fields should remain unchanged for partial updates.
    assert update.json()["product"]["category"] == "clothing"
    assert len(update.json()["product"].get("variants", [])) == 1
    assert update.json()["product"]["variants"][0]["id"] == "var_900001"

    replace_variants = client.put(
        "/v1/admin/products/prod_900001",
        headers=headers,
        json={
            "variants": [
                {"id": "var_900002", "size": "S", "color": "white", "inStock": True}
            ]
        },
    )
    assert replace_variants.status_code == 200
    payload = replace_variants.json()["product"]
    assert len(payload.get("variants", [])) == 1
    assert payload["variants"][0]["id"] == "var_900002"

    invalid_status = client.put(
        "/v1/admin/products/prod_900001",
        headers=headers,
        json={"status": "invalid"},
    )
    assert invalid_status.status_code == 400

    categories = client.get("/v1/admin/categories", headers=headers)
    assert categories.status_code == 200
    assert "clothing" in categories.json()["categories"]

    delete = client.delete("/v1/admin/products/prod_900001", headers=headers)
    assert delete.status_code == 204

    missing = client.get("/v1/products/prod_900001")
    assert missing.status_code == 404

