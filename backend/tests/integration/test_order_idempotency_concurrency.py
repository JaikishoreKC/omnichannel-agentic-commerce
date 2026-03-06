from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi.testclient import TestClient

from app.main import app


def test_orders_same_idempotency_key_parallel_requests_return_same_order() -> None:
    client = TestClient(app)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "orders-concurrency@example.com",
            "password": "SecurePass123!",
            "name": "Orders Concurrency",
        },
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}"}

    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    body = {
        "shippingAddress": {
            "name": "Order User",
            "line1": "100 Market St",
            "city": "Austin",
            "state": "TX",
            "postalCode": "78701",
            "country": "US",
        },
        "paymentMethod": {"type": "card", "token": "pm_parallel"},
    }

    def create_order_once() -> tuple[int, str | None]:
        thread_client = TestClient(app)
        response = thread_client.post(
            "/v1/orders",
            headers={**auth_header, "Idempotency-Key": "orders-parallel-key-1"},
            json=body,
        )
        order_id = None
        if response.status_code == 201:
            order_id = response.json().get("order", {}).get("id")
        return response.status_code, order_id

    rows: list[tuple[int, str | None]] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(create_order_once) for _ in range(2)]
        for future in as_completed(futures):
            rows.append(future.result())

    assert len(rows) == 2
    assert all(status == 201 for status, _ in rows)
    order_ids = {order_id for _, order_id in rows if order_id}
    assert len(order_ids) == 1

    listed = client.get("/v1/orders", headers=auth_header)
    assert listed.status_code == 200
    assert len(listed.json().get("orders", [])) == 1
