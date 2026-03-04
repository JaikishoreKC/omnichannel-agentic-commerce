from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_memory_service
from app.models.schemas import UpdatePreferencesRequest

router = APIRouter(prefix="/memory", tags=["memory"])
memory_service = get_memory_service()


@router.get("")
def get_memory(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return memory_service.get_memory_snapshot(user_id=str(user["id"]))


@router.get("/preferences")
def get_preferences(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return memory_service.get_preferences(user_id=str(user["id"]))


@router.put("/preferences")
def update_preferences(
    payload: UpdatePreferencesRequest,
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return memory_service.update_preferences(
        user_id=str(user["id"]), updates=payload.model_dump()
    )


@router.get("/history")
def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return memory_service.get_history(user_id=str(user["id"]), limit=limit)


@router.delete("")
def clear_memory(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return memory_service.clear_memory(user_id=str(user["id"]))


@router.delete("/preferences")
def clear_preferences(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return memory_service.clear_preferences(user_id=str(user["id"]))


@router.delete("/preferences/{key}")
def forget_preference(
    key: str,
    value: str | None = Query(default=None),
    user: dict[str, object] = Depends(get_current_user),
) -> dict[str, object]:
    return memory_service.forget_preference(user_id=str(user["id"]), key=key, value=value)


@router.delete("/history")
def clear_history(user: dict[str, object] = Depends(get_current_user)) -> dict[str, object]:
    return memory_service.clear_history(user_id=str(user["id"]))
