from __future__ import annotations

import threading
from typing import Optional

from core.coach.service import CoachNotificationDispatcher, CoachService
from gui.api.license import build_license_status
from gui.deps import get_user_components
from gui.version import get_version_mode
from utils.logger import get_logger


_logger = get_logger()
_scheduler: Optional["CoachScheduler"] = None


def build_coach_runtime() -> dict:
    runtime = build_license_status()
    if get_version_mode() != "cloud":
        runtime["active"] = False
        runtime["cloud_license_active"] = False
        runtime["cloud_ai_ready"] = False
        runtime["ai_mode"] = "self_key" if runtime.get("has_self_key") else "none"
        runtime["ai_ready"] = bool(runtime.get("has_self_key"))
    return runtime


class CoachScheduler(threading.Thread):
    def __init__(self, interval_sec: int = 60) -> None:
        super().__init__(daemon=True, name="coach-scheduler")
        self.interval_sec = interval_sec
        self.stop_event = threading.Event()
        self.dispatcher = CoachNotificationDispatcher()

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        self.tick()
        while not self.stop_event.wait(self.interval_sec):
            self.tick()

    def tick(self) -> None:
        try:
            user_model, profile = get_user_components()
            if not profile:
                return
            service = CoachService(user_model, profile, build_coach_runtime())
            service.sync_daily_plan()
            service.ensure_notification_schedule()
            service.dispatch_due_notifications(self.dispatcher)
        except Exception as exc:
            _logger.exception(f"Coach scheduler tick failed: {exc}")


def start_coach_scheduler() -> CoachScheduler:
    global _scheduler
    if _scheduler and _scheduler.is_alive():
        return _scheduler
    _scheduler = CoachScheduler()
    _scheduler.start()
    return _scheduler
