from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import get_superu_client, get_voice_recovery_service

router = APIRouter(prefix="/voice", tags=["voice"])
superu_client = get_superu_client()
voice_recovery_service = get_voice_recovery_service()


@router.post("/superu/callback")
async def handle_superu_callback(request: Request) -> dict[str, Any]:
    raw_body = await request.body()
    signature = request.headers.get("X-SuperU-Signature") or request.headers.get("X-Signature")
    timestamp = request.headers.get("X-SuperU-Timestamp") or request.headers.get("X-Timestamp")
    try:
        superu_client.verify_webhook_signature(
            raw_body=raw_body,
            signature_header=signature,
            timestamp_header=timestamp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if not raw_body:
        raise HTTPException(status_code=400, detail="Webhook payload is required")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook payload must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")

    result = voice_recovery_service.ingest_provider_callback(payload=payload)
    if not bool(result.get("accepted", False)):
        raise HTTPException(status_code=400, detail=str(result.get("reason", "Webhook rejected")))
    return {"received": True, **result}
