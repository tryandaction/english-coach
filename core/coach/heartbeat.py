from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


PROMPT_COOLDOWN_MINUTES = 90
INACTIVITY_HOURS = 24
RECENT_STUDY_WINDOW_HOURS = 4
REVIEW_DUE_THRESHOLD = 8


class HeartbeatAction(str, Enum):
    SILENT = "SILENT"
    NUDGE_REVIEW = "NUDGE_REVIEW"
    NUDGE_NEW_WORDS = "NUDGE_NEW_WORDS"
    MICRO_TEST = "MICRO_TEST"
    ENCOURAGE_AND_WAIT = "ENCOURAGE_AND_WAIT"


@dataclass
class HeartbeatSignals:
    now: datetime
    quiet_now: bool = False
    last_interaction_at: Optional[datetime] = None
    last_prompt_at: Optional[datetime] = None
    today_sessions: int = 0
    plan_status: str = "planned"
    tasks_done: int = 0
    review_due_count: int = 0
    frequent_forgetting_count: int = 0


@dataclass
class HeartbeatDecision:
    action: HeartbeatAction
    reason: str
    task_key: str = ""
    cooldown_until: str = ""

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload


class HeartbeatDecisionService:
    def decide(self, signals: HeartbeatSignals) -> HeartbeatDecision:
        if signals.quiet_now:
            return HeartbeatDecision(action=HeartbeatAction.SILENT, reason="当前处于 quiet hours。")

        if signals.last_prompt_at and signals.now - signals.last_prompt_at < timedelta(minutes=PROMPT_COOLDOWN_MINUTES):
            return HeartbeatDecision(
                action=HeartbeatAction.SILENT,
                reason="最近已经提醒过，先避免重复打扰。",
                cooldown_until=(signals.last_prompt_at + timedelta(minutes=PROMPT_COOLDOWN_MINUTES)).replace(microsecond=0).isoformat(),
            )

        if signals.review_due_count >= REVIEW_DUE_THRESHOLD or signals.frequent_forgetting_count > 0:
            return HeartbeatDecision(
                action=HeartbeatAction.NUDGE_REVIEW,
                reason="复习池已经积压，优先清理到期或高错词。",
                task_key="vocab_review",
            )

        if signals.today_sessions == 0 and (
            signals.last_interaction_at is None
            or signals.now - signals.last_interaction_at >= timedelta(hours=INACTIVITY_HOURS)
        ):
            return HeartbeatDecision(
                action=HeartbeatAction.NUDGE_NEW_WORDS,
                reason="已经一段时间没有形成新的学习进度，先给一个最小启动动作。",
                task_key="daily_plan",
            )

        if (
            signals.today_sessions > 0
            and signals.plan_status != "done"
            and signals.last_interaction_at
            and signals.now - signals.last_interaction_at <= timedelta(hours=RECENT_STUDY_WINDOW_HOURS)
        ):
            return HeartbeatDecision(
                action=HeartbeatAction.MICRO_TEST,
                reason="今天已经开始学习，但还没收口，适合补一个最短 micro task。",
                task_key="micro_test",
            )

        if signals.today_sessions > 0:
            return HeartbeatDecision(
                action=HeartbeatAction.ENCOURAGE_AND_WAIT,
                reason="今天已经有学习记录，先保留连续性，不追加高频提醒。",
                task_key="encourage",
            )

        return HeartbeatDecision(action=HeartbeatAction.SILENT, reason="当前没有比保持安静更有价值的提醒。")
