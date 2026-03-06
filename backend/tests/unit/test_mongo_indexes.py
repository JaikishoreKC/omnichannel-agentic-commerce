import pytest
from pymongo.errors import OperationFailure

from app.infrastructure.mongo_indexes import MONGO_INDEX_SPECS, _create_or_repair_named_index


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


class _FakeCollection:
    def __init__(self) -> None:
        self.dropped: list[str] = []
        self._existing = {
            "refresh_tokens_token_unique": {
                "key": [("token", 1)],
                "unique": True,
            }
        }
        self._first_call = True

    def create_index(self, keys: list[tuple[str, int]], **options: object) -> str:
        name = str(options.get("name"))
        if self._first_call and name == "refresh_tokens_token_unique":
            self._first_call = False
            raise OperationFailure(
                "conflict",
                code=86,
                details={"codeName": "IndexKeySpecsConflict"},
            )
        self._existing[name] = {"key": list(keys), "unique": bool(options.get("unique", False))}
        return name

    def index_information(self) -> dict[str, dict[str, object]]:
        return self._existing

    def drop_index(self, name: str) -> None:
        self.dropped.append(name)
        self._existing.pop(name, None)


def test_create_or_repair_named_index_replaces_legacy_conflict() -> None:
    collection = _FakeCollection()
    name = _create_or_repair_named_index(
        collection=collection,
        keys=[("tokenHash", 1)],
        options={"name": "refresh_tokens_token_unique", "unique": True},
    )
    assert name == "refresh_tokens_token_unique"
    assert collection.dropped == ["refresh_tokens_token_unique"]
    assert collection.index_information()["refresh_tokens_token_unique"]["key"] == [("tokenHash", 1)]


def test_create_or_repair_named_index_raises_when_existing_name_missing() -> None:
    class _MissingIndexCollection(_FakeCollection):
        def index_information(self) -> dict[str, dict[str, object]]:
            return {}

    with pytest.raises(OperationFailure):
        _create_or_repair_named_index(
            collection=_MissingIndexCollection(),
            keys=[("tokenHash", 1)],
            options={"name": "refresh_tokens_token_unique", "unique": True},
        )
