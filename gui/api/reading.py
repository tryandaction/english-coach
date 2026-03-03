"""Reading comprehension API."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/reading", tags=["reading"])

# ── Pool database ──────────────────────────────────────────────────────────────
_pool_db: Optional[sqlite3.Connection] = None
_pool_lock = threading.Lock()
_POOL_MIN    = 2
_POOL_TARGET = 4
_replenish_task: Optional[asyncio.Task] = None


def _schedule_replenish(exam: str, cefr: str) -> None:
    """Schedule pool replenishment in a background thread (safe from sync context)."""
    def _run():
        try:
            asyncio.run(_maybe_replenish(exam, cefr))
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def _get_pool_db() -> sqlite3.Connection:
    global _pool_db
    if _pool_db is not None:
        return _pool_db
    try:
        from gui.deps import load_config
        import sys
        cfg = load_config()
        raw = cfg.get("data_dir", "data")
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(".")
        data_dir = Path(raw) if Path(raw).is_absolute() else base / raw
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "reading_pool.db"
    except Exception:
        db_path = Path(tempfile.gettempdir()) / "reading_pool.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pool (
            id         TEXT PRIMARY KEY,
            exam       TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            topic      TEXT,
            data_json  TEXT NOT NULL,
            created_at REAL DEFAULT (unixepoch())
        )
    """)
    conn.commit()
    _pool_db = conn
    return conn


