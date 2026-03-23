"""Reading comprehension API."""
from __future__ import annotations

import asyncio
import json
import re
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

from core.coach.recap import build_reading_recap
from gui.deps import get_components

router = APIRouter(prefix="/api/reading", tags=["reading"])


def _row_value(row, key: str, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        return default


def _parse_questions(value) -> list[dict]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


@dataclass
class PassageRecord:
    chunk_id: str
    chunk_ids: list[str]
    source_file: str
    passage_text: str
    difficulty: str
    topic: str
    subject: str
    exam: str
    metadata: dict
    questions: list[dict]
    question_types: list[str]
    word_count: int
    estimated_time: int
    difficulty_score: int
    source_quality: str
    ai_generated: bool = False
    mock_exam_ready: bool = False


def _json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _preferred_value(values: list, default: str = "", skip_general: bool = False) -> str:
    normalized = [str(value or "").strip() for value in values if str(value or "").strip()]
    if skip_general:
        for value in normalized:
            if value.lower() != "general":
                return value
    return normalized[0] if normalized else default


def _passage_group_key(row) -> str:
    source_file = str(_row_value(row, "source_file", "") or "").strip()
    if source_file and source_file != "ai_warehouse":
        return f"source:{source_file}"
    chunk_id = str(_row_value(row, "chunk_id", "") or "").strip()
    return f"chunk:{chunk_id or source_file or 'unknown'}"


def _fetch_passage_rows(kb, row) -> list:
    group_key = _passage_group_key(row)
    if group_key.startswith("source:"):
        source_file = group_key.split(":", 1)[1]
        rows = kb._sql.execute(
            """SELECT rowid, *
               FROM chunks
               WHERE content_type = 'reading' AND source_file = ?
               ORDER BY rowid ASC""",
            (source_file,),
        ).fetchall()
        if rows:
            return rows

    chunk_id = str(_row_value(row, "chunk_id", "") or "").strip()
    if chunk_id:
        db_row = kb._sql.execute(
            "SELECT rowid, * FROM chunks WHERE chunk_id = ?",
            (chunk_id,),
        ).fetchone()
        if db_row is not None:
            return [db_row]
    return [row]


def _merge_questions(rows: list) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        metadata = _json_object(_row_value(row, "metadata_json", "{}") or "{}")
        for question in _parse_questions(metadata.get("questions")):
            if not isinstance(question, dict):
                continue
            key = str(
                question.get("id")
                or question.get("question")
                or json.dumps(question, sort_keys=True, ensure_ascii=True)
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(question)
    return merged


def _build_passage_record(kb, row) -> Optional[PassageRecord]:
    rows = _fetch_passage_rows(kb, row)
    chunk_ids = [str(_row_value(item, "chunk_id", "") or "").strip() for item in rows if _row_value(item, "chunk_id", "")]
    paragraphs: list[str] = []
    metadata: dict = {}
    question_types: list[str] = []
    source_quality = "builtin"
    ai_generated = False

    for item in rows:
        text = str(_row_value(item, "text", "") or "").strip()
        if text and (not paragraphs or paragraphs[-1] != text):
            paragraphs.append(text)
        metadata.update(_json_object(_row_value(item, "metadata_json", "{}") or "{}"))
        for qtype in _json_list(_row_value(item, "question_types_json", "[]") or "[]"):
            qtype = str(qtype or "").strip()
            if qtype and qtype not in question_types:
                question_types.append(qtype)
        item_quality = str(_row_value(item, "source_quality", "") or "").strip()
        if item_quality:
            source_quality = item_quality
        if item_quality == "ai_generated" or _json_object(_row_value(item, "metadata_json", "{}") or "{}").get("ai_generated"):
            ai_generated = True

    passage_text = "\n\n".join(paragraphs).strip()
    if not passage_text:
        return None

    questions = _merge_questions(rows)
    if questions:
        metadata["questions"] = questions
        question_types = _actual_question_types(questions)

    word_count = len(passage_text.split())
    estimated_candidates = [_safe_int(_row_value(item, "estimated_time", 0), 0) for item in rows]
    difficulty_candidates = [_safe_int(_row_value(item, "difficulty_score", 0), 0) for item in rows]
    topic = _preferred_value([_row_value(item, "topic", "") for item in rows], default="")
    subject = _preferred_value(
        [_row_value(item, "subject_category", "") for item in rows],
        default=topic or "general",
        skip_general=True,
    )

    return PassageRecord(
        chunk_id=chunk_ids[0] if chunk_ids else str(_row_value(row, "chunk_id", "") or ""),
        chunk_ids=chunk_ids,
        source_file=str(_row_value(rows[0], "source_file", "") or ""),
        passage_text=passage_text,
        difficulty=_preferred_value([_row_value(item, "difficulty", "") for item in rows], default="B2"),
        topic=topic,
        subject=subject,
        exam=_preferred_value([_row_value(item, "exam", "") for item in rows], default="general"),
        metadata=metadata,
        questions=questions,
        question_types=question_types,
        word_count=word_count,
        estimated_time=max(max(estimated_candidates or [0]), max(3, round(word_count / 180))),
        difficulty_score=max(difficulty_candidates or [0]),
        source_quality=source_quality,
        ai_generated=ai_generated,
        mock_exam_ready=bool(metadata.get("mock_exam_ready")),
    )


def _seen_passage_keys(kb, seen_chunk_ids: Optional[list[str]]) -> set[str]:
    if not seen_chunk_ids:
        return set()

    ids = [str(chunk_id).strip() for chunk_id in seen_chunk_ids if str(chunk_id).strip()]
    if not ids:
        return set()

    placeholders = ",".join("?" * len(ids))
    rows = kb._sql.execute(
        f"""SELECT chunk_id, source_file
            FROM chunks
            WHERE content_type = 'reading' AND chunk_id IN ({placeholders})""",
        ids,
    ).fetchall()

    keys = {_passage_group_key(row) for row in rows}
    found = {str(_row_value(row, "chunk_id", "") or "").strip() for row in rows}
    for chunk_id in ids:
        if chunk_id not in found:
            keys.add(f"chunk:{chunk_id}")
    return keys


def _coalesce_passages(kb, rows: list, seen_chunk_ids: Optional[list[str]] = None, limit: Optional[int] = None) -> list[PassageRecord]:
    passages: list[PassageRecord] = []
    used: set[str] = set()
    seen_keys = _seen_passage_keys(kb, seen_chunk_ids)

    for row in rows:
        group_key = _passage_group_key(row)
        if group_key in used or group_key in seen_keys:
            continue
        passage = _build_passage_record(kb, row)
        if passage is None:
            continue
        passages.append(passage)
        used.add(group_key)
        if limit and len(passages) >= limit:
            break
    return passages


def _cache_passage_questions(kb, passage: PassageRecord, questions: list[dict]) -> None:
    if not passage.chunk_id or not questions:
        return
    metadata = dict(passage.metadata or {})
    metadata["questions"] = questions
    question_types = _actual_question_types(questions)
    kb._sql.execute(
        "UPDATE chunks SET metadata_json = ?, question_types_json = ? WHERE chunk_id = ?",
        (
            json.dumps(metadata, ensure_ascii=False),
            json.dumps(question_types, ensure_ascii=True),
            passage.chunk_id,
        ),
    )
    kb._sql.commit()
    passage.metadata = metadata
    passage.questions = questions
    passage.question_types = question_types


def _mark_passage_seen(user_model, user_id: str, passage: PassageRecord) -> None:
    seen_ids = passage.chunk_ids or ([passage.chunk_id] if passage.chunk_id else [])
    if seen_ids:
        user_model.mark_seen(user_id, seen_ids)


def _load_generation_passage_text(kb, supplied_passage: Optional[str], exam: str, cefr: str, not_found_message: str) -> str:
    if supplied_passage:
        return supplied_passage
    rows = kb.get_by_type(
        content_type="reading",
        difficulty=cefr,
        exam=exam,
        limit=18,
        random_order=True,
    )
    passages = _coalesce_passages(kb, rows, limit=4)
    if not passages:
        raise HTTPException(404, not_found_message)
    return max(passages, key=lambda item: (item.word_count, len(item.questions))).passage_text


READING_FILTER_OPTIONS = {
    "toefl": [
        ("factual", "Factual Information"),
        ("inference", "Inference"),
        ("vocabulary", "Vocabulary"),
        ("negative_factual", "Negative Factual"),
        ("rhetorical_purpose", "Rhetorical Purpose"),
        ("reference", "Reference"),
        ("sentence_simplification", "Sentence Simplification"),
        ("insert_text", "Insert Text"),
        ("prose_summary", "Prose Summary"),
        ("fill_table", "Fill in a Table"),
    ],
    "ielts": [
        ("tfng", "True / False / Not Given"),
        ("matching_headings", "Matching Headings"),
        ("summary_completion", "Summary Completion"),
        ("matching_information", "Matching Information"),
        ("short_answer", "Short Answer"),
        ("diagram_label", "Diagram Label"),
    ],
}


_PASSAGE_MIN_WORDS = {
    "toefl": 650,
    "ielts": 700,
    "gre": 350,
    "cet": 240,
    "general": 180,
}

_CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

_MOCK_READING_TARGETS = {
    "toefl": {"cefr_floor": "B2", "min_words": 650, "question_count": 10},
    "ielts": {"cefr_floor": "B2", "min_words": 700, "question_count": 10},
}


def _min_passage_words(exam: str) -> int:
    return _PASSAGE_MIN_WORDS.get(str(exam or "general").lower(), 180)


def _needs_ai_passage_upgrade(exam: str, word_count: int) -> bool:
    return word_count > 0 and word_count < _min_passage_words(exam)


def _cefr_floor(level: str, floor: str) -> str:
    normalized = str(level or "").upper().strip() or floor
    return normalized if _CEFR_ORDER.get(normalized, 0) >= _CEFR_ORDER.get(floor, 0) else floor


def _mock_target(exam: str) -> dict:
    exam_key = str(exam or "").lower()
    return dict(_MOCK_READING_TARGETS.get(exam_key, {"cefr_floor": "B2", "min_words": _min_passage_words(exam_key), "question_count": 10}))


def _question_target(exam: str, practice_mode: str, requested_question_types: Optional[list[str]] = None) -> int:
    if practice_mode == "mock":
        return int(_mock_target(exam)["question_count"])
    if requested_question_types:
        return max(4, min(10, len(requested_question_types) * 2))
    return 5


def _ensure_question_count(
    questions: list[dict],
    target_count: int,
    passage_text: str,
    exam: str,
    requested_types: Optional[list[str]] = None,
) -> list[dict]:
    output = [dict(item) for item in questions if isinstance(item, dict)]
    if target_count <= 0:
        return output
    if len(output) >= target_count:
        return output[:target_count]
    extras = _offline_fallback_questions(passage_text, requested_types, exam)
    index = 0
    while len(output) < target_count and extras:
        base = dict(extras[index % len(extras)])
        base["id"] = f"{base.get('id', 'offline')}_{len(output)}"
        output.append(base)
        index += 1
    return output


def _cefr_from_difficulty(score: Optional[int], default: str) -> str:
    if score is None:
        return default
    if score <= 3:
        return "B1"
    if score <= 5:
        return "B2"
    if score <= 7:
        return "C1"
    return "C2"


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", str(text or "").replace("\n", " ")) if s.strip()]
    return [s for s in sentences if len(s.split()) >= 4] or ([str(text or "").strip()] if text else [])


def _short_answer(text: str, max_words: int = 10) -> str:
    words = [w for w in str(text or "").replace("\n", " ").split() if w]
    return " ".join(words[:max_words]).strip(" ,;:.") or "Not available"


def _pick_keyword(text: str, offset: int = 0) -> str:
    stopwords = {
        "about", "after", "before", "because", "between", "during", "their", "there",
        "these", "those", "which", "while", "where", "being", "under", "through",
        "study", "could", "would", "should", "other", "people", "often", "using",
    }
    words = []
    seen = set()
    for token in re.findall(r"[A-Za-z][A-Za-z-]{4,}", str(text or "")):
        lower = token.lower()
        if lower in stopwords or lower in seen:
            continue
        seen.add(lower)
        words.append(token)
    if not words:
        return "the passage"
    return words[min(offset, len(words) - 1)]


def _offline_fallback_questions(passage_text: str, requested_types: Optional[list[str]], exam: str) -> list[dict]:
    sentences = _split_sentences(passage_text)
    first = sentences[0] if sentences else ""
    middle = sentences[len(sentences) // 2] if sentences else first
    last = sentences[-1] if sentences else first
    longest = max(sentences, key=len) if sentences else first
    types = requested_types or [item[0] for item in READING_FILTER_OPTIONS.get(exam, [])[:4]]
    questions = []

    for index, qtype in enumerate(types[:5]):
        keyword = _pick_keyword(passage_text, index)
        if qtype in {"factual", "matching_information", "short_answer"}:
            answer = _short_answer(first)
            prompt = f"根据文章，关于“{keyword}”提到的关键信息是什么？"
        elif qtype in {"inference", "negative_factual", "rhetorical_purpose", "matching_headings", "tfng"}:
            answer = _short_answer(middle)
            prompt = f"结合上下文，文章中“{keyword}”对应的核心意思是什么？"
        elif qtype in {"vocabulary", "reference", "sentence_simplification", "insert_text"}:
            answer = _short_answer(longest)
            prompt = f"请解释文中与“{keyword}”相关的句子主要表达了什么。"
        else:
            answer = _short_answer(last)
            prompt = f"请概括文章后半部分与“{keyword}”相关的核心信息。"

        questions.append({
            "id": f"offline_{qtype}_{index}",
            "type": qtype,
            "question": prompt,
            "answer": answer,
            "explanation": "离线 fallback 题：当前使用本地通用理解题保证训练不中断。",
        })

    return questions


def _actual_question_types(questions: list[dict]) -> list[str]:
    return sorted({q.get("type") for q in questions if isinstance(q, dict) and q.get("type")})


def _build_session_payload(
    sid: str,
    passage_text: str,
    questions: list[dict],
    difficulty: str,
    topic: str = "",
    subject: Optional[str] = None,
    exam: Optional[str] = None,
    ai_generated: bool = False,
    fallback_reason: Optional[str] = None,
    requested_question_types: Optional[list[str]] = None,
) -> dict:
    payload = {
        "session_id": sid,
        "passage": passage_text,
        "word_count": len(passage_text.split()),
        "difficulty": difficulty,
        "topic": topic,
        "question_count": len(questions),
        "has_questions": len(questions) > 0,
        "ai_generated": ai_generated,
        "question_types": _actual_question_types(questions),
    }
    if subject:
        payload["subject"] = subject
    if exam:
        payload["exam"] = exam
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    if requested_question_types:
        payload["requested_question_types"] = requested_question_types
    return payload


# ── TOEFL 2026 New Question Types ─────────────────────────────────────────────

class CompleteWordsRequest(BaseModel):
    passage: Optional[str] = None
    cefr_level: Optional[str] = None


class DailyLifeRequest(BaseModel):
    text_type: str = "email"  # email, notice, menu, schedule, advertisement
    cefr_level: Optional[str] = None


@router.post("/toefl2026/complete-words")
def generate_complete_words(req: CompleteWordsRequest):
    """Generate TOEFL 2026 'Complete the Words' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_complete_words_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl2026/daily-life")
def generate_daily_life(req: DailyLifeRequest):
    """Generate TOEFL 2026 'Read in Daily Life' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    try:
        result = ai.generate_daily_life_question(cefr, req.text_type)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


# ── Additional TOEFL Reading Question Types ──────────────────────────────────

class TOEFLReadingRequest(BaseModel):
    passage: Optional[str] = None
    cefr_level: Optional[str] = None


@router.post("/toefl/negative-factual")
def generate_negative_factual(req: TOEFLReadingRequest):
    """Generate TOEFL 'Negative Factual Information' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_negative_factual_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl/rhetorical-purpose")
def generate_rhetorical_purpose(req: TOEFLReadingRequest):
    """Generate TOEFL 'Rhetorical Purpose' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_rhetorical_purpose_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl/reference")
def generate_reference(req: TOEFLReadingRequest):
    """Generate TOEFL 'Reference' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_reference_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl/sentence-simplification")
def generate_sentence_simplification(req: TOEFLReadingRequest):
    """Generate TOEFL 'Sentence Simplification' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_sentence_simplification_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl/insert-text")
def generate_insert_text(req: TOEFLReadingRequest):
    """Generate TOEFL 'Insert Text' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_insert_text_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl/prose-summary")
def generate_prose_summary(req: TOEFLReadingRequest):
    """Generate TOEFL 'Prose Summary' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_prose_summary_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl/fill-table")
def generate_fill_table(req: TOEFLReadingRequest):
    """Generate TOEFL 'Fill in a Table' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "toefl", cefr, "No passages found")

    try:
        result = ai.generate_fill_table_question(passage, cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")

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
        from gui.deps import load_config, _CONFIG_PATH
        import sys
        cfg = load_config()
        raw = cfg.get("data_dir", "data")
        data_dir = Path(raw) if Path(raw).is_absolute() else _CONFIG_PATH.parent / raw
        # Only create directory if it doesn't exist (user may have set custom path)
        if not data_dir.exists():
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
                    exam=exam, exclude_ids=seen, limit=24, random_order=True
                )
                passages = _coalesce_passages(kb, rows, seen_chunk_ids=seen, limit=3)
                if passages:
                    passage = passages[0]
                    if _needs_ai_passage_upgrade(exam, passage.word_count):
                        gen = ai.generate_reading_passage(
                            cefr_level=passage.difficulty or diff,
                            exam=exam,
                            topic=passage.topic,
                        )
                        questions = ai.generate_comprehension_questions(
                            passage=gen["passage"], cefr_level=gen["difficulty"],
                            num_questions=5, exam=exam
                        ) or []
                        data = {"passage": gen["passage"],
                                "chunk_id": f"ai_{uuid.uuid4().hex[:8]}",
                                "questions": questions, "difficulty": gen["difficulty"],
                                "topic": gen.get("topic", passage.topic),
                                "subject": passage.subject,
                                "word_count": gen["word_count"], "ai_generated": True}
                    else:
                        passage_text = passage.passage_text
                        chunk_id = passage.chunk_id
                        questions = list(passage.questions)
                        if not questions:
                            questions = ai.generate_comprehension_questions(
                                passage=passage_text, cefr_level=diff,
                                num_questions=5, exam=exam
                            ) or []
                        if questions:
                            _cache_passage_questions(kb, passage, questions)
                        data = {"passage": passage_text, "chunk_id": chunk_id,
                                "chunk_ids": passage.chunk_ids,
                                "questions": questions, "difficulty": diff,
                                "topic": passage.topic,
                                "subject": passage.subject,
                                "word_count": passage.word_count,
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
    exam: str = ""
    topic: str = ""
    requested_question_types: list[str] = field(default_factory=list)
    answered: int = 0
    correct: int = 0
    completed: bool = False
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
        questions = pooled["questions"] or _offline_fallback_questions(passage_text, None, target_exam)
        chunk_id     = pooled["chunk_id"]
        fallback_reason = None if pooled["questions"] else "当前题目来自离线 fallback，避免无题可做。"
        if not pooled.get("ai_generated"):
            user_model.mark_seen(profile.user_id, pooled.get("chunk_ids") or [chunk_id])
        sid = uuid.uuid4().hex[:12]
        db_sid = user_model.start_session(profile.user_id, "reading")
        _sessions[sid] = ReadingSession(
            session_id=sid, user_id=profile.user_id,
            db_session_id=db_sid, passage=passage_text,
            chunk_id=chunk_id, questions=questions,
            exam=target_exam, topic=pooled.get("topic", ""),
        )
        _schedule_replenish(target_exam, cefr)
        payload = _build_session_payload(
            sid=sid,
            passage_text=passage_text,
            questions=questions,
            difficulty=pooled.get("difficulty", cefr),
            topic=pooled.get("topic", ""),
            subject=pooled.get("subject"),
            exam=target_exam,
            ai_generated=pooled.get("ai_generated", False),
            fallback_reason=fallback_reason,
        )
        payload["word_count"] = pooled.get("word_count", len(passage_text.split()))
        return payload

    # Pool empty — fall through to on-demand generation
    seen = user_model.get_seen_ids(profile.user_id)

    rows = kb.get_by_type(
        content_type="reading",
        difficulty=profile.cefr_level,
        exam=target_exam,
        exclude_ids=seen,
        limit=24,
        random_order=True,
    )
    passages = _coalesce_passages(kb, rows, seen_chunk_ids=seen, limit=4)
    if not passages:
        rows = kb.get_by_type(content_type="reading", difficulty=profile.cefr_level, limit=24, random_order=True)
        passages = _coalesce_passages(kb, rows, limit=4)
    if not passages:
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
        fallback_reason = None
        if not questions:
            questions = _offline_fallback_questions(passage_text, None, target_exam)
            fallback_reason = "AI 未返回题目，已回退为离线 comprehension 题。"

        # Save AI-generated passage to KB warehouse for future reuse
        try:
            from core.ingestion.pipeline import Chunk, ContentType
            import json as _json
            chunk = Chunk(
                chunk_id=chunk_id,
                source_file=f"ai_warehouse/{chunk_id}.md",
                content_type=ContentType.READING,
                difficulty=gen["difficulty"],
                topic=gen["topic"],
                exam=target_exam,
                language="en",
                text=passage_text,
                metadata={"questions": questions, "ai_generated": True},
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
            exam=target_exam,
            topic=gen["topic"],
        )
        _schedule_replenish(target_exam, cefr)
        payload = _build_session_payload(
            sid=sid,
            passage_text=passage_text,
            questions=questions,
            difficulty=gen["difficulty"],
            topic=gen["topic"],
            subject=gen.get("subject"),
            exam=target_exam,
            ai_generated=True,
            fallback_reason=fallback_reason,
        )
        payload["word_count"] = gen["word_count"]
        return payload

    passage = passages[0]
    fallback_reason = None
    ai_generated = False

    if ai and _needs_ai_passage_upgrade(target_exam, passage.word_count):
        _mark_passage_seen(user_model, profile.user_id, passage)
        try:
            gen = ai.generate_reading_passage(
                cefr_level=passage.difficulty or profile.cefr_level,
                exam=target_exam,
                topic=passage.topic,
            )
            passage_text = gen["passage"]
            chunk_id = f"ai_quality_{uuid.uuid4().hex[:8]}"
            questions = ai.generate_comprehension_questions(
                passage=passage_text,
                cefr_level=gen["difficulty"],
                num_questions=5,
                exam=target_exam,
            ) or []
            ai_generated = True
            fallback_reason = "内置素材篇幅偏短，已自动升级为 AI 长篇文章。"
            if not questions:
                questions = _offline_fallback_questions(passage_text, None, target_exam)
                fallback_reason += " AI 未返回题目，已回退为离线 comprehension 题。"
        except Exception:
            ai_generated = False
            fallback_reason = None

    if not ai_generated:
        passage_text = passage.passage_text
        chunk_id = passage.chunk_id
        _mark_passage_seen(user_model, profile.user_id, passage)

        # Try to reuse cached questions from KB metadata first
        questions = list(passage.questions)

        # Generate questions with AI if not cached
        if not questions and ai:
            try:
                questions = ai.generate_comprehension_questions(
                    passage=passage_text,
                    cefr_level=passage.difficulty or profile.cefr_level,
                    num_questions=5,
                    exam=target_exam,
                ) or []
                if questions:
                    _cache_passage_questions(kb, passage, questions)
            except Exception:
                questions = []
        if not questions:
            questions = _offline_fallback_questions(passage_text, None, target_exam)
            fallback_reason = "当前题目来自离线 fallback，避免无题可做。"

    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "reading")
    _sessions[sid] = ReadingSession(
        session_id=sid,
        user_id=profile.user_id,
        db_session_id=db_sid,
        passage=passage_text,
        chunk_id=chunk_id,
        questions=questions,
        exam=target_exam,
        topic=gen.get("topic", passage.topic) if ai_generated else passage.topic,
    )

    _schedule_replenish(target_exam, cefr)
    payload = _build_session_payload(
        sid=sid,
        passage_text=passage_text,
        questions=questions,
        difficulty=gen["difficulty"] if ai_generated else passage.difficulty,
        topic=gen.get("topic", passage.topic) if ai_generated else passage.topic,
        subject=passage.subject,
        exam=target_exam,
        ai_generated=ai_generated,
        fallback_reason=fallback_reason,
    )
    payload["word_count"] = len(passage_text.split()) if ai_generated else passage.word_count
    return payload


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
    if last and not sess.completed:
        kb, srs, user_model, ai, profile = get_components()
        duration = int(time.time() - sess.start_time)
        accuracy = sess.correct / max(sess.answered, 1)
        actual_question_types = _actual_question_types(sess.questions)
        recap = build_reading_recap(
            topic=sess.topic,
            correct=sess.correct,
            answered=sess.answered,
            requested_question_types=sess.requested_question_types,
            actual_question_types=actual_question_types,
        )
        user_model.record_answer(sess.user_id, "reading_comprehension", accuracy >= 0.67)
        user_model.end_session(
            sess.db_session_id,
            duration,
            sess.answered,
            accuracy,
            content_json=json.dumps(
                {
                    "exam": sess.exam,
                    "topic": sess.topic,
                    "chunk_id": sess.chunk_id,
                    "question_types": sess.requested_question_types or actual_question_types,
                    "requested_question_types": sess.requested_question_types,
                    "correct": sess.correct,
                    "answered": sess.answered,
                    "passage_preview": sess.passage[:220],
                    **recap,
                },
                ensure_ascii=False,
            ),
        )
        sess.completed = True

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


# ── IELTS Reading Question Types ─────────────────────────────────────────────

class IELTSReadingRequest(BaseModel):
    passage: Optional[str] = None
    cefr_level: Optional[str] = None


@router.post("/ielts/tfng")
def generate_ielts_tfng(req: IELTSReadingRequest):
    """Generate IELTS 'True/False/Not Given' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "ielts", cefr, "No IELTS passages found")

    try:
        from ai.reading_question_generators import generate_ielts_tfng_question
        result = generate_ielts_tfng_question(passage, cefr, ai)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/ielts/matching-headings")
def generate_ielts_matching_headings(req: IELTSReadingRequest):
    """Generate IELTS 'Matching Headings' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "ielts", cefr, "No IELTS passages found")

    try:
        from ai.reading_question_generators import generate_ielts_matching_headings
        result = generate_ielts_matching_headings(passage, cefr, ai)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


class IELTSCompletionRequest(BaseModel):
    passage: Optional[str] = None
    completion_type: str = "summary"  # summary, note, table
    cefr_level: Optional[str] = None


@router.post("/ielts/completion")
def generate_ielts_completion(req: IELTSCompletionRequest):
    """Generate IELTS completion question (Summary/Note/Table)."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "ielts", cefr, "No IELTS passages found")

    try:
        from ai.reading_question_generators import generate_ielts_completion_question
        result = generate_ielts_completion_question(passage, req.completion_type, cefr, ai)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


class IELTSMatchingRequest(BaseModel):
    passage: Optional[str] = None
    matching_type: str = "information"  # information, features, sentence_endings
    cefr_level: Optional[str] = None


@router.post("/ielts/matching")
def generate_ielts_matching(req: IELTSMatchingRequest):
    """Generate IELTS matching question (Information/Features/Sentence Endings)."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "ielts", cefr, "No IELTS passages found")

    try:
        from ai.reading_question_generators import generate_ielts_matching_question
        result = generate_ielts_matching_question(passage, req.matching_type, cefr, ai)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/ielts/short-answer")
def generate_ielts_short_answer(req: IELTSReadingRequest):
    """Generate IELTS 'Short Answer' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "ielts", cefr, "No IELTS passages found")

    try:
        from ai.reading_question_generators import generate_ielts_short_answer
        result = generate_ielts_short_answer(passage, cefr, ai)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/ielts/diagram-label")
def generate_ielts_diagram_label(req: IELTSReadingRequest):
    """Generate IELTS 'Diagram Label' question."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    passage = _load_generation_passage_text(kb, req.passage, "ielts", cefr, "No IELTS passages found")

    try:
        from ai.reading_question_generators import generate_ielts_diagram_label
        result = generate_ielts_diagram_label(passage, cefr, ai)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


# ── Filtered Practice Mode ───────────────────────────────────────────────────

class FilteredPracticeRequest(BaseModel):
    exam: str  # toefl/ielts
    difficulty: Optional[int] = None  # 1-10 scale
    subject: Optional[str] = None
    topic: Optional[str] = None
    question_types: Optional[list[str]] = None
    practice_mode: str = "single"  # single/mock/targeted


class LibraryPassageRequest(BaseModel):
    exam: str
    chunk_id: str
    difficulty: Optional[int] = None
    question_types: Optional[list[str]] = None
    practice_mode: str = "targeted"


@router.post("/start-filtered")
def start_filtered_session(req: FilteredPracticeRequest):
    """Start a reading session with multi-dimensional filtering."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    is_mock = req.practice_mode == "mock"
    cefr = _cefr_from_difficulty(req.difficulty, profile.cefr_level or "B2")
    if is_mock:
        cefr = _cefr_floor(cefr, str(_mock_target(req.exam)["cefr_floor"]))
    target_question_count = _question_target(req.exam, req.practice_mode, req.question_types)
    min_words = int(_mock_target(req.exam)["min_words"]) if is_mock else _min_passage_words(req.exam)

    seen = user_model.get_seen_ids(profile.user_id)
    fallback_notes: list[str] = []

    def _load_type_priority_rows(exclude_seen: bool) -> list:
        if not req.question_types:
            return []
        conditions = [
            "content_type = ?",
            "exam = ?",
            "difficulty = ?",
        ]
        params = ["reading", req.exam, cefr]
        if req.subject:
            conditions.append("subject_category = ?")
            params.append(req.subject)
        if req.topic:
            conditions.append("LOWER(topic) LIKE ?")
            params.append(f"%{req.topic.lower()}%")
        like_parts = []
        for question_type in req.question_types:
            like_parts.append("question_types_json LIKE ?")
            params.append(f'%"{question_type}"%')
        if like_parts:
            conditions.append("(" + " OR ".join(like_parts) + ")")
        if exclude_seen and seen:
            conditions.append(f"chunk_id NOT IN ({','.join('?' * len(seen))})")
            params.extend(seen)
        params.append(24)
        return kb._sql.execute(
            f"""SELECT rowid, *
                FROM chunks
                WHERE {' AND '.join(conditions)}
                ORDER BY RANDOM() LIMIT ?""",
            params,
        ).fetchall()

    def _load_filtered_rows(exclude_seen: bool) -> list:
        if is_mock and not req.subject and not req.topic:
            accepted_difficulties = [level for level, rank in _CEFR_ORDER.items() if rank >= _CEFR_ORDER.get(cefr, 0)]
            conditions = ["content_type = ?", "exam = ?"]
            params = ["reading", req.exam]
            if accepted_difficulties:
                placeholders = ",".join("?" * len(accepted_difficulties))
                conditions.append(f"difficulty IN ({placeholders})")
                params.extend(accepted_difficulties)
            if exclude_seen and seen:
                conditions.append(f"chunk_id NOT IN ({','.join('?' * len(seen))})")
                params.extend(seen)
            params.append(60)
            return kb._sql.execute(
                f"""SELECT rowid, *
                    FROM chunks
                    WHERE {' AND '.join(conditions)}
                    ORDER BY rowid DESC LIMIT ?""",
                params,
            ).fetchall()

        if req.subject or req.topic:
            conditions = [
                "content_type = ?",
                "exam = ?",
                "difficulty = ?",
            ]
            params = ["reading", req.exam, cefr]
            if req.subject:
                conditions.append("subject_category = ?")
                params.append(req.subject)
            if req.topic:
                conditions.append("LOWER(topic) LIKE ?")
                params.append(f"%{req.topic.lower()}%")
            if exclude_seen and seen:
                conditions.append(f"chunk_id NOT IN ({','.join('?' * len(seen))})")
                params.extend(seen)
            params.append(24)
            return kb._sql.execute(
                f"""SELECT rowid, *
                    FROM chunks
                    WHERE {' AND '.join(conditions)}
                    ORDER BY RANDOM() LIMIT ?""",
                params
            ).fetchall()

        query_params = {
            "content_type": "reading",
            "difficulty": cefr,
            "exam": req.exam,
            "limit": 24,
            "random_order": True,
        }
        if exclude_seen:
            query_params["exclude_ids"] = seen
        return kb.get_by_type(**query_params)

    rows = _load_type_priority_rows(exclude_seen=True) or _load_filtered_rows(exclude_seen=True)
    passages = _coalesce_passages(kb, rows, seen_chunk_ids=seen, limit=5)
    if not passages:
        rows = _load_type_priority_rows(exclude_seen=False) or _load_filtered_rows(exclude_seen=False)
        passages = _coalesce_passages(kb, rows, limit=5)
    if not passages and (req.subject or req.topic):
        fallback_notes.append("未找到完全匹配的主题筛选，已放宽到同考试同难度素材。")
        rows = _load_type_priority_rows(exclude_seen=True)
        if not rows:
            query_params = {
                "content_type": "reading",
                "difficulty": cefr,
                "exam": req.exam,
                "limit": 24,
                "random_order": True,
            }
            if seen:
                query_params["exclude_ids"] = seen
            rows = kb.get_by_type(**query_params)
        passages = _coalesce_passages(kb, rows, seen_chunk_ids=seen, limit=5)
        if not passages:
            rows = _load_type_priority_rows(exclude_seen=False)
            if not rows:
                rows = kb.get_by_type(
                    content_type="reading",
                    difficulty=cefr,
                    exam=req.exam,
                    limit=24,
                    random_order=True,
                )
            passages = _coalesce_passages(kb, rows, limit=5)

    if passages and req.question_types:
        requested = set(req.question_types)
        passages.sort(
            key=lambda item: (
                0 if requested & set(item.question_types or []) else 1,
                0 if item.questions else 1,
            )
        )
    elif passages and is_mock:
        passages.sort(
            key=lambda item: (
                0 if item.mock_exam_ready else 1,
                0 if item.word_count >= min_words else 1,
                0 if len(item.questions) >= target_question_count else 1,
                -item.word_count,
                -len(item.questions),
            )
        )

    if not passages:
        # No passages found - try AI generation if available
        if not ai:
            raise HTTPException(404, "No passages found matching filters")

        try:
            # Generate passage with AI
            from ai.question_distribution import generate_questions_with_distribution, TOEFL_STANDARD_DISTRIBUTION, IELTS_STANDARD_DISTRIBUTION

            gen = ai.generate_reading_passage(
                cefr_level=cefr,
                exam=req.exam,
                topic=req.subject or "general",
                min_words=min_words if is_mock else None,
            )
            passage_text = gen["passage"]

            # Generate questions with specified types or use standard distribution
            if req.question_types:
                # Custom distribution based on requested types
                distribution = {qt: 2 for qt in req.question_types}
            else:
                # Use standard distribution
                distribution = TOEFL_STANDARD_DISTRIBUTION if req.exam == "toefl" else IELTS_STANDARD_DISTRIBUTION

            questions = generate_questions_with_distribution(
                passage=passage_text,
                question_types=req.question_types or list(distribution.keys()),
                distribution=distribution,
                difficulty=req.difficulty or 5,
                exam=req.exam,
                cefr_level=cefr,
                ai_client=ai,
            )
            questions = _ensure_question_count(questions, target_question_count, passage_text, req.exam, req.question_types)

            chunk_id = f"ai_filtered_{uuid.uuid4().hex[:8]}"
            passage_subject = req.subject or gen.get("subject") or gen.get("topic", "")
            passage_topic = req.topic or gen.get("topic", "")
            passage_difficulty = gen.get("difficulty", cefr)
            passage_word_count = len(passage_text.split())
            fallback_notes.append("当前素材由 AI 生成，以满足筛选条件。")

        except Exception as e:
            raise HTTPException(500, f"AI generation failed: {e}")
    else:
        # Use passage from KB
        passage = passages[0]
        passage_text = passage.passage_text
        chunk_id = passage.chunk_id
        passage_subject = req.subject or passage.subject
        passage_topic = req.topic or passage.topic
        passage_difficulty = passage.difficulty or cefr
        passage_word_count = passage.word_count
        questions = list(passage.questions)
        upgraded = False

        if ai and (
            _needs_ai_passage_upgrade(req.exam, passage.word_count)
            or (is_mock and len(questions) < target_question_count)
        ):
            try:
                from ai.question_distribution import generate_questions_with_distribution, TOEFL_STANDARD_DISTRIBUTION, IELTS_STANDARD_DISTRIBUTION

                gen = ai.generate_reading_passage(
                    cefr_level=passage.difficulty or cefr,
                    exam=req.exam,
                    topic=req.topic or req.subject or passage.topic,
                    min_words=min_words if is_mock else None,
                )
                passage_text = gen["passage"]
                chunk_id = f"ai_filtered_{uuid.uuid4().hex[:8]}"
                passage_topic = req.topic or gen.get("topic", passage.topic)
                passage_difficulty = gen.get("difficulty", cefr)
                passage_word_count = len(passage_text.split())
                _mark_passage_seen(user_model, profile.user_id, passage)

                if req.question_types:
                    distribution = {qt: 2 for qt in req.question_types}
                else:
                    distribution = TOEFL_STANDARD_DISTRIBUTION if req.exam == "toefl" else IELTS_STANDARD_DISTRIBUTION

                questions = generate_questions_with_distribution(
                    passage=passage_text,
                    question_types=req.question_types or list(distribution.keys()),
                    distribution=distribution,
                    difficulty=req.difficulty or 5,
                    exam=req.exam,
                    cefr_level=cefr,
                    ai_client=ai,
                )
                questions = _ensure_question_count(questions, target_question_count, passage_text, req.exam, req.question_types)
                fallback_notes.append("本地素材不满足模考篇幅或题量要求，已自动升级为 AI 长篇文章。")
                upgraded = True
            except Exception:
                upgraded = False

        if not upgraded:
            # Parse existing questions or generate new ones
            try:
                questions = list(passage.questions)

                # Filter questions by type if specified
                if req.question_types and questions:
                    filtered = [q for q in questions if q.get("type") in req.question_types]
                    if filtered:
                        questions = filtered
                    else:
                        fallback_notes.append("当前素材没有精确匹配题型，已回退为本篇通用题。")
                        questions = questions[: min(len(questions), 5)]

                # If no questions or filtered out all questions, generate new ones
                if (not questions or (is_mock and len(questions) < target_question_count)) and ai:
                    from ai.question_distribution import generate_questions_with_distribution, TOEFL_STANDARD_DISTRIBUTION, IELTS_STANDARD_DISTRIBUTION

                    if req.question_types:
                        distribution = {qt: 2 for qt in req.question_types}
                    else:
                        distribution = TOEFL_STANDARD_DISTRIBUTION if req.exam == "toefl" else IELTS_STANDARD_DISTRIBUTION

                    questions = generate_questions_with_distribution(
                        passage=passage_text,
                        question_types=req.question_types or list(distribution.keys()),
                        distribution=distribution,
                        difficulty=req.difficulty or 5,
                        exam=req.exam,
                        cefr_level=cefr,
                        ai_client=ai,
                    )
                    if questions:
                        _cache_passage_questions(kb, passage, questions)
                if is_mock:
                    questions = _ensure_question_count(questions, target_question_count, passage_text, req.exam, req.question_types)
            except Exception:
                questions = []

            _mark_passage_seen(user_model, profile.user_id, passage)

    if not questions:
        questions = _offline_fallback_questions(passage_text, req.question_types, req.exam)
        fallback_notes.append("当前使用离线 fallback 题，保证训练不中断。")
    elif is_mock:
        questions = _ensure_question_count(questions, target_question_count, passage_text, req.exam, req.question_types)

    # Create session
    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "reading")
    _sessions[sid] = ReadingSession(
        session_id=sid,
        user_id=profile.user_id,
        db_session_id=db_sid,
        passage=passage_text,
        chunk_id=chunk_id,
        questions=questions,
        exam=req.exam,
        topic=passage_topic,
        requested_question_types=req.question_types or [],
    )

    payload = _build_session_payload(
        sid=sid,
        passage_text=passage_text,
        questions=questions,
        difficulty=passage_difficulty,
        topic=passage_topic,
        subject=passage_subject,
        exam=req.exam,
        ai_generated=chunk_id.startswith("ai_filtered_"),
        fallback_reason=" ".join(fallback_notes) if fallback_notes else None,
        requested_question_types=req.question_types,
    )
    payload["word_count"] = passage_word_count
    payload["difficulty_score"] = req.difficulty
    payload["practice_mode"] = req.practice_mode
    return payload


