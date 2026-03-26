from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from core.review.service import ReviewPoolService


@dataclass
class LearnerSnapshot:
    user_id: str
    exam: str
    cefr_level: str
    stage: str
    ai_ready: bool
    preferred_style: str
    study_preferences: list[str] = field(default_factory=list)
    long_term_goal: str = ""
    weak_areas: list[str] = field(default_factory=list)
    today_sessions: int = 0
    today_minutes: int = 0
    today_items: int = 0
    plan_status: str = "planned"
    mode_counts: dict[str, int] = field(default_factory=dict)
    recent_mode_accuracy: dict[str, float] = field(default_factory=dict)
    review_due_count: int = 0
    frequent_forgetting_count: int = 0
    deck_total: int = 0
    known_words: int = 0
    unsure_words: int = 0
    unknown_words: int = 0
    review_batch_size: int = 8
    top_review_words: list[str] = field(default_factory=list)
    last_interaction_at: str = ""
    last_output_mode: str = ""
    last_output_at: str = ""


class LearnerContextBuilder:
    def __init__(self, db, profile, *, ai_ready: bool = False, srs=None) -> None:
        self._db = db
        self.profile = profile
        self.ai_ready = ai_ready
        self.srs = srs
        self.review = ReviewPoolService(db, profile)

    def _stage(self) -> str:
        exam_date_text = str(getattr(self.profile, "target_exam_date", "") or "").strip()
        if exam_date_text:
            try:
                days_left = (date.fromisoformat(exam_date_text) - date.today()).days
                if 0 <= days_left <= 30:
                    return "sprint"
            except ValueError:
                pass
        return "core" if int(getattr(self.profile, "total_sessions", 0) or 0) < 3 else "growth"

    def _today_summary(self) -> dict:
        row = self._db.execute(
            """
            SELECT COUNT(*) AS sessions,
                   COALESCE(SUM(duration_sec), 0) AS duration_sec,
                   COALESCE(SUM(items_done), 0) AS items_done
            FROM sessions
            WHERE user_id=? AND date(COALESCE(ended_at, started_at)) = ?
            """,
            (self.profile.user_id, date.today().isoformat()),
        ).fetchone()
        return {
            "sessions": int(row["sessions"] or 0),
            "minutes": int((row["duration_sec"] or 0) // 60),
            "items": int(row["items_done"] or 0),
        }

    def _mode_counts(self) -> dict[str, int]:
        rows = self._db.execute(
            "SELECT mode, COUNT(*) AS count FROM sessions WHERE user_id=? GROUP BY mode",
            (self.profile.user_id,),
        ).fetchall()
        result: dict[str, int] = {}
        for row in rows:
            mode = str(row["mode"] or "").lower()
            if mode.startswith("mock_"):
                mode = "mock"
            result[mode or "other"] = int(row["count"] or 0)
        return result

    def _recent_mode_accuracy(self) -> dict[str, float]:
        rows = self._db.execute(
            """
            SELECT mode, AVG(accuracy) AS avg_accuracy
            FROM (
                SELECT mode, accuracy
                FROM sessions
                WHERE user_id=? AND ended_at IS NOT NULL
                ORDER BY ended_at DESC
                LIMIT 20
            )
            GROUP BY mode
            """,
            (self.profile.user_id,),
        ).fetchall()
        result: dict[str, float] = {}
        for row in rows:
            mode = str(row["mode"] or "").lower()
            if mode.startswith("mock_"):
                mode = "mock"
            result[mode or "other"] = round(float(row["avg_accuracy"] or 0), 4)
        return result

    def _last_interaction_at(self) -> str:
        row = self._db.execute(
            """
            SELECT COALESCE(ended_at, started_at) AS ts
            FROM sessions
            WHERE user_id=?
            ORDER BY COALESCE(ended_at, started_at) DESC
            LIMIT 1
            """,
            (self.profile.user_id,),
        ).fetchone()
        return str(row["ts"] or "") if row else ""

    def _last_output_state(self) -> tuple[str, str]:
        row = self._db.execute(
            """
            SELECT mode, COALESCE(ended_at, started_at) AS ts
            FROM sessions
            WHERE user_id=? AND mode IN ('writing', 'speaking')
            ORDER BY COALESCE(ended_at, started_at) DESC
            LIMIT 1
            """,
            (self.profile.user_id,),
        ).fetchone()
        if not row:
            return "", ""
        return str(row["mode"] or ""), str(row["ts"] or "")

    def _plan_status(self, fallback: str = "planned") -> str:
        row = self._db.execute(
            "SELECT status FROM coach_daily_plan WHERE user_id=? AND plan_date=?",
            (self.profile.user_id, date.today().isoformat()),
        ).fetchone()
        return str(row["status"] or fallback) if row else fallback

    def build(self, *, plan_status: Optional[str] = None) -> LearnerSnapshot:
        summary = self._today_summary()
        review_summary = self.review.summary(self.profile.user_id)
        review_batch = self.review.recommended_batch(self.profile.user_id, size=5)
        deck_total = int(
            self._db.execute(
                "SELECT COUNT(*) AS count FROM srs_cards WHERE user_id=?",
                (self.profile.user_id,),
            ).fetchone()["count"]
            or 0
        )
        last_output_mode, last_output_at = self._last_output_state()
        return LearnerSnapshot(
            user_id=self.profile.user_id,
            exam=str(getattr(self.profile, "target_exam", "general") or "general").lower(),
            cefr_level=str(getattr(self.profile, "cefr_level", "B1") or "B1"),
            stage=self._stage(),
            ai_ready=bool(self.ai_ready),
            preferred_style=str(getattr(self.profile, "preferred_style", "direct") or "direct"),
            study_preferences=list(getattr(self.profile, "study_preferences", []) or []),
            long_term_goal=str(getattr(self.profile, "long_term_goal", "") or ""),
            weak_areas=list(getattr(self.profile, "weak_areas", []) or []),
            today_sessions=summary["sessions"],
            today_minutes=summary["minutes"],
            today_items=summary["items"],
            plan_status=plan_status or self._plan_status(),
            mode_counts=self._mode_counts(),
            recent_mode_accuracy=self._recent_mode_accuracy(),
            review_due_count=review_summary.due_total,
            frequent_forgetting_count=review_summary.forgetting_total,
            deck_total=deck_total,
            known_words=review_summary.known_words,
            unsure_words=review_summary.unsure_words,
            unknown_words=review_summary.unknown_words,
            review_batch_size=review_summary.recommended_batch_size,
            top_review_words=[item.word for item in review_batch],
            last_interaction_at=self._last_interaction_at(),
            last_output_mode=last_output_mode,
            last_output_at=last_output_at,
        )
