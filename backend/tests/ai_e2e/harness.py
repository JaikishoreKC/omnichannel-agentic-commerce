from __future__ import annotations

import inspect
import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import Lock
from dataclasses import dataclass, replace
from typing import Any, Callable

from fastapi.testclient import TestClient

from app.container import container
from app.main import app


AI_E2E_ROOT = Path(__file__).resolve().parent
TRACE_DIR = AI_E2E_ROOT / "traces"
LLM_RECORDING_DIR = AI_E2E_ROOT / "llm_recordings"


@dataclass
class AiUserContext:
    email: str
    password: str
    session_id: str
    access_token: str
    user_id: str
    default_payment_method: dict[str, Any]


class MutationSpy:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.records.clear()

    def wrap(self, *, component: str, method: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            stack = inspect.stack()
            service_frames = [
                frame.function
                for frame in stack
                if "\\app\\services\\" in frame.filename.replace("/", "\\")
            ]
            caller_frame = next(
                (
                    frame
                    for frame in stack
                    if "\\app\\" in frame.filename.replace("/", "\\")
                    and "\\app\\repositories\\" not in frame.filename.replace("/", "\\")
                ),
                None,
            )
            self.records.append(
                {
                    "component": component,
                    "method": method,
                    "via_service": bool(service_frames),
                    "service_calls": service_frames[:6],
                    "caller": caller_frame.function if caller_frame else "unknown",
                }
            )
            return fn(*args, **kwargs)

        return _wrapped

    def write_events(self) -> list[dict[str, Any]]:
        return [record for record in self.records if record["method"] in {"create", "update", "delete", "upsert", "set_idempotent"}]


class LLMCallRecorder:
    """Record/replay wrapper for llm_client._call_llm to support deterministic E2E runs."""

    def __init__(self, *, mode: str, recordings_dir: Path, fallback_to_live_when_missing: bool = False) -> None:
        self.mode = mode
        self.recordings_dir = recordings_dir
        self.fallback_to_live_when_missing = fallback_to_live_when_missing
        self._lock = Lock()

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode or "live").strip().lower()
        if normalized in {"record", "replay", "live"}:
            return normalized
        return "live"

    def _key(self, *, role: str | None, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "role": str(role or "planner"),
            "system_prompt": str(system_prompt),
            "user_prompt": str(user_prompt),
        }
        digest = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
        return digest

    def _record_path(self, key: str) -> Path:
        return self.recordings_dir / f"{key}.json"

    @staticmethod
    def _extract_message_from_prompt(user_prompt: str) -> str:
        try:
            payload = json.loads(user_prompt)
            if isinstance(payload, dict):
                return str(payload.get("message", "")).strip().lower()
        except json.JSONDecodeError:
            pass
        return str(user_prompt or "").strip().lower()

    def _fallback_replay_response(self, *, user_prompt: str, system_prompt: str, role: str | None) -> str:
        message = self._extract_message_from_prompt(user_prompt)
        system = str(system_prompt or "").lower()
        normalized_role = str(role or "planner").strip().lower()

        if "action" in system and normalized_role == "planner":
            if "show me running shoes" in message:
                return json.dumps(
                    {
                        "actions": [{"name": "search_products", "targetAgent": "product", "params": {"query": "running shoes"}}],
                        "confidence": 0.95,
                        "needsClarification": False,
                        "clarificationQuestion": "",
                    }
                )
            if "add the first running shoe" in message or "add shoes to cart" in message:
                return json.dumps(
                    {
                        "actions": [{"name": "add_item", "targetAgent": "cart", "params": {"query": "running shoes", "quantity": 1}}],
                        "confidence": 0.95,
                        "needsClarification": False,
                        "clarificationQuestion": "",
                    }
                )
            if "what's in my cart" in message or "what is in my cart" in message:
                return json.dumps(
                    {
                        "actions": [{"name": "get_cart", "targetAgent": "cart", "params": {}}],
                        "confidence": 0.95,
                        "needsClarification": False,
                        "clarificationQuestion": "",
                    }
                )
            if "buy everything" in message or "checkout" in message:
                return json.dumps(
                    {
                        "actions": [{"name": "checkout_summary", "targetAgent": "order", "params": {}}],
                        "confidence": 0.95,
                        "needsClarification": False,
                        "clarificationQuestion": "",
                    }
                )
            if "delete all products" in message:
                return json.dumps(
                    {
                        "actions": [],
                        "confidence": 0.6,
                        "needsClarification": True,
                        "clarificationQuestion": "I can help with safe cart and order tasks. Could you clarify what you want to do?",
                    }
                )
            if "maybe i should buy shoes later" in message:
                return json.dumps(
                    {
                        "actions": [],
                        "confidence": 0.5,
                        "needsClarification": True,
                        "clarificationQuestion": "Could you clarify what you want to buy now?",
                    }
                )
            return json.dumps(
                {
                    "actions": [],
                    "confidence": 0.0,
                    "needsClarification": False,
                    "clarificationQuestion": "",
                }
            )

        if "intent" in system and normalized_role == "planner":
            return json.dumps({"intent": "general_question", "confidence": 0.8, "entities": {}})

        return json.dumps({"message": "I couldn't find matching products. Want to broaden filters?"})

    def wrap(self, original: Callable[..., str]) -> Callable[..., str]:
        mode = self._normalize_mode(self.mode)

        def _wrapped(*, user_prompt: str, system_prompt: str, role: str | None = None) -> str:
            key = self._key(role=role, system_prompt=system_prompt, user_prompt=user_prompt)
            target = self._record_path(key)

            if mode == "replay":
                if target.exists():
                    data = json.loads(target.read_text(encoding="utf-8"))
                    return str(data.get("response", ""))
                if not self.fallback_to_live_when_missing:
                    return self._fallback_replay_response(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        role=role,
                    )

            response = original(user_prompt=user_prompt, system_prompt=system_prompt, role=role)

            if mode == "record":
                record = {
                    "key": key,
                    "recordedAt": datetime.now(timezone.utc).isoformat(),
                    "request": {
                        "role": str(role or "planner"),
                        "system_prompt": str(system_prompt),
                        "user_prompt": str(user_prompt),
                    },
                    "response": str(response),
                }
                with self._lock:
                    self.recordings_dir.mkdir(parents=True, exist_ok=True)
                    target.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True), encoding="utf-8")

            return response

        return _wrapped


