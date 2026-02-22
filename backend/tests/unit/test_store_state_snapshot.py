from app.store.in_memory import InMemoryStore


def test_store_state_export_import_roundtrip() -> None:
    source = InMemoryStore()
    source.sessions_by_id["session_custom"] = {
        "id": "session_custom",
        "userId": None,
        "channel": "web",
        "createdAt": source.iso_now(),
        "lastActivity": source.iso_now(),
        "expiresAt": source.iso_now(),
        "context": {},
    }
    source.carts_by_id["cart_custom"] = {
        "id": "cart_custom",
        "userId": None,
        "sessionId": "session_custom",
        "items": [],
        "subtotal": 0,
        "tax": 0,
        "shipping": 0,
        "discount": 0,
        "total": 0,
        "itemCount": 0,
        "currency": "USD",
        "appliedDiscount": None,
        "createdAt": source.iso_now(),
        "updatedAt": source.iso_now(),
    }

    snapshot = source.export_state()

    target = InMemoryStore()
    target.import_state(snapshot)

    assert "session_custom" in target.sessions_by_id
    assert "cart_custom" in target.carts_by_id
