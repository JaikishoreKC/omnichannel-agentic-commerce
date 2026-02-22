from fastapi.testclient import TestClient

from app.main import app


def test_websocket_message_flow() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "websocket", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json(
            {
                "type": "message",
                "payload": {"content": "show me running shoes", "timestamp": "2026-01-01T00:00:00Z"},
            }
        )
        response = websocket.receive_json()
        assert response["type"] == "response"
        assert response["payload"]["agent"] == "product"
        assert len(response["payload"]["data"]["products"]) >= 1

        websocket.send_json({"type": "typing", "payload": {"isTyping": True}})
        typing = websocket.receive_json()
        assert typing["type"] == "typing"
        assert typing["payload"]["isTyping"] is True


def test_websocket_streaming_flow_when_requested() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "websocket", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json(
            {
                "type": "message",
                "payload": {
                    "content": "show me running shoes",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "stream": True,
                },
            }
        )

        saw_start = False
        saw_delta = False
        saw_end = False
        saw_response = False

        for _ in range(20):
            event = websocket.receive_json()
            event_type = event["type"]
            if event_type == "stream_start":
                saw_start = True
                assert event["payload"]["streamId"].startswith("stream_")
            elif event_type == "stream_delta":
                saw_delta = True
                assert len(str(event["payload"]["delta"])) >= 1
            elif event_type == "stream_end":
                saw_end = True
            elif event_type == "response":
                saw_response = True
                assert event["payload"]["agent"] == "product"
                break

        assert saw_start is True
        assert saw_delta is True
        assert saw_end is True
        assert saw_response is True


def test_websocket_assistant_typing_events_when_requested() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "websocket", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json(
            {
                "type": "message",
                "payload": {
                    "content": "show me running shoes",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "typing": True,
                },
            }
        )

        saw_typing_start = False
        saw_typing_end = False
        saw_response = False
        for _ in range(20):
            event = websocket.receive_json()
            if event["type"] == "typing" and event.get("payload", {}).get("actor") == "assistant":
                if event["payload"].get("isTyping") is True:
                    saw_typing_start = True
                if event["payload"].get("isTyping") is False:
                    saw_typing_end = True
            if event["type"] == "response":
                saw_response = True
                break

        assert saw_typing_start is True
        assert saw_typing_end is True
        assert saw_response is True


def test_websocket_ping_pong_roundtrip() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "websocket", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json({"type": "ping", "payload": {"timestamp": "2026-01-01T00:00:00Z"}})
        event = websocket.receive_json()
        assert event["type"] == "pong"


def test_websocket_reconnect_same_session() -> None:
    client = TestClient(app)
    session = client.post("/v1/sessions", json={"channel": "websocket", "initialContext": {}})
    assert session.status_code == 201
    session_id = session.json()["sessionId"]

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json(
            {
                "type": "message",
                "payload": {"content": "show me running shoes", "timestamp": "2026-01-01T00:00:00Z"},
            }
        )
        while True:
            first = websocket.receive_json()
            if first["type"] == "response":
                break
        assert first["payload"]["agent"] == "product"

    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        websocket.send_json(
            {
                "type": "message",
                "payload": {"content": "show me accessories", "timestamp": "2026-01-01T00:01:00Z"},
            }
        )
        while True:
            second = websocket.receive_json()
            if second["type"] == "response":
                break
        assert second["payload"]["agent"] == "product"
