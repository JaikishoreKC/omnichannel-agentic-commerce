from __future__ import annotations

import argparse
import json
import math
from statistics import mean
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient

from app.main import app


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lightweight in-process performance smoke checks.")
    parser.add_argument("--iterations", type=int, default=40, help="Number of samples per HTTP scenario.")
    parser.add_argument("--ws-iterations", type=int, default=20, help="Number of websocket roundtrip samples.")
    parser.add_argument("--products-p95-ms", type=float, default=500.0, help="Max p95 latency for GET /v1/products.")
    parser.add_argument(
        "--interactions-p95-ms",
        type=float,
        default=500.0,
        help="Max p95 latency for POST /v1/interactions/message.",
    )
    parser.add_argument(
        "--ws-roundtrip-p95-ms",
        type=float,
        default=200.0,
        help="Max p95 latency for websocket message->response roundtrip.",
    )
    return parser


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[index]


def _measure_ms(fn: Any) -> tuple[float, Any]:
    start = perf_counter()
    result = fn()
    elapsed_ms = (perf_counter() - start) * 1000.0
    return elapsed_ms, result


def run(
    *,
    iterations: int,
    ws_iterations: int,
    products_p95_ms: float,
    interactions_p95_ms: float,
    ws_roundtrip_p95_ms: float,
) -> dict[str, Any]:
    safe_iterations = max(5, iterations)
    safe_ws_iterations = max(5, ws_iterations)
    client = TestClient(app)

    session_response = client.post("/v1/sessions", json={"channel": "web", "initialContext": {}})
    if session_response.status_code != 201:
        raise RuntimeError("Failed to create test session")
    session_id = session_response.json()["sessionId"]

    products_samples: list[float] = []
    for _ in range(safe_iterations):
        duration_ms, response = _measure_ms(lambda: client.get("/v1/products?limit=20"))
        if response.status_code != 200:
            raise RuntimeError("GET /v1/products failed during performance smoke run")
        products_samples.append(duration_ms)

    interaction_samples: list[float] = []
    for _ in range(safe_iterations):
        duration_ms, response = _measure_ms(
            lambda: client.post(
                "/v1/interactions/message",
                json={
                    "sessionId": session_id,
                    "content": "show me running shoes under $150",
                    "channel": "web",
                },
            )
        )
        if response.status_code != 200:
            raise RuntimeError("POST /v1/interactions/message failed during performance smoke run")
        interaction_samples.append(duration_ms)

    ws_samples: list[float] = []
    with client.websocket_connect(f"/ws?sessionId={session_id}") as websocket:
        for i in range(safe_ws_iterations):
            started = perf_counter()
            websocket.send_json(
                {
                    "type": "message",
                    "payload": {
                        "content": "show me running shoes",
                        "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                    },
                }
            )
            while True:
                event = websocket.receive_json()
                if event.get("type") == "response":
                    break
            ws_samples.append((perf_counter() - started) * 1000.0)

    products_p95 = _percentile(products_samples, 95.0)
    interactions_p95 = _percentile(interaction_samples, 95.0)
    ws_p95 = _percentile(ws_samples, 95.0)

    summary = {
        "iterations": safe_iterations,
        "wsIterations": safe_ws_iterations,
        "products": {
            "avgMs": round(mean(products_samples), 2),
            "p95Ms": round(products_p95, 2),
            "targetP95Ms": products_p95_ms,
            "pass": products_p95 <= products_p95_ms,
        },
        "interactions": {
            "avgMs": round(mean(interaction_samples), 2),
            "p95Ms": round(interactions_p95, 2),
            "targetP95Ms": interactions_p95_ms,
            "pass": interactions_p95 <= interactions_p95_ms,
        },
        "websocketRoundtrip": {
            "avgMs": round(mean(ws_samples), 2),
            "p95Ms": round(ws_p95, 2),
            "targetP95Ms": ws_roundtrip_p95_ms,
            "pass": ws_p95 <= ws_roundtrip_p95_ms,
        },
    }
    summary["pass"] = bool(
        summary["products"]["pass"]
        and summary["interactions"]["pass"]
        and summary["websocketRoundtrip"]["pass"]
    )
    return summary


def main() -> int:
    args = _parser().parse_args()
    result = run(
        iterations=args.iterations,
        ws_iterations=args.ws_iterations,
        products_p95_ms=args.products_p95_ms,
        interactions_p95_ms=args.interactions_p95_ms,
        ws_roundtrip_p95_ms=args.ws_roundtrip_p95_ms,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
