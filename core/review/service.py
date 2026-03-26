from __future__ import annotations

from datetime import date
from typing import Optional

from core.memory.service import LearnerMemoryService
from .models import ReviewCandidate, ReviewPoolSummary


class ReviewPoolService:
    def __init__(self, db, profile=None) -> None:
        self._db = db
        self.profile = profile
        self.memory = LearnerMemoryService(db, profile)

    @property
    def user_id(self) -> str:
        return str(getattr(self.profile, "user_id", "") or "")

    def _preferred_batch_size(self) -> int:
        prefs = list(getattr(self.profile, "study_preferences", []) or [])
        if "short_tasks" in prefs:
            return 5
        session_minutes = int(getattr(self.profile, "session_minutes", 30) or 30)
        if session_minutes <= 20:
            return 6
        return 8

    def _priority_score(self, item) -> tuple[float, str]:
        today = date.today()
        overdue_days = 0
        is_due_now = False
        if item.due_for_review:
            try:
                due_date = date.fromisoformat(item.due_for_review)
                overdue_days = max((today - due_date).days, 0)
                is_due_now = due_date <= today
            except ValueError:
                overdue_days = 0
        exam = str(getattr(self.profile, "target_exam", "general") or "general").lower()
        exam_match = 2 if exam != "general" and exam in {str(tag).lower() for tag in item.tags} else 0
        status_bonus = {"unknown": 8, "unsure": 5, "known": 0}.get(item.status, 0)
        due_bonus = 20 if is_due_now else 0
        score = due_bonus + overdue_days * 4 + item.wrong_count * 5 + exam_match + status_bonus - item.success_count * 0.5
        if is_due_now:
            reason = "overdue_review"
        elif item.wrong_count >= 3:
            reason = "frequent_forgetting"
        else:
            reason = "weak_vocab"
        return max(score, 0.0), reason

    def summary(self, user_id: Optional[str] = None) -> ReviewPoolSummary:
        uid = user_id or self.user_id
        memory = self.memory.memory_summary(user_id=uid)
        due_total = int(memory.get("review_due_count", 0) or 0)
        forgetting_total = int(memory.get("frequent_forgetting_count", 0) or 0)
        return ReviewPoolSummary(
            due_total=due_total,
            forgetting_total=forgetting_total,
            candidate_total=due_total + forgetting_total,
            recommended_batch_size=self._preferred_batch_size(),
            known_words=int(memory.get("known_words", 0) or 0),
            unsure_words=int(memory.get("unsure_words", 0) or 0),
            unknown_words=int(memory.get("unknown_words", 0) or 0),
        )

    def candidates(self, user_id: Optional[str] = None, limit: int = 20) -> list[ReviewCandidate]:
        uid = user_id or self.user_id
        rows = self._db.execute(
            """
            SELECT *
            FROM learner_vocab_state
            WHERE user_id=?
              AND (
                (due_for_review <> '' AND due_for_review <= ?)
                OR wrong_count >= 3
              )
            ORDER BY
              CASE WHEN due_for_review <> '' AND due_for_review <= ? THEN 0 ELSE 1 END ASC,
              wrong_count DESC,
              success_count ASC,
              updated_at DESC
            LIMIT ?
            """,
            (uid, date.today().isoformat(), date.today().isoformat(), limit),
        ).fetchall()
        items: list[ReviewCandidate] = []
        for row in rows:
            candidate = ReviewCandidate(
                word_id=row["word_id"],
                word=row["word"] or "",
                status=row["status"] or "unknown",
                due_for_review=row["due_for_review"] or "",
                wrong_count=int(row["wrong_count"] or 0),
                success_count=int(row["success_count"] or 0),
                source=row["source"] or "",
                topic=row["topic"] or "general",
                difficulty=row["difficulty"] or "B1",
                tags=[],
            )
            # Read tags directly from row payload to avoid cross-service recursion.
            try:
                import json

                candidate.tags = list(json.loads(row["tags_json"] or "[]"))
            except Exception:
                candidate.tags = []
            candidate.priority_score, candidate.priority_reason = self._priority_score(candidate)
            items.append(candidate)
        return sorted(items, key=lambda item: (-item.priority_score, item.word))

    def recommended_batch(self, user_id: Optional[str] = None, size: Optional[int] = None) -> list[ReviewCandidate]:
        batch_size = int(size or self._preferred_batch_size())
        return self.candidates(user_id=user_id, limit=batch_size)
