from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def in_quiet_hours(
    *,
    user: dict[str, Any],
    now: datetime,
    settings: dict[str, Any],
) -> bool:
    tz_name = str(user.get("timezone", "")).strip() or str(settings.get("defaultTimezone", "UTC")).strip()
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    local_now = now.astimezone(zone)
    hour = local_now.hour
    start = int(settings.get("quietHoursStart", 21))
    end = int(settings.get("quietHoursEnd", 8))
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end

def next_non_quiet_time(
    *,
    user: dict[str, Any],
    now: datetime,
    settings: dict[str, Any],
) -> datetime:
    tz_name = str(user.get("timezone", "")).strip() or str(settings.get("defaultTimezone", "UTC")).strip()
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    local_now = now.astimezone(zone)
    start = int(settings.get("quietHoursStart", 21))
    end = int(settings.get("quietHoursEnd", 8))
    if start == end:
        return now + timedelta(minutes=1)

    local_target = local_now.replace(hour=end, minute=0, second=0, microsecond=0)
    if start < end:
        if local_now.hour >= end:
            local_target = local_target + timedelta(days=1)
    else:
        if local_now.hour >= start:
            local_target = local_target + timedelta(days=1)
        elif local_now.hour < end and local_target <= local_now:
            local_target = local_target + timedelta(days=1)

    if local_target <= local_now:
        local_target = local_target + timedelta(minutes=1)
    return local_target.astimezone(timezone.utc)

def budget_and_cap_guardrails(
    *,
    user_id: str,
    settings: dict[str, Any],
    now: datetime,
    voice_service: Any,
) -> str:
    today = now.date().isoformat()
    calls = voice_service.voice_repository.list_calls(limit=5000)

    calls_today = [row for row in calls if str(row.get("createdAt", "")).startswith(today)]
    if len(calls_today) >= int(settings.get("maxCallsPerDay", 0)):
        return "max_calls_per_day_reached"

    user_calls_today = [row for row in calls_today if str(row.get("userId", "")) == user_id]
    if len(user_calls_today) >= int(settings.get("maxCallsPerUserPerDay", 0)):
        return "max_calls_per_user_per_day_reached"

    spend_today = len(calls_today) * float(settings.get("estimatedCostPerCallUsd", 0.0))
    if spend_today + float(settings.get("estimatedCostPerCallUsd", 0.0)) > float(
        settings.get("dailyBudgetUsd", 0.0)
    ):
        return "daily_budget_exceeded"
    return "ok"
