from fastapi.testclient import TestClient

from app.main import app


def _create_session(client: TestClient) -> str:
    response = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert response.status_code == 201
    return response.json()["sessionId"]


def test_interaction_search_and_add_to_cart_guest() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    search = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "Show me running shoes under $150",
            "channel": "web",
        },
    )
    assert search.status_code == 200
    payload = search.json()["payload"]
    assert payload["agent"] == "product"
    assert len(payload["data"]["products"]) >= 1

    add = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    assert add.status_code == 200
    assert add.json()["payload"]["agent"] == "cart"

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["itemCount"] >= 1


def test_interaction_checkout_requires_auth_then_succeeds() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    search = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "show me running shoes", "channel": "web"},
    )
    assert search.status_code == 200

    add = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    assert add.status_code == 200

    guest_checkout = client.post(
        "/v1/interactions/message",
        json={"sessionId": session_id, "content": "checkout", "channel": "web"},
    )
    assert guest_checkout.status_code == 200
    assert guest_checkout.json()["payload"]["data"]["code"] == "AUTH_REQUIRED"

    auth = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "interaction-checkout@example.com",
            "password": "SecurePass123!",
            "name": "Interaction User",
        },
    )
    assert auth.status_code == 201
    token = auth.json()["accessToken"]

    user_checkout = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"sessionId": session_id, "content": "checkout", "channel": "web"},
    )
    assert user_checkout.status_code == 200
    payload = user_checkout.json()["payload"]
    assert payload["agent"] == "order"
    assert payload["data"]["order"]["status"] == "confirmed"


def test_interaction_parallel_multi_status() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    auth = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "parallel-status@example.com",
            "password": "SecurePass123!",
            "name": "Parallel User",
        },
    )
    assert auth.status_code == 201
    token = auth.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}"}

    client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={"sessionId": session_id, "content": "show me running shoes", "channel": "web"},
    )
    client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={"sessionId": session_id, "content": "add to cart", "channel": "web"},
    )
    client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={"sessionId": session_id, "content": "checkout", "channel": "web"},
    )

    combined = client.post(
        "/v1/interactions/message",
        headers=auth_header,
        json={
            "sessionId": session_id,
            "content": "show my cart and order status",
            "channel": "web",
        },
    )
    assert combined.status_code == 200
    payload = combined.json()["payload"]
    assert payload["agent"] == "orchestrator"
    assert "cart" in payload["data"]
    assert "order" in payload["data"]


def test_interaction_single_message_search_and_add_to_cart() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "find running shoes under $150 and add to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "orchestrator"
    assert "product" in payload["data"]
    assert "cart" in payload["data"]

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["itemCount"] >= 1


def test_interaction_apply_discount_code() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    seed = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "find running shoes and add to cart",
            "channel": "web",
        },
    )
    assert seed.status_code == 200

    discount = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "apply discount code SAVE20",
            "channel": "web",
        },
    )
    assert discount.status_code == 200
    payload = discount.json()["payload"]
    assert payload["agent"] == "cart"
    assert "saved" in payload["message"].lower()

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert float(cart.json()["discount"]) > 0.0


def test_interaction_order_issue_phrase_routes_to_order_agent() -> None:
    client = TestClient(app)
    session_id = _create_session(client)
    auth = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "order-issue@example.com",
            "password": "SecurePass123!",
            "name": "Order Issue User",
        },
    )
    assert auth.status_code == 201
    token = auth.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}", "X-Session-Id": session_id}

    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    order = client.post(
        "/v1/orders",
        headers={**auth_header, "Idempotency-Key": "order-issue-key-1"},
        json={
            "shippingAddress": {
                "name": "Issue User",
                "line1": "100 Market St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_issue"},
        },
    )
    assert order.status_code == 201

    issue = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"sessionId": session_id, "content": "my order hasn't arrived yet", "channel": "web"},
    )
    assert issue.status_code == 200
    payload = issue.json()["payload"]
    assert payload["agent"] == "order"
    assert "latest order" in payload["message"].lower()


