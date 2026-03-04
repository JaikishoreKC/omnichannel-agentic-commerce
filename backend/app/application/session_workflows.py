from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException


async def get_or_create_session(
    *,
    session_service: Any,
    session_id: str | None,
    channel: str,
    anonymous_id: str | None,
    user_agent: str | None,
    ip_address: str | None,
    source: str,
    referrer: str,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(session_service.get_session, session_id)
    except HTTPException:
        return await asyncio.to_thread(
            session_service.create_session,
            channel=channel,
            initial_context={},
            anonymous_id=anonymous_id,
            user_agent=user_agent,
            ip_address=ip_address,
            metadata={
                "source": source,
                "referrer": referrer,
            },
        )


async def resolve_user_session_and_link_identity(
    *,
    session_service: Any,
    cart_service: Any,
    auth_service: Any,
    user_id: str,
    session: dict[str, Any],
    preferred_session_id: str | None,
    channel: str,
    user_agent: str | None,
    ip_address: str | None,
    source: str,
    referrer: str,
) -> dict[str, Any]:
    anonymous_id = str(session.get("anonymousId", "")).strip() or None
    if preferred_session_id:
        await asyncio.to_thread(
            cart_service.merge_guest_cart_into_user,
            session_id=preferred_session_id,
            user_id=user_id,
        )
    resolved = await asyncio.to_thread(
        session_service.resolve_user_session,
        user_id=user_id,
        preferred_session_id=preferred_session_id or session.get("id"),
        channel=channel,
        anonymous_id=anonymous_id,
        user_agent=user_agent,
        ip_address=ip_address,
        metadata={
            "source": source,
            "referrer": referrer,
        },
    )
    await asyncio.to_thread(
        auth_service.link_identity,
        user_id=user_id,
        channel=channel,
        external_id=str(resolved["id"]),
        anonymous_id=str(resolved.get("anonymousId", "")) or None,
    )
    return resolved
