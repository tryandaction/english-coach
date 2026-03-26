from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any, Optional

from . import store
from .models import DailyMemorySnapshot, LearnerMemoryFact, VocabMemoryState


class LearnerMemoryService:
    def __init__(self, db: sqlite3.Connection, profile: Any | None = None) -> None:
        self._db = db
        self.profile = profile
        store.ensure_memory_schema(self._db)

    @property
    def user_id(self) -> str:
        return str(getattr(self.profile, "user_id", "") or "")

    def remember_fact(
        self,
        fact_type: str,
        fact_key: str,
        value: Any,
        *,
        source: str = "manual",
        confidence: float = 1.0,
        user_id: Optional[str] = None,
    ) -> LearnerMemoryFact:
        uid = user_id or self.user_id
        fact = store.upsert_fact(
            self._db,
            user_id=uid,
            fact_type=fact_type,
            fact_key=fact_key,
            value=value,
            source=source,
            confidence=confidence,
        )
        store.append_event(
            self._db,
            user_id=uid,
            event_type="manual_memory",
            payload={"fact_type": fact.fact_type, "fact_key": fact.fact_key, "value": fact.value},
        )
        return fact

    def facts(self, fact_type: Optional[str] = None, *, user_id: Optional[str] = None, limit: int = 50) -> list[LearnerMemoryFact]:
        uid = user_id or self.user_id
        return store.list_facts(self._db, uid, fact_type=fact_type, limit=limit)

    def record_vocab_enrollment(self, user_id: str, word_ids: list[str]) -> int:
        return store.bootstrap_vocab_states(self._db, user_id, word_ids)

    def set_vocab_status(
        self,
        user_id: str,
        word_id: str,
        status: str,
        *,
        source: Optional[str] = None,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        tags: Optional[list[str]] = None,
        due_for_review: Optional[str] = None,
    ) -> Optional[VocabMemoryState]:
        current = store.bootstrap_vocab_state(self._db, user_id, word_id)
        if not current:
            return None
        updated = store.upsert_vocab_state(
            self._db,
            user_id=user_id,
            word_id=word_id,
            status=status,
            source=source if source is not None else current.source,
            topic=topic if topic is not None else current.topic,
            difficulty=difficulty if difficulty is not None else current.difficulty,
            tags=tags if tags is not None else current.tags,
            wrong_count=current.wrong_count,
            success_count=current.success_count,
            last_seen_at=store.iso_now(),
            due_for_review=due_for_review if due_for_review is not None else current.due_for_review,
        )
        store.append_event(
            self._db,
            user_id=user_id,
            event_type="manual_vocab_state",
            mode="chat",
            word_id=word_id,
            payload={
                "word": updated.word,
                "status": updated.status,
                "source": updated.source,
                "tags": updated.tags,
            },
        )
        return updated

    def review_due_list(self, user_id: Optional[str] = None, *, limit: int = 50) -> list[VocabMemoryState]:
        uid = user_id or self.user_id
        return store.review_due_list(self._db, uid, limit=limit)

    def frequent_forgetting_list(
        self,
        user_id: Optional[str] = None,
        *,
        min_wrong_count: int = 3,
        limit: int = 50,
    ) -> list[VocabMemoryState]:
        uid = user_id or self.user_id
        return store.frequent_forgetting_list(self._db, uid, min_wrong_count=min_wrong_count, limit=limit)

    def _derive_vocab_status(self, quality: int, repetitions: int, total_reviews: int, correct_reviews: int) -> str:
        if quality <= 2:
            return "unknown"
        if repetitions >= 3:
            return "known"
        accuracy = (correct_reviews / total_reviews) if total_reviews else 0.0
        if total_reviews >= 4 and accuracy >= 0.8:
            return "known"
        return "unsure"

    def record_vocab_review(self, card_id: str, quality: int, *, response_ms: int = 0) -> Optional[VocabMemoryState]:
        row = self._db.execute(
            """
            SELECT c.user_id, c.word_id, c.repetitions, c.total_reviews, c.correct_reviews, c.due_date,
                   v.word, v.source, v.topic, v.difficulty, v.exam_type, v.subject_domain
            FROM srs_cards c
            JOIN vocabulary v ON v.word_id = c.word_id
            WHERE c.card_id=?
            """,
            (card_id,),
        ).fetchone()
        if not row:
            return None
        current = store.bootstrap_vocab_state(self._db, row["user_id"], row["word_id"])
        if not current:
            return None
        correct = quality >= 3
        updated = store.upsert_vocab_state(
            self._db,
            user_id=row["user_id"],
            word_id=row["word_id"],
            word=row["word"],
            status=self._derive_vocab_status(
                quality=int(quality),
                repetitions=int(row["repetitions"] or 0),
                total_reviews=int(row["total_reviews"] or 0),
                correct_reviews=int(row["correct_reviews"] or 0),
            ),
            source=row["source"] or "",
            topic=row["topic"] or "general",
            difficulty=row["difficulty"] or "B1",
            tags=store.derive_tags(row),
            wrong_count=current.wrong_count + (0 if correct else 1),
            success_count=current.success_count + (1 if correct else 0),
            last_seen_at=store.iso_now(),
            due_for_review=row["due_date"] or "",
        )
        store.append_event(
            self._db,
            user_id=row["user_id"],
            event_type="vocab_review",
            mode="vocab",
            word_id=row["word_id"],
            payload={
                "word": row["word"],
                "quality": int(quality),
                "correct": bool(correct),
                "response_ms": int(response_ms),
                "status": updated.status,
                "due_for_review": updated.due_for_review,
                "wrong_count": updated.wrong_count,
                "success_count": updated.success_count,
            },
        )
        return updated

    def record_session_completion(
        self,
        session_id: str,
        mode: str,
        duration_sec: int,
        items_done: int,
        accuracy: float,
        *,
        content_json: str | None = None,
        user_id: Optional[str] = None,
    ) -> None:
        uid = user_id or self.user_id
        payload = {}
        if content_json:
            try:
                payload = json.loads(content_json)
            except Exception:
                payload = {}
        compact = {
            "duration_sec": int(duration_sec),
            "items_done": int(items_done),
            "accuracy": round(float(accuracy), 4),
            "result_headline": str(payload.get("result_headline", payload.get("result_card", "")) or "").strip(),
            "improved_point": str(payload.get("improved_point", "") or "").strip(),
            "next_step": str(payload.get("next_step", payload.get("tomorrow_reason", "")) or "").strip(),
        }
        store.append_event(
            self._db,
            user_id=uid,
            event_type="session_completed",
            mode=mode,
            session_id=session_id,
            payload=compact,
        )

    def refresh_daily_memory(self, *, user_id: Optional[str] = None, memory_date: Optional[str] = None) -> DailyMemorySnapshot:
        uid = user_id or self.user_id
        day = memory_date or date.today().isoformat()
        session_row = self._db.execute(
            """
            SELECT COUNT(*) AS sessions,
                   COALESCE(SUM(duration_sec), 0) AS duration_sec,
                   COALESCE(SUM(items_done), 0) AS items_done,
                   COALESCE(AVG(accuracy), 0) AS avg_accuracy
            FROM sessions
            WHERE user_id=? AND date(COALESCE(ended_at, started_at))=?
            """,
            (uid, day),
        ).fetchone()
        mode_rows = self._db.execute(
            """
            SELECT mode, COUNT(*) AS count
            FROM sessions
            WHERE user_id=? AND date(COALESCE(ended_at, started_at))=?
            GROUP BY mode
            """,
            (uid, day),
        ).fetchall()
        latest_session = self._db.execute(
            """
            SELECT content_json
            FROM sessions
            WHERE user_id=? AND date(COALESCE(ended_at, started_at))=?
            ORDER BY COALESCE(ended_at, started_at) DESC
            LIMIT 1
            """,
            (uid, day),
        ).fetchone()
        latest_payload = {}
        if latest_session and latest_session["content_json"]:
            try:
                latest_payload = json.loads(latest_session["content_json"])
            except Exception:
                latest_payload = {}
        due_count_row = self._db.execute(
            """
            SELECT COUNT(*) AS count
            FROM learner_vocab_state
            WHERE user_id=? AND due_for_review <> '' AND due_for_review <= ?
            """,
            (uid, day),
        ).fetchone()
        summary = {
            "sessions": int(session_row["sessions"] or 0),
            "minutes": int((session_row["duration_sec"] or 0) // 60),
            "items": int(session_row["items_done"] or 0),
            "avg_accuracy": round(float(session_row["avg_accuracy"] or 0) * 100, 1),
            "modes": {str(row["mode"]): int(row["count"] or 0) for row in mode_rows},
            "review_due": int(due_count_row["count"] or 0),
            "result_headline": str(latest_payload.get("result_headline", latest_payload.get("result_card", "")) or "").strip(),
            "improved_point": str(latest_payload.get("improved_point", "") or "").strip(),
            "next_step": str(latest_payload.get("next_step", latest_payload.get("tomorrow_reason", "")) or "").strip(),
        }
        return store.write_daily_memory(self._db, uid, day, summary)

    def memory_summary(self, *, user_id: Optional[str] = None) -> dict[str, Any]:
        uid = user_id or self.user_id
        return store.memory_summary(self._db, uid)