def test_interaction_change_order_address_when_allowed() -> None:
    client = TestClient(app)
    session_id = _create_session(client)
    auth = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": "address-change@example.com",
            "password": "SecurePass123!",
            "name": "Address User",
        },
    )
    assert auth.status_code == 201
    token = auth.json()["accessToken"]
    auth_header = {"Authorization": f"Bearer {token}", "X-Session-Id": session_id}

    add_item = client.post(
        "/v1/cart/items",
        headers=auth_header,
        json={"productId": "prod_001", "variantId": "var_001", "quantity": 1},
    )
    assert add_item.status_code == 201

    order = client.post(
        "/v1/orders",
        headers={**auth_header, "Idempotency-Key": "address-change-key-1"},
        json={
            "shippingAddress": {
                "name": "Address User",
                "line1": "100 Market St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
            "paymentMethod": {"type": "card", "token": "pm_address"},
        },
    )
    assert order.status_code == 201
    order_id = order.json()["order"]["id"]

    update = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sessionId": session_id,
            "content": (
                f"change order {order_id} address "
                "line1=500 Main St, city=Austin, state=TX, postalCode=78702, country=US"
            ),
            "channel": "web",
        },
    )
    assert update.status_code == 200
    payload = update.json()["payload"]
    assert payload["agent"] == "order"
    assert payload["data"]["shippingAddress"]["line1"] == "500 Main St"


def test_interaction_add_by_product_name_and_quantity() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add 2 running shoes to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "cart"
    assert "running shoes" in payload["message"].lower()

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["itemCount"] == 2


def test_interaction_add_to_cart_requests_clarification_when_ambiguous() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add shoes to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "cart"
    assert payload["data"]["code"] == "CLARIFICATION_REQUIRED"
    assert "multiple matches" in payload["message"].lower()
    assert len(payload["data"]["options"]) >= 2


def test_interaction_add_by_product_id_requires_variant_clarification() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add prod_001 to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "cart"
    assert payload["data"]["code"] == "CLARIFICATION_REQUIRED"
    assert "size" in payload["message"].lower() or "color" in payload["message"].lower()


def test_interaction_add_by_product_id_with_size_and_color_succeeds() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add prod_001 size 10 color blue to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "cart"
    assert "added" in payload["message"].lower()

def test_interaction_add_multiple_items_in_single_message() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add 2 running shoes and 1 hoodie to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "cart"
    assert "added" in payload["message"].lower()

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    names = [item["name"].lower() for item in cart.json()["items"]]
    assert any("running shoes" in name for name in names)
    assert any("hoodie" in name for name in names)


def test_interaction_adjust_item_quantity_up_and_down() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    seed = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add 2 running shoes to cart",
            "channel": "web",
        },
    )
    assert seed.status_code == 200

    increase = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "increase quantity of running shoes in cart by 2",
            "channel": "web",
        },
    )
    assert increase.status_code == 200
    assert "updated" in increase.json()["payload"]["message"].lower()

    cart_after_increase = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart_after_increase.status_code == 200
    first_item = cart_after_increase.json()["items"][0]
    assert first_item["quantity"] == 4

    decrease = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "decrease quantity of running shoes in cart by 1",
            "channel": "web",
        },
    )
    assert decrease.status_code == 200

    cart_after_decrease = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart_after_decrease.status_code == 200
    assert cart_after_decrease.json()["items"][0]["quantity"] == 3


def test_interaction_clear_cart() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    seed = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add 2 running shoes and 1 hoodie to cart",
            "channel": "web",
        },
    )
    assert seed.status_code == 200

    clear = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "empty my cart",
            "channel": "web",
        },
    )
    assert clear.status_code == 200
    payload = clear.json()["payload"]
    assert payload["agent"] == "cart"
    assert "cleared" in payload["message"].lower()

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["itemCount"] == 0


def test_interaction_remove_partial_quantity_from_cart() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    seed = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add 3 running shoes to cart",
            "channel": "web",
        },
    )
    assert seed.status_code == 200

    remove = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "remove 2 running shoes from cart",
            "channel": "web",
        },
    )
    assert remove.status_code == 200
    assert "remaining quantity is 1" in remove.json()["payload"]["message"].lower()

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["items"][0]["quantity"] == 1