def _pool_count(exam: str, difficulty: str) -> int:
    try:
        conn = _get_pool_db()
        with _pool_lock:
            row = conn.execute(
                "SELECT COUNT(*) FROM pool WHERE exam=? AND difficulty=?",
                (exam, difficulty)
            ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _pool_pop(exam: str, difficulty: str) -> Optional[dict]:
    try:
        conn = _get_pool_db()
        with _pool_lock:
            row = conn.execute(
                "SELECT id, data_json FROM pool WHERE exam=? AND difficulty=? ORDER BY RANDOM() LIMIT 1",
                (exam, difficulty)
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT id, data_json FROM pool WHERE exam=? ORDER BY RANDOM() LIMIT 1",
                    (exam,)
                ).fetchone()
            if not row:
                return None
            pid, data_json = row
            conn.execute("DELETE FROM pool WHERE id=?", (pid,))
            conn.commit()
        return json.loads(data_json)
    except Exception:
        return None


def _pool_push(exam: str, difficulty: str, data: dict) -> None:
    try:
        conn = _get_pool_db()
        with _pool_lock:
            conn.execute(
                "INSERT INTO pool (id, exam, difficulty, topic, data_json) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), exam, difficulty, data.get("topic", ""), json.dumps(data))
            )
            conn.commit()
    except Exception:
        pass


async def _replenish_pool(target_exam: str = "general", cefr: str = "B1") -> None:
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        return
    combos = [(target_exam, cefr)] + [
        (e, d) for e, d in [("general","B1"),("toefl","B2"),("ielts","B2"),("gre","C1"),("cet","B1")]
        if (e, d) != (target_exam, cefr)
    ]
    for exam, diff in combos:
        needed = _POOL_TARGET - _pool_count(exam, diff)
        if needed <= 0:
            continue
        for _ in range(needed):
            try:
                seen = user_model.get_seen_ids(profile.user_id) if profile else []
                rows = kb.get_by_type(
                    content_type="reading", difficulty=diff,
                    exam=exam, exclude_ids=seen, limit=10, random_order=True
                )
                if rows:
                    row = max(rows, key=lambda r: len(r["text"]))
                    passage_text = row["text"]
                    chunk_id = row["chunk_id"]
                    questions = []
                    try:
                        meta = json.loads(row.get("metadata_json") or "{}")
                        cached = meta.get("questions")
                        if cached:
                            questions = json.loads(cached) if isinstance(cached, str) else cached
                    except Exception:
                        pass
                    if not questions:
                        questions = ai.generate_comprehension_questions(
                            passage=passage_text, cefr_level=diff,
                            num_questions=5, exam=exam
                        ) or []
                    data = {"passage": passage_text, "chunk_id": chunk_id,
                            "questions": questions, "difficulty": diff,
                            "topic": row.get("topic", ""),
                            "word_count": len(passage_text.split()),
                            "ai_generated": False}
                else:
                    gen = ai.generate_reading_passage(cefr_level=diff, exam=exam)
                    questions = ai.generate_comprehension_questions(
                        passage=gen["passage"], cefr_level=diff,
                        num_questions=5, exam=exam
                    ) or []
                    data = {"passage": gen["passage"],
                            "chunk_id": f"ai_{uuid.uuid4().hex[:8]}",
                            "questions": questions, "difficulty": gen["difficulty"],
                            "topic": gen.get("topic", ""),
                            "word_count": gen["word_count"], "ai_generated": True}
                _pool_push(exam, diff, data)
            except Exception:
                pass
            await asyncio.sleep(0)


async def _maybe_replenish(exam: str, cefr: str) -> None:
    global _replenish_task
    if _pool_count(exam, cefr) < _POOL_MIN:
        if _replenish_task is None or _replenish_task.done():
            _replenish_task = asyncio.create_task(_replenish_pool(exam, cefr))


async def seed_pool_on_startup() -> None:
    """Pre-generate reading sessions on startup using user's exam/level."""
    try:
        from gui.deps import get_components
        _, _, _, _, profile = get_components()
        target_exam = (profile.target_exam or "general").lower() if profile else "general"
        cefr = (profile.cefr_level or "B1") if profile else "B1"
    except Exception:
        target_exam = "general"
        cefr = "B1"
    asyncio.create_task(_replenish_pool(target_exam, cefr))


@dataclass
class ReadingSession:
    session_id: str
    user_id: str
    db_session_id: str
    passage: str
    chunk_id: str
    questions: list
    answered: int = 0
    correct: int = 0
    start_time: float = field(default_factory=time.time)


_sessions: dict[str, ReadingSession] = {}


@router.post("/start")
def start_session(exam: Optional[str] = None):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    target_exam = exam or profile.target_exam or "general"
    cefr = profile.cefr_level or "B1"

    # Try pool first (instant)
    pooled = _pool_pop(target_exam, cefr)
    if pooled:
        passage_text = pooled["passage"]
        questions    = pooled["questions"]
        chunk_id     = pooled["chunk_id"]
        if not pooled.get("ai_generated"):
            user_model.mark_seen(profile.user_id, [chunk_id])
        sid = uuid.uuid4().hex[:12]
        db_sid = user_model.start_session(profile.user_id, "reading")
        _sessions[sid] = ReadingSession(
            session_id=sid, user_id=profile.user_id,
            db_session_id=db_sid, passage=passage_text,
            chunk_id=chunk_id, questions=questions,
        )
        _schedule_replenish(target_exam, cefr)
        return {
            "session_id": sid,
            "passage": passage_text,
            "word_count": pooled.get("word_count", len(passage_text.split())),
            "difficulty": pooled.get("difficulty", cefr),
            "topic": pooled.get("topic", ""),
            "question_count": len(questions),
            "has_questions": len(questions) > 0,
            "ai_generated": pooled.get("ai_generated", False),
        }

    # Pool empty — fall through to on-demand generation
    seen = user_model.get_seen_ids(profile.user_id)

    rows = kb.get_by_type(
        content_type="reading",
        difficulty=profile.cefr_level,
        exam=target_exam,
        exclude_ids=seen,
        limit=6,
        random_order=True,
    )
    if not rows:
        rows = kb.get_by_type(content_type="reading", difficulty=profile.cefr_level, limit=6, random_order=True)
    if not rows:
        # No KB content — generate a passage with AI if available
        if not ai:
            return {"error": "no_passages", "message": "No reading passages found. Please add content files and run ingest, or configure an API key to generate passages automatically."}
        try:
            gen = ai.generate_reading_passage(
                cefr_level=profile.cefr_level,
                exam=target_exam,
            )
        except Exception as e:
            return {"error": "no_passages", "message": f"No reading passages found and AI generation failed: {e}"}
        passage_text = gen["passage"]
        chunk_id = f"ai_generated_{uuid.uuid4().hex[:8]}"
        meta = {"difficulty": gen["difficulty"], "topic": gen["topic"], "chunk_id": chunk_id}
        questions = []
        try:
            questions = ai.generate_comprehension_questions(
                passage=passage_text,
                cefr_level=profile.cefr_level,
                num_questions=5,
                exam=target_exam,
            ) or []
        except Exception:
            questions = []

        # Save AI-generated passage to KB warehouse for future reuse
        try:
            from core.ingestion.pipeline import Chunk, ContentType
            import json as _json
            chunk = Chunk(
                chunk_id=chunk_id,
                source_file="ai_warehouse",
                content_type=ContentType.READING,
                difficulty=gen["difficulty"],
                topic=gen["topic"],
                exam=target_exam,
                language="en",
                text=passage_text,
                metadata={"questions": _json.dumps(questions), "ai_generated": True},
            )
            kb.add_chunks([chunk])
        except Exception:
            pass
        sid = uuid.uuid4().hex[:12]
        db_sid = user_model.start_session(profile.user_id, "reading")
        _sessions[sid] = ReadingSession(
            session_id=sid,
            user_id=profile.user_id,
            db_session_id=db_sid,
            passage=passage_text,
            chunk_id=chunk_id,
            questions=questions,
        )
        _schedule_replenish(target_exam, cefr)
        return {
            "session_id": sid,
            "passage": passage_text,
            "word_count": gen["word_count"],
            "difficulty": gen["difficulty"],
            "topic": gen["topic"],
            "question_count": len(questions),
            "has_questions": len(questions) > 0,
            "ai_generated": True,
        }

    passage_row = max(rows, key=lambda r: len(r["text"]))
    passage_text = passage_row["text"]
    chunk_id = passage_row["chunk_id"]
    user_model.mark_seen(profile.user_id, [chunk_id])

    # Try to reuse cached questions from KB metadata first
    questions = []
    try:
        import json as _json
        meta_json = passage_row["metadata_json"] if hasattr(passage_row, "__getitem__") else None
        if meta_json:
            meta_dict = _json.loads(meta_json)
            cached_q = meta_dict.get("questions")
            if cached_q:
                questions = _json.loads(cached_q) if isinstance(cached_q, str) else cached_q
    except Exception:
        questions = []

    # Generate questions with AI if not cached
    if not questions and ai:
        try:
            questions = ai.generate_comprehension_questions(
                passage=passage_text,
                cefr_level=profile.cefr_level,
                num_questions=5,
                exam=target_exam,
            ) or []
            # Cache questions back into KB metadata
            if questions:
                try:
                    import json as _json
                    existing_meta = {}
                    try:
                        existing_meta = _json.loads(passage_row["metadata_json"] or "{}")
                    except Exception:
                        pass
                    existing_meta["questions"] = _json.dumps(questions)
                    kb._sql.execute(
                        "UPDATE chunks SET metadata_json=? WHERE chunk_id=?",
                        (_json.dumps(existing_meta), chunk_id),
                    )
                    kb._sql.commit()
                except Exception:
                    pass
        except Exception:
            questions = []

    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "reading")
    _sessions[sid] = ReadingSession(
        session_id=sid,
        user_id=profile.user_id,
        db_session_id=db_sid,
        passage=passage_text,
        chunk_id=chunk_id,
        questions=questions,
    )

    meta = passage_row
    asyncio.create_task(_maybe_replenish(target_exam, cefr))
    return {
        "session_id": sid,
        "passage": passage_text,
        "word_count": len(passage_text.split()),
        "difficulty": meta.get("difficulty", "?") if hasattr(meta, "get") else "?",
        "topic": meta.get("topic", "") if hasattr(meta, "get") else "",
        "question_count": len(questions),
        "has_questions": len(questions) > 0,
    }