MUTATION_METHODS: list[tuple[Any, str, str]] = [
    (container.cart_repository, "create", "cart_repository"),
    (container.cart_repository, "update", "cart_repository"),
    (container.cart_repository, "delete", "cart_repository"),
    (container.order_repository, "create", "order_repository"),
    (container.order_repository, "update", "order_repository"),
    (container.order_repository, "set_idempotent", "order_repository"),
    (container.inventory_repository, "upsert", "inventory_repository"),
    (container.inventory_repository, "delete", "inventory_repository"),
    (container.session_repository, "create", "session_repository"),
    (container.session_repository, "update", "session_repository"),
    (container.session_repository, "delete", "session_repository"),
    (container.product_repository, "create", "product_repository"),
    (container.product_repository, "update", "product_repository"),
    (container.product_repository, "delete", "product_repository"),
]


def get_ai_e2e_mode() -> str:
    mode = str(os.getenv("AI_E2E_MODE", "live")).strip().lower()
    if mode in {"live", "record", "replay"}:
        return mode
    return "live"


def ensure_ai_e2e_dirs() -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    LLM_RECORDING_DIR.mkdir(parents=True, exist_ok=True)


def get_real_llm_api_keys_from_env() -> tuple[str, str]:
    planner = str(os.getenv("OPENROUTER_API_KEY_PLANNER", "")).strip()
    general = str(os.getenv("OPENROUTER_API_KEY_GENERAL", "")).strip()
    return planner, general


def configure_real_llm_settings() -> Any:
    planner_key, general_key = get_real_llm_api_keys_from_env()
    if not planner_key or not general_key:
        return None
    original = container.llm_client.settings
    updated = replace(
        original,
        llm_enabled=True,
        llm_planner_enabled=True,
        llm_intent_classifier_enabled=True,
        planner_feature_enabled=True,
        planner_canary_percent=100,
        llm_decision_policy="planner_first",
        llm_timeout_seconds=max(20.0, float(original.llm_timeout_seconds)),
        openrouter_api_key_planner=planner_key,
        openrouter_api_key_general=general_key,
    )
    container.llm_client.settings = updated
    return original