def test_interaction_llm_planner_executes_multi_step_cart_actions(monkeypatch) -> None:
    from app.container import llm_client
    from app.infrastructure.llm_client import LLMActionPlan, LLMPlannedAction

    client = TestClient(app)
    session_id = _create_session(client)

    def fake_plan_actions(*, message: str, recent_messages: list[dict[str, object]] | None = None, inferred_intent: str | None = None) -> LLMActionPlan | None:
        lowered = message.lower()
        if "running shoes" not in lowered:
            return None
        return LLMActionPlan(
            actions=[
                LLMPlannedAction(
                    name="add_item",
                    target_agent="cart",
                    params={"query": "running shoes", "quantity": 2},
                ),
                LLMPlannedAction(
                    name="add_item",
                    target_agent="cart",
                    params={"query": "hoodie", "quantity": 1},
                ),
            ],
            confidence=0.92,
            needs_clarification=False,
            clarification_question="",
        )

    monkeypatch.setattr(llm_client, "plan_actions", fake_plan_actions)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add running shoes and hoodie to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["agent"] == "orchestrator"
    assert payload["metadata"]["planner"]["used"] is True
    assert payload["metadata"]["planner"]["actionCount"] == 2
    assert payload["metadata"]["planner"]["stepCount"] == 2
    assert payload["metadata"]["planner"]["steps"][0]["action"] == "add_item"
    assert payload["metadata"]["planner"]["steps"][0]["targetAgent"] == "cart"

    cart = client.get("/v1/cart", headers={"X-Session-Id": session_id})
    assert cart.status_code == 200
    assert cart.json()["itemCount"] == 3


def test_interaction_planner_atomic_mode_reports_step_errors(monkeypatch) -> None:
    from dataclasses import replace

    from app.container import llm_client
    from app.infrastructure.llm_client import LLMActionPlan, LLMPlannedAction

    client = TestClient(app)
    session_id = _create_session(client)

    planner_settings = replace(
        llm_client.settings,
        llm_enabled=True,
        openrouter_api_key="test-key",
        llm_planner_enabled=True,
        planner_feature_enabled=True,
        planner_canary_percent=100,
        llm_planner_execution_mode="atomic",
    )
    monkeypatch.setattr(llm_client, "settings", planner_settings)

    def fake_plan_actions(*, message: str, recent_messages: list[dict[str, object]] | None = None, inferred_intent: str | None = None) -> LLMActionPlan | None:
        return LLMActionPlan(
            actions=[
                LLMPlannedAction(
                    name="add_item",
                    target_agent="cart",
                    params={"query": "item-does-not-exist", "quantity": 1},
                ),
                LLMPlannedAction(
                    name="add_item",
                    target_agent="cart",
                    params={"query": "running shoes", "quantity": 1},
                ),
            ],
            confidence=0.95,
            needs_clarification=False,
            clarification_question="",
        )

    monkeypatch.setattr(llm_client, "plan_actions", fake_plan_actions)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add items to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    payload = response.json()["payload"]
    planner = payload["metadata"]["planner"]
    assert planner["executionMode"] == "atomic"
    assert planner["stepCount"] == 2
    assert planner["steps"][0]["success"] is False
    assert planner["steps"][0]["error"]["code"] in {"ACTION_FAILED", "CLARIFICATION_REQUIRED"}
    assert planner["steps"][1]["error"]["code"] == "SKIPPED_ATOMIC_MODE"


def test_interaction_planner_canary_zero_disables_planner_attempt(monkeypatch) -> None:
    from dataclasses import replace

    from app.container import llm_client

    client = TestClient(app)
    session_id = _create_session(client)

    planner_settings = replace(
        llm_client.settings,
        llm_enabled=True,
        openrouter_api_key="test-key",
        llm_planner_enabled=True,
        planner_feature_enabled=True,
        planner_canary_percent=0,
    )
    monkeypatch.setattr(llm_client, "settings", planner_settings)

    response = client.post(
        "/v1/interactions/message",
        json={
            "sessionId": session_id,
            "content": "add running shoes and hoodie to cart",
            "channel": "web",
        },
    )
    assert response.status_code == 200
    execution_policy = response.json()["payload"]["metadata"]["executionPolicy"]
    assert execution_policy["plannerEnabled"] is False
    assert execution_policy["plannerAttempted"] is False