@router.post("/start-from-library")
def start_from_library(req: LibraryPassageRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    row = kb._sql.execute(
        "SELECT rowid, * FROM chunks WHERE content_type = 'reading' AND chunk_id = ? LIMIT 1",
        (req.chunk_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Passage not found")

    passage = _build_passage_record(kb, row)
    if passage is None:
        raise HTTPException(404, "Passage not found")

    cefr = _cefr_from_difficulty(req.difficulty, profile.cefr_level or "B2")
    target_exam = req.exam or passage.exam or profile.target_exam or "general"
    fallback_notes: list[str] = []

    passage_text = passage.passage_text
    passage_topic = passage.topic
    passage_subject = passage.subject
    passage_difficulty = passage.difficulty or cefr
    passage_word_count = passage.word_count
    chunk_id = passage.chunk_id or req.chunk_id
    questions = list(passage.questions)

    if req.question_types and questions:
        filtered = [q for q in questions if q.get("type") in req.question_types]
        if filtered:
            questions = filtered
        else:
            fallback_notes.append("当前素材没有精确匹配题型，已回退为本篇通用题。")
            questions = questions[: min(len(questions), 5)]

    if not questions and ai:
        try:
            from ai.question_distribution import (
                IELTS_STANDARD_DISTRIBUTION,
                TOEFL_STANDARD_DISTRIBUTION,
                generate_questions_with_distribution,
            )

            if req.question_types:
                distribution = {qt: 2 for qt in req.question_types}
            else:
                distribution = TOEFL_STANDARD_DISTRIBUTION if target_exam == "toefl" else IELTS_STANDARD_DISTRIBUTION

            questions = generate_questions_with_distribution(
                passage=passage_text,
                question_types=req.question_types or list(distribution.keys()),
                distribution=distribution,
                difficulty=req.difficulty or 5,
                exam=target_exam,
                cefr_level=cefr,
                ai_client=ai,
            )
            if questions:
                _cache_passage_questions(kb, passage, questions)
        except Exception:
            questions = []

    _mark_passage_seen(user_model, profile.user_id, passage)

    if not questions:
        questions = _offline_fallback_questions(passage_text, req.question_types, target_exam)
        fallback_notes.append("当前使用离线 fallback 题，保证训练不中断。")

    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "reading")
    _sessions[sid] = ReadingSession(
        session_id=sid,
        user_id=profile.user_id,
        db_session_id=db_sid,
        passage=passage_text,
        chunk_id=chunk_id,
        questions=questions,
        exam=target_exam,
        topic=passage_topic,
        requested_question_types=req.question_types or [],
    )

    payload = _build_session_payload(
        sid=sid,
        passage_text=passage_text,
        questions=questions,
        difficulty=passage_difficulty,
        topic=passage_topic,
        subject=passage_subject,
        exam=target_exam,
        ai_generated=chunk_id.startswith("ai_"),
        fallback_reason=" ".join(fallback_notes) if fallback_notes else None,
        requested_question_types=req.question_types,
    )
    payload["word_count"] = passage_word_count
    payload["difficulty_score"] = req.difficulty
    payload["practice_mode"] = req.practice_mode
    return payload


@router.get("/passages/library")
def get_passage_library(
    exam: str,
    difficulty_min: int = 1,
    difficulty_max: int = 10,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Browse reading passage library with filters."""
    kb, srs, user_model, ai, profile = get_components()

    # Build query
    conditions = ["content_type = 'reading'", "exam = ?"]
    params = [exam]

    # Map difficulty scores to CEFR for filtering
    cefr_levels = []
    if difficulty_min <= 3:
        cefr_levels.append("B1")
    if difficulty_min <= 5 and difficulty_max >= 3:
        cefr_levels.append("B2")
    if difficulty_min <= 7 and difficulty_max >= 5:
        cefr_levels.append("C1")
    if difficulty_max >= 7:
        cefr_levels.append("C2")

    if cefr_levels:
        placeholders = ','.join('?' * len(cefr_levels))
        conditions.append(f"difficulty IN ({placeholders})")
        params.extend(cefr_levels)

    if subject:
        conditions.append("subject_category = ?")
        params.append(subject)
    if topic:
        conditions.append("LOWER(topic) LIKE ?")
        params.append(f"%{topic.lower()}%")

    query = f"""
        SELECT rowid, *
        FROM chunks
        WHERE {' AND '.join(conditions)}
        ORDER BY difficulty_score, topic, rowid
    """

    rows = kb._sql.execute(query, params).fetchall()
    all_passages = _coalesce_passages(kb, rows)
    visible_passages = all_passages[offset : offset + limit]

    passages = []
    for passage in visible_passages:
        preview = passage.passage_text.replace("\r", " ").replace("\n", " ").strip()
        if len(preview) > 200:
            preview = preview[:200].rstrip() + "..."
        passages.append({
            "chunk_id": passage.chunk_id,
            "difficulty": passage.difficulty,
            "difficulty_score": passage.difficulty_score,
            "topic": passage.topic,
            "subject": passage.subject,
            "word_count": passage.word_count,
            "estimated_time": passage.estimated_time,
            "question_types": passage.question_types,
            "source_quality": passage.source_quality,
            "preview": preview,
        })

    return {
        "passages": passages,
        "total": len(all_passages),
        "limit": limit,
        "offset": offset,
        "filters": {
            "exam": exam,
            "difficulty_range": [difficulty_min, difficulty_max],
            "subject": subject,
            "topic": topic,
        }
    }


@router.get("/filters/meta")
def get_filter_meta(exam: str):
    kb, srs, user_model, ai, profile = get_components()

    rows = kb._sql.execute(
        """SELECT chunk_id, source_file, topic, subject_category
           FROM chunks
           WHERE content_type = 'reading' AND exam = ?""",
        (exam,),
    ).fetchall()

    topic_counts: dict[str, int] = {}
    subject_counts: dict[str, int] = {}
    seen_keys: set[str] = set()
    for row in rows:
        group_key = _passage_group_key(row)
        if group_key in seen_keys:
            continue
        seen_keys.add(group_key)

        topic = str(_row_value(row, "topic", "") or "").strip()
        subject = str(_row_value(row, "subject_category", "") or "").strip()
        if topic:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        if subject:
            subject_counts[subject] = subject_counts.get(subject, 0) + 1

    topic_rows = [
        {"value": key, "count": value}
        for key, value in sorted(topic_counts.items(), key=lambda item: (-item[1], item[0]))[:24]
    ]
    subject_rows = [
        {"value": key, "count": value}
        for key, value in sorted(subject_counts.items(), key=lambda item: (-item[1], item[0]))[:24]
    ]

    return {
        "exam": exam,
        "question_types": [
            {"id": key, "label": label}
            for key, label in READING_FILTER_OPTIONS.get(exam, [])
        ],
        "topics": topic_rows,
        "subjects": subject_rows,
        "difficulty_bands": [
            {"id": "easy", "label": "Easy", "min": 1, "max": 3, "score": 3},
            {"id": "balanced", "label": "Balanced", "min": 4, "max": 6, "score": 5},
            {"id": "hard", "label": "Hard", "min": 7, "max": 10, "score": 8},
        ],
    }
