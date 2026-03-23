from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.coach.service import CoachNotificationDispatcher, CoachService
from gui.coach_runtime import build_coach_runtime
from gui.deps import get_user_components

router = APIRouter(prefix="/api/coach", tags=["coach"])


class CoachSettingsRequest(BaseModel):
    preferred_study_time: str = "20:00"
    quiet_hours: dict = {"start": "22:30", "end": "08:00"}
    reminder_level: str = "basic"
    desktop_enabled: bool = True
    bark_enabled: bool = False
    webhook_enabled: bool = False
    bark_key: str = ""
    webhook_url: str = ""


class DismissRequest(BaseModel):
    event_id: str


def _service() -> CoachService:
    user_model, profile = get_user_components()
    if not profile:
        raise HTTPException(400, "No profile")
    return CoachService(user_model, profile, build_coach_runtime())


def _empty_status() -> dict:
    settings = {
        "preferred_study_time": "20:00",
        "quiet_hours": {"start": "22:30", "end": "08:00"},
        "reminder_level": "basic",
        "desktop_enabled": True,
        "bark_enabled": False,
        "webhook_enabled": False,
        "bark_key": "",
        "webhook_url": "",
    }
    return {
        "tier": "free",
        "stage": "growth",
        "settings": settings,
        "plan": {"tasks": [], "summary": {}, "stage": "growth", "status": "planned"},
        "coach_summary": {},
        "recent_notifications": [],
        "next_notification": None,
        "catch_up": "",
        "channel_capabilities": {"desktop": True, "bark": False, "webhook": False},
    }


def _fallback_status(service: CoachService) -> dict:
    empty = _empty_status()
    empty["tier"] = service.tier()
    empty["settings"] = service.get_settings()
    empty["channel_capabilities"] = service.channel_capabilities()
    return empty


@router.get("/status")
def get_status():
    try:
        service = _service()
    except HTTPException:
        return _empty_status()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(service.build_status)
            return future.result(timeout=5)
    except FuturesTimeoutError:
        return _fallback_status(service)
    except Exception:
        return _fallback_status(service)


@router.get("/settings")
def get_settings():
    try:
        service = _service()
        return {
            "settings": service.get_settings(),
            "tier": service.tier(),
            "channel_capabilities": service.channel_capabilities(),
        }
    except HTTPException:
        empty = _empty_status()
        return {
            "settings": empty["settings"],
            "tier": empty["tier"],
            "channel_capabilities": empty["channel_capabilities"],
        }


@router.post("/settings")
def save_settings(req: CoachSettingsRequest):
    service = _service()
    settings = service.save_settings(req.model_dump())
    return {
        "ok": True,
        "settings": settings,
        "tier": service.tier(),
        "channel_capabilities": service.channel_capabilities(),
    }


@router.post("/test-reminder")
def test_reminder():
    service = _service()
    dispatched = service.test_notification(CoachNotificationDispatcher())
    return {"ok": True, "dispatched": dispatched}


@router.post("/dismiss")
def dismiss(req: DismissRequest):
    ok = _service().dismiss_notification(req.event_id)
    return {"ok": ok}
