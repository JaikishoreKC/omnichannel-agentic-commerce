from app.infrastructure.mongo_indexes import MONGO_INDEX_SPECS


def test_mongo_index_specs_cover_repository_collections() -> None:
    required = {
        "runtime_state",
        "users",
        "refresh_tokens",
        "sessions",
        "carts",
        "orders",
        "idempotency_keys",
        "memories",
        "interactions",
        "support_tickets",
        "products",
        "categories",
        "inventory",
        "notifications",
        "admin_activity_logs",
    }
    assert required.issubset(set(MONGO_INDEX_SPECS.keys()))


def test_mongo_index_specs_use_stable_named_indexes() -> None:
    all_names: list[str] = []
    for specs in MONGO_INDEX_SPECS.values():
        for _, options in specs:
            name = options.get("name")
            assert isinstance(name, str)
            assert len(name) > 0
            all_names.append(name)
    assert len(all_names) == len(set(all_names))