class AnswerRequest(BaseModel):
    question_index: int
    user_answer: str


@router.post("/answer/{session_id}")
def submit_answer(session_id: str, req: AnswerRequest):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    if req.question_index >= len(sess.questions):
        raise HTTPException(400, "Invalid question index")

    q = sess.questions[req.question_index]
    model_answer = q.get("answer", "")
    options = q.get("options", [])

    # MC question: compare by leading letter (A/B/C/D/E) or full option text
    if options:
        user_letter = req.user_answer.strip()[0].upper() if req.user_answer.strip() else ""
        correct_letter = model_answer.strip()[0].upper() if model_answer.strip() else ""
        correct = user_letter == correct_letter
    else:
        from modes.reading import _keyword_match
        correct = _keyword_match(req.user_answer, model_answer)

    sess.answered += 1
    if correct:
        sess.correct += 1

    last = req.question_index >= len(sess.questions) - 1
    if last:
        kb, srs, user_model, ai, profile = get_components()
        duration = int(time.time() - sess.start_time)
        accuracy = sess.correct / max(sess.answered, 1)
        user_model.record_answer(sess.user_id, "reading_comprehension", accuracy >= 0.67)
        user_model.end_session(sess.db_session_id, duration, sess.answered, accuracy)

    return {
        "correct": correct,
        "model_answer": model_answer,
        "explanation": q.get("explanation", ""),
        "question_type": q.get("type", "factual"),
        "session_complete": last,
        "stats": {"answered": sess.answered, "correct": sess.correct} if last else None,
    }


@router.get("/question/{session_id}/{index}")
def get_question(session_id: str, index: int):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    if index >= len(sess.questions):
        raise HTTPException(400, "No more questions")
    q = sess.questions[index]
    return {
        "index": index,
        "total": len(sess.questions),
        "question": q.get("question", ""),
        "type": q.get("type", "factual"),
        "options": q.get("options", []),
    }
