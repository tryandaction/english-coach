from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime
from typing import Any, Optional

from .models import DailyMemorySnapshot, LearnerMemoryFact, LearningEvent, VocabMemoryState


VALID_FACT_TYPES = {"goal", "preference", "retained_note", "strength", "weakness"}
VALID_VOCAB_STATUSES = {"known", "unsure", "unknown"}


def iso_now(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now()).replace(microsecond=0).isoformat()


def loads_json(raw: Any, default: Any) -> Any:
    if raw in (None, ""):
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        value = json.loads(raw)
    except Exception:
        return default
    return default if value is None else value


def dumps_json(value: Any, default: Any) -> str:
    if value is None:
        value = default
    return json.dumps(value, ensure_ascii=False)


def normalize_fact_type(fact_type: str) -> str:
    value = str(fact_type or "").strip().lower()
    return value if value in VALID_FACT_TYPES else "retained_note"


def normalize_status(status: str) -> str:
    value = str(status or "").strip().lower()
    return value if value in VALID_VOCAB_STATUSES else "unknown"


def fact_from_row(row: sqlite3.Row) -> LearnerMemoryFact:
    return LearnerMemoryFact(
        fact_id=row["fact_id"],
        user_id=row["user_id"],
        fact_type=row["fact_type"],
        fact_key=row["fact_key"],
        value=loads_json(row["value_json"], None),
        source=row["source"] or "manual",
        confidence=float(row["confidence"] or 1.0),
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def vocab_from_row(row: sqlite3.Row) -> VocabMemoryState:
    return VocabMemoryState(
        user_id=row["user_id"],
        word_id=row["word_id"],
        word=row["word"] or "",
        status=normalize_status(row["status"]),
        source=row["source"] or "",
        topic=row["topic"] or "general",
        difficulty=row["difficulty"] or "B1",
        tags=list(loads_json(row["tags_json"], [])),
        wrong_count=int(row["wrong_count"] or 0),
        success_count=int(row["success_count"] or 0),
        last_seen_at=row["last_seen_at"] or "",
        due_for_review=row["due_for_review"] or "",
        updated_at=row["updated_at"] or "",
    )


def ensure_memory_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS learner_memory_facts (
            fact_id      TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            fact_type    TEXT NOT NULL,
            fact_key     TEXT NOT NULL,
            value_json   TEXT NOT NULL,
            source       TEXT DEFAULT 'manual',
            confidence   REAL DEFAULT 1.0,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            UNIQUE(user_id, fact_type, fact_key)
        );

        CREATE TABLE IF NOT EXISTS learner_learning_events (
            event_id      TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            session_id    TEXT DEFAULT '',
            event_type    TEXT NOT NULL,
            mode          TEXT DEFAULT '',
            word_id       TEXT DEFAULT '',
            payload_json  TEXT DEFAULT '{}',
            event_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS learner_vocab_state (
            user_id         TEXT NOT NULL,
            word_id         TEXT NOT NULL,
            word            TEXT DEFAULT '',
            status          TEXT DEFAULT 'unknown',
            source          TEXT DEFAULT '',
            topic           TEXT DEFAULT 'general',
            difficulty      TEXT DEFAULT 'B1',
            tags_json       TEXT DEFAULT '[]',
            wrong_count     INTEGER DEFAULT 0,
            success_count   INTEGER DEFAULT 0,
            last_seen_at    TEXT DEFAULT '',
            due_for_review  TEXT DEFAULT '',
            updated_at      TEXT NOT NULL,
            PRIMARY KEY (user_id, word_id)
        );

        CREATE TABLE IF NOT EXISTS learner_daily_memory (
            user_id       TEXT NOT NULL,
            memory_date   TEXT NOT NULL,
            summary_json  TEXT NOT NULL,
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (user_id, memory_date)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learner_memory_fact_user_type ON learner_memory_facts(user_id, fact_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learner_events_user_time ON learner_learning_events(user_id, event_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learner_vocab_due ON learner_vocab_state(user_id, due_for_review)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learner_vocab_status ON learner_vocab_state(user_id, status)"
    )
    conn.commit()


def upsert_fact(
    conn: sqlite3.Connection,
    user_id: str,
    fact_type: str,
    fact_key: str,
    value: Any,
    source: str = "manual",
    confidence: float = 1.0,
    created_at: Optional[str] = None,
) -> LearnerMemoryFact:
    now = created_at or iso_now()
    fact_type = normalize_fact_type(fact_type)
    fact_key = str(fact_key or "").strip() or fact_type
    conn.execute(
        """
        INSERT INTO learner_memory_facts
            (fact_id, user_id, fact_type, fact_key, value_json, source, confidence, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id, fact_type, fact_key) DO UPDATE SET
            value_json=excluded.value_json,
            source=excluded.source,
            confidence=excluded.confidence,
            updated_at=excluded.updated_at
        """,
        (
            uuid.uuid4().hex[:16],
            user_id,
            fact_type,
            fact_key,
            dumps_json(value, None),
            str(source or "manual").strip() or "manual",
            float(confidence),
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM learner_memory_facts WHERE user_id=? AND fact_type=? AND fact_key=?",
        (user_id, fact_type, fact_key),
    ).fetchone()
    return fact_from_row(row)


def list_facts(
    conn: sqlite3.Connection,
    user_id: str,
    fact_type: Optional[str] = None,
    limit: int = 50,
) -> list[LearnerMemoryFact]:
    if fact_type:
        rows = conn.execute(
            """
            SELECT *
            FROM learner_memory_facts
            WHERE user_id=? AND fact_type=?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, normalize_fact_type(fact_type), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM learner_memory_facts
            WHERE user_id=?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [fact_from_row(row) for row in rows]


def append_event(
    conn: sqlite3.Connection,
    user_id: str,
    event_type: str,
    mode: str = "",
    session_id: str = "",
    word_id: str = "",
    payload: Optional[dict] = None,
    event_at: Optional[str] = None,
) -> LearningEvent:
    event = LearningEvent(
        event_id=uuid.uuid4().hex[:16],
        user_id=user_id,
        event_type=str(event_type or "").strip() or "unknown",
        mode=str(mode or "").strip(),
        session_id=str(session_id or "").strip(),
        word_id=str(word_id or "").strip(),
        payload=payload or {},
        event_at=event_at or iso_now(),
    )
    conn.execute(
        """
        INSERT INTO learner_learning_events
            (event_id, user_id, session_id, event_type, mode, word_id, payload_json, event_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            event.event_id,
            event.user_id,
            event.session_id,
            event.event_type,
            event.mode,
            event.word_id,
            dumps_json(event.payload, {}),
            event.event_at,
        ),
    )
    conn.commit()
    return event


def last_event_at(conn: sqlite3.Connection, user_id: str) -> str:
    row = conn.execute(
        "SELECT MAX(event_at) AS event_at FROM learner_learning_events WHERE user_id=?",
        (user_id,),
    ).fetchone()
    return str(row["event_at"] or "") if row else ""


def get_vocab_state(conn: sqlite3.Connection, user_id: str, word_id: str) -> Optional[VocabMemoryState]:
    row = conn.execute(
        "SELECT * FROM learner_vocab_state WHERE user_id=? AND word_id=?",
        (user_id, word_id),
    ).fetchone()
    return vocab_from_row(row) if row else None


def metadata_for_word(conn: sqlite3.Connection, word_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT word, source, topic, difficulty, exam_type, subject_domain
        FROM vocabulary
        WHERE word_id=?
        """,
        (word_id,),
    ).fetchone()


def derive_tags(row: Optional[sqlite3.Row]) -> list[str]:
    if not row:
        return []
    tags = []
    for value in (row["exam_type"], row["subject_domain"]):
        text = str(value or "").strip().lower()
        if text and text != "general" and text not in tags:
            tags.append(text)
    return tags


def bootstrap_vocab_state(conn: sqlite3.Connection, user_id: str, word_id: str) -> Optional[VocabMemoryState]:
    existing = get_vocab_state(conn, user_id, word_id)
    if existing:
        return existing
    meta = metadata_for_word(conn, word_id)
    due_row = conn.execute(
        "SELECT due_date FROM srs_cards WHERE user_id=? AND word_id=?",
        (user_id, word_id),
    ).fetchone()
    if not meta:
        return None
    return upsert_vocab_state(
        conn,
        user_id=user_id,
        word_id=word_id,
        word=meta["word"],
        status="unknown",
        source=meta["source"] or "",
        topic=meta["topic"] or "general",
        difficulty=meta["difficulty"] or "B1",
        tags=derive_tags(meta),
        wrong_count=0,
        success_count=0,
        last_seen_at="",
        due_for_review=str(due_row["due_date"] or "") if due_row else "",
    )


def bootstrap_vocab_states(conn: sqlite3.Connection, user_id: str, word_ids: list[str]) -> int:
    created = 0
    for word_id in word_ids:
        state = bootstrap_vocab_state(conn, user_id, word_id)
        if state:
            created += 1
    return created


def upsert_vocab_state(
    conn: sqlite3.Connection,
    user_id: str,
    word_id: str,
    *,
    word: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[list[str]] = None,
    wrong_count: Optional[int] = None,
    success_count: Optional[int] = None,
    last_seen_at: Optional[str] = None,
    due_for_review: Optional[str] = None,
) -> VocabMemoryState:
    existing = get_vocab_state(conn, user_id, word_id)
    meta = metadata_for_word(conn, word_id)
    payload = {
        "word": word if word is not None else (existing.word if existing else (meta["word"] if meta else "")),
        "status": normalize_status(status if status is not None else (existing.status if existing else "unknown")),
        "source": source if source is not None else (existing.source if existing else (meta["source"] if meta else "")),
        "topic": topic if topic is not None else (existing.topic if existing else (meta["topic"] if meta else "general")),
        "difficulty": difficulty if difficulty is not None else (existing.difficulty if existing else (meta["difficulty"] if meta else "B1")),
        "tags": tags if tags is not None else (existing.tags if existing else derive_tags(meta)),
        "wrong_count": int(wrong_count if wrong_count is not None else (existing.wrong_count if existing else 0)),
        "success_count": int(success_count if success_count is not None else (existing.success_count if existing else 0)),
        "last_seen_at": last_seen_at if last_seen_at is not None else (existing.last_seen_at if existing else ""),
        "due_for_review": due_for_review if due_for_review is not None else (existing.due_for_review if existing else ""),
        "updated_at": iso_now(),
    }
    conn.execute(
        """
        INSERT INTO learner_vocab_state
            (user_id, word_id, word, status, source, topic, difficulty, tags_json,
             wrong_count, success_count, last_seen_at, due_for_review, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id, word_id) DO UPDATE SET
            word=excluded.word,
            status=excluded.status,
            source=excluded.source,
            topic=excluded.topic,
            difficulty=excluded.difficulty,
            tags_json=excluded.tags_json,
            wrong_count=excluded.wrong_count,
            success_count=excluded.success_count,
            last_seen_at=excluded.last_seen_at,
            due_for_review=excluded.due_for_review,
            updated_at=excluded.updated_at
        """,
        (
            user_id,
            word_id,
            payload["word"],
            payload["status"],
            payload["source"],
            payload["topic"],
            payload["difficulty"],
            dumps_json(payload["tags"], []),
            payload["wrong_count"],
            payload["success_count"],
            payload["last_seen_at"],
            payload["due_for_review"],
            payload["updated_at"],
        ),
    )
    conn.commit()
    return get_vocab_state(conn, user_id, word_id)


def review_due_list(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    due_on_or_before: Optional[str] = None,
    limit: int = 50,
) -> list[VocabMemoryState]:
    cutoff = due_on_or_before or date.today().isoformat()
    rows = conn.execute(
        """
        SELECT *
        FROM learner_vocab_state
        WHERE user_id=? AND due_for_review <> '' AND due_for_review <= ?
        ORDER BY due_for_review ASC, wrong_count DESC, updated_at DESC
        LIMIT ?
        """,
        (user_id, cutoff, limit),
    ).fetchall()
    return [vocab_from_row(row) for row in rows]


def frequent_forgetting_list(
    conn: sqlite3.Connection,
    user_id: str,
    *,
    min_wrong_count: int = 3,
    limit: int = 50,
) -> list[VocabMemoryState]:
    rows = conn.execute(
        """
        SELECT *
        FROM learner_vocab_state
        WHERE user_id=? AND wrong_count >= ? AND status != 'known'
        ORDER BY wrong_count DESC, success_count ASC, updated_at DESC
        LIMIT ?
        """,
        (user_id, int(min_wrong_count), limit),
    ).fetchall()
    return [vocab_from_row(row) for row in rows]


def write_daily_memory(
    conn: sqlite3.Connection,
    user_id: str,
    memory_date: str,
    summary: dict,
) -> DailyMemorySnapshot:
    updated_at = iso_now()
    conn.execute(
        """
        INSERT INTO learner_daily_memory
            (user_id, memory_date, summary_json, updated_at)
        VALUES (?,?,?,?)
        ON CONFLICT(user_id, memory_date) DO UPDATE SET
            summary_json=excluded.summary_json,
            updated_at=excluded.updated_at
        """,
        (user_id, memory_date, dumps_json(summary, {}), updated_at),
    )
    conn.commit()
    return DailyMemorySnapshot(user_id=user_id, memory_date=memory_date, summary=summary, updated_at=updated_at)


def get_daily_memory(
    conn: sqlite3.Connection,
    user_id: str,
    memory_date: Optional[str] = None,
) -> Optional[DailyMemorySnapshot]:
    if memory_date:
        row = conn.execute(
            "SELECT * FROM learner_daily_memory WHERE user_id=? AND memory_date=?",
            (user_id, memory_date),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT *
            FROM learner_daily_memory
            WHERE user_id=?
            ORDER BY memory_date DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return DailyMemorySnapshot(
        user_id=row["user_id"],
        memory_date=row["memory_date"],
        summary=loads_json(row["summary_json"], {}),
        updated_at=row["updated_at"] or "",
    )


def memory_summary(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    facts_count = conn.execute(
        "SELECT COUNT(*) AS count FROM learner_memory_facts WHERE user_id=?",
        (user_id,),
    ).fetchone()["count"]
    due_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM learner_vocab_state
        WHERE user_id=? AND due_for_review <> '' AND due_for_review <= ?
        """,
        (user_id, date.today().isoformat()),
    ).fetchone()["count"]
    forgetting_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM learner_vocab_state
        WHERE user_id=? AND wrong_count >= 3 AND status != 'known'
        """,
        (user_id,),
    ).fetchone()["count"]
    status_rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM learner_vocab_state
        WHERE user_id=?
        GROUP BY status
        """,
        (user_id,),
    ).fetchall()
    status_counts = {str(row["status"]): int(row["count"] or 0) for row in status_rows}
    snapshot = get_daily_memory(conn, user_id)
    return {
        "facts_count": int(facts_count or 0),
        "review_due_count": int(due_count or 0),
        "frequent_forgetting_count": int(forgetting_count or 0),
        "known_words": int(status_counts.get("known", 0)),
        "unsure_words": int(status_counts.get("unsure", 0)),
        "unknown_words": int(status_counts.get("unknown", 0)),
        "last_event_at": last_event_at(conn, user_id),
        "last_daily_snapshot": snapshot.summary if snapshot else {},
    }
