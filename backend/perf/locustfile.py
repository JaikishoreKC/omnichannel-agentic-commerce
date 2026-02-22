from __future__ import annotations

import uuid

from locust import HttpUser, between, task


class CommerceUser(HttpUser):
    wait_time = between(0.2, 1.2)

    def on_start(self) -> None:
        response = self.client.post(
            "/v1/sessions",
            json={"channel": "web", "initialContext": {}},
        )
        response.raise_for_status()
        self.session_id = response.json()["sessionId"]

    @task(4)
    def browse_products(self) -> None:
        self.client.get("/v1/products?limit=20", name="GET /v1/products")

    @task(2)
    def interaction_search(self) -> None:
        self.client.post(
            "/v1/interactions/message",
            name="POST /v1/interactions/message",
            json={
                "sessionId": self.session_id,
                "content": "show me running shoes under $150",
                "channel": "web",
            },
        )

    @task(1)
    def guest_cart_add_remove(self) -> None:
        add = self.client.post(
            "/v1/cart/items",
            name="POST /v1/cart/items",
            headers={"X-Session-Id": self.session_id},
            json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
        )
        if add.status_code >= 400:
            return
        cart = self.client.get("/v1/cart", name="GET /v1/cart", headers={"X-Session-Id": self.session_id})
        if cart.status_code >= 400:
            return
        items = cart.json().get("items", [])
        if not items:
            return
        item_id = items[0].get("itemId")
        if not item_id:
            return
        self.client.delete(
            f"/v1/cart/items/{item_id}",
            name="DELETE /v1/cart/items/{item_id}",
            headers={"X-Session-Id": self.session_id},
        )

    @task(1)
    def register_user_flow(self) -> None:
        email = f"load-{uuid.uuid4().hex[:10]}@example.com"
        self.client.post(
            "/v1/auth/register",
            name="POST /v1/auth/register",
            headers={"X-Session-Id": self.session_id},
            json={
                "email": email,
                "password": "SecurePass123!",
                "name": "Load Tester",
            },
        )