def configure_replay_llm_settings() -> Any:
    """Replay mode does not require API keys but still forces planner/classifier usage."""
    original = container.llm_client.settings
    updated = replace(
        original,
        llm_enabled=True,
        llm_planner_enabled=True,
        llm_intent_classifier_enabled=True,
        planner_feature_enabled=True,
        planner_canary_percent=100,
        llm_decision_policy="planner_first",
        openrouter_api_key_planner="replay-planner",
        openrouter_api_key_general="replay-general",
    )
    container.llm_client.settings = updated
    return original


def restore_llm_settings(original: Any) -> None:
    if original is not None:
        container.llm_client.settings = original


def install_llm_record_replay() -> Callable[[], None]:
    mode = get_ai_e2e_mode()
    if mode not in {"record", "replay"}:
        return lambda: None

    ensure_ai_e2e_dirs()
    original = container.llm_client._call_llm
    wrapper = LLMCallRecorder(mode=mode, recordings_dir=LLM_RECORDING_DIR)
    container.llm_client._call_llm = wrapper.wrap(original)

    def _restore() -> None:
        container.llm_client._call_llm = original

    return _restore


def make_client() -> TestClient:
    return TestClient(app)


def create_test_user_context(client: TestClient, *, email: str, password: str) -> AiUserContext:
    session = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    assert session.status_code == 201, session.text
    session_id = str(session.json()["sessionId"])

    register = client.post(
        "/v1/auth/register",
        headers={"X-Session-Id": session_id},
        json={
            "email": email,
            "password": password,
            "name": "AI E2E User",
            "phone": "+1-555-0100",
            "timezone": "UTC",
        },
    )
    assert register.status_code == 201, register.text
    body = register.json()

    access_token = str(body["accessToken"])
    user_id = str(body["user"]["id"])

    profile = client.patch(
        "/v1/auth/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": "AI E2E User",
            "phone": "+1-555-0100",
            "timezone": "UTC",
            "defaultShippingAddress": {
                "name": "AI E2E User",
                "line1": "100 Test Ave",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
        },
    )
    assert profile.status_code == 200, profile.text

    return AiUserContext(
        email=email,
        password=password,
        session_id=session_id,
        access_token=access_token,
        user_id=user_id,
        default_payment_method={"type": "card", "token": "pm_ai_e2e_default"},
    )


def seed_deterministic_catalog() -> dict[str, Any]:
    category_service = container.category_service
    product_service = container.product_service

    categories = [
        {"id": "running-shoes", "slug": "running-shoes", "name": "Running Shoes", "status": "active"},
        {"id": "laptops", "slug": "laptops", "name": "Laptops", "status": "active"},
        {"id": "headphones", "slug": "headphones", "name": "Headphones", "status": "active"},
        {"id": "phone-cases", "slug": "phone-cases", "name": "Phone Cases", "status": "active"},
    ]
    for category in categories:
        try:
            category_service.create_category(category)
        except Exception:
            pass

    products = [
        {
            "id": "ai_prod_run_001",
            "name": "Velocity Running Shoes",
            "description": "Lightweight running shoes for daily training",
            "category": "running-shoes",
            "brand": "SprintCo",
            "price": 119.0,
            "variants": [{"id": "ai_var_run_001", "size": "9", "color": "blue", "inStock": True, "inventory": {"totalQuantity": 30, "availableQuantity": 30}}],
            "status": "active",
        },
        {
            "id": "ai_prod_lap_001",
            "name": "Atlas Laptop 14",
            "description": "14-inch productivity laptop",
            "category": "laptops",
            "brand": "Atlas",
            "price": 1099.0,
            "variants": [{"id": "ai_var_lap_001", "size": "std", "color": "gray", "inStock": True, "inventory": {"totalQuantity": 8, "availableQuantity": 8}}],
            "status": "active",
        },
        {
            "id": "ai_prod_head_001",
            "name": "Pulse Wireless Headphones",
            "description": "Noise cancelling over-ear headphones",
            "category": "headphones",
            "brand": "Pulse",
            "price": 199.0,
            "variants": [{"id": "ai_var_head_001", "size": "std", "color": "black", "inStock": True, "inventory": {"totalQuantity": 20, "availableQuantity": 20}}],
            "status": "active",
        },
        {
            "id": "ai_prod_case_001",
            "name": "Shield Phone Case",
            "description": "Shockproof phone case",
            "category": "phone-cases",
            "brand": "Shield",
            "price": 29.0,
            "variants": [{"id": "ai_var_case_001", "size": "std", "color": "green", "inStock": True, "inventory": {"totalQuantity": 50, "availableQuantity": 50}}],
            "status": "active",
        },
    ]

    for product in products:
        existing = container.product_repository.get(product["id"])
        if existing:
            product_service.update_product(product_id=product["id"], patch=product)
        else:
            product_service.create_product(product)

    return {"products": products, "categories": categories}


