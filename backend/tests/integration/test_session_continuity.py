from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _create_session(client: TestClient, channel: str = "web") -> str:
    response = client.post("/v1/sessions", json={"channel": channel, "initialContext": {}})
    assert response.status_code == 201
    return response.json()["sessionId"]


def test_login_reuses_existing_user_session_for_chat_continuity() -> None:
    client = TestClient(app)
    session_a = _create_session(client, channel="web")
    email = f"continuity-{uuid4().hex}@example.com"
    password = "SecurePass123!"

    register = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_a, "X-Channel": "web"},
        json={"email": email, "password": password, "name": "Continuity User"},
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    assert register.json()["sessionId"] == session_a
    identity = register.json()["user"]["identity"]
    assert identity["anonymousId"] is not None
    assert any(link["provider"] == "web" for link in identity["linkedChannels"])

    search = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"sessionId": session_a, "content": "show me running shoes", "channel": "web"},
    )
    assert search.status_code == 200
    assert search.json()["sessionId"] == session_a
    assert search.json()["payload"]["agent"] == "product"

    session_b = _create_session(client, channel="mobile")
    login = client.post(
        "/v1/auth/login",
        headers={"X-Session-Id": session_b, "X-Channel": "mobile"},
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    assert login.json()["sessionId"] == session_a
    second_token = login.json()["accessToken"]
    linked_channels = login.json()["user"]["identity"]["linkedChannels"]
    assert any(link["provider"] == "mobile" for link in linked_channels)

    add = client.post(
        "/v1/interactions/message",
        headers={"Authorization": f"Bearer {second_token}"},
        json={"sessionId": session_b, "content": "add to cart", "channel": "mobile"},
    )
    assert add.status_code == 200
    assert add.json()["sessionId"] == session_a
    assert add.json()["payload"]["agent"] == "cart"


def test_websocket_switches_to_existing_user_session_when_authenticated() -> None:
    client = TestClient(app)
    session_a = _create_session(client, channel="web")
    email = f"ws-continuity-{uuid4().hex}@example.com"
    password = "SecurePass123!"

    register = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_a, "X-Channel": "web"},
        json={"email": email, "password": password, "name": "WS Continuity User"},
    )
    assert register.status_code == 201
    token = register.json()["accessToken"]
    assert register.json()["sessionId"] == session_a

    session_b = _create_session(client, channel="kiosk")
    with client.websocket_connect(
        f"/ws?sessionId={session_b}",
        headers={"Authorization": f"Bearer {token}"},
    ) as websocket:
        first = websocket.receive_json()
        assert first["type"] == "session"
        assert first["payload"]["sessionId"] == session_a

        websocket.send_json(
            {
                "type": "message",
                "payload": {"content": "show me accessories", "timestamp": "2026-01-01T00:00:00Z"},
            }
        )
        while True:
            event = websocket.receive_json()
            if event["type"] == "response":
                assert event["payload"]["agent"] == "product"
                break