def snapshot_state(*, user_id: str, session_id: str, tracked_variant_ids: list[str] | None = None) -> dict[str, Any]:
    tracked_variant_ids = tracked_variant_ids or ["ai_var_run_001", "ai_var_lap_001", "ai_var_head_001", "ai_var_case_001"]
    cart = container.cart_repository.get_for_user_or_session(user_id=user_id, session_id="")
    orders = container.order_repository.list_by_user(user_id)
    session = container.session_repository.get(session_id)
    inventory = {
        variant_id: container.inventory_repository.get(variant_id)
        for variant_id in tracked_variant_ids
    }
    return {
        "cart_item_count": int(cart.get("itemCount", 0)) if isinstance(cart, dict) else 0,
        "cart_status": str(cart.get("status", "")) if isinstance(cart, dict) else "",
        "order_count": len(orders),
        "session_exists": isinstance(session, dict),
        "inventory": inventory,
    }


def run_interaction(
    client: TestClient,
    *,
    user_ctx: AiUserContext,
    message: str,
    mutation_spy: MutationSpy,
    trace_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mutation_spy.reset()
    before = snapshot_state(user_id=user_ctx.user_id, session_id=user_ctx.session_id)

    response = client.post(
        "/v1/interactions/message",
        headers={
            "Authorization": f"Bearer {user_ctx.access_token}",
            "X-Session-Id": user_ctx.session_id,
        },
        json={
            "sessionId": user_ctx.session_id,
            "content": message,
            "channel": "web",
        },
    )

    after = snapshot_state(user_id=user_ctx.user_id, session_id=user_ctx.session_id)
    payload = response.json().get("payload", {}) if response.headers.get("content-type", "").startswith("application/json") else {}
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}

    trace = {
        "trace_name": trace_name,
        "USER_INPUT": message,
        "HTTP_STATUS": response.status_code,
        "LLM_RESPONSE": {
            "planner": metadata.get("planner", {}),
            "executionPolicy": metadata.get("executionPolicy", {}),
        },
        "INTENT": metadata.get("intent"),
        "SELECTED_TOOL": metadata.get("routingDiagnostics", {}).get("actionNames", []),
        "SERVICE_CALLED": [
            event["service_calls"]
            for event in mutation_spy.write_events()
            if event["service_calls"]
        ],
        "DATABASE_WRITE": mutation_spy.write_events(),
        "FINAL_RESPONSE": {
            "agent": payload.get("agent") if isinstance(payload, dict) else None,
            "message": payload.get("message") if isinstance(payload, dict) else None,
            "data_keys": sorted(list((payload.get("data") or {}).keys())) if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else [],
        },
        "STATE_BEFORE": before,
        "STATE_AFTER": after,
        "AI_E2E_MODE": get_ai_e2e_mode(),
    }
    ensure_ai_e2e_dirs()
    file_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{trace_name}.json"
    target = TRACE_DIR / file_name
    target.write_text(json.dumps(trace, indent=2, sort_keys=True, default=str), encoding="utf-8")
    trace["TRACE_FILE"] = str(target)
    print(json.dumps(trace, indent=2, sort_keys=True, default=str))
    return trace, response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text}


def assert_service_layer_only_mutations(trace: dict[str, Any]) -> None:
    writes = trace.get("DATABASE_WRITE", [])
    for event in writes:
        assert bool(event.get("via_service")), f"Direct repository mutation detected: {event}"
