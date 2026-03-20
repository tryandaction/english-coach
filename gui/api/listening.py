"""Listening comprehension API — with pre-generation pool for instant start."""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sqlite3
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.coach.recap import build_listening_recap
from gui.deps import get_components, get_content_dir

router = APIRouter(prefix="/api/listening", tags=["listening"])

_sessions: dict[str, dict] = {}
_MAX_PLAYS = 3
_VOICE_A    = "en-US-AriaNeural"
_VOICE_B    = "en-US-GuyNeural"
_VOICE_MONO = "en-GB-SoniaNeural"

_CONTENT_DIR = get_content_dir() / "listening"

_QUESTION_TYPE_LABELS = {
    "detail": "Detail",
    "inference": "Inference",
    "organization": "Organization",
    "attitude": "Attitude",
    "multiple_choice": "Multiple Choice",
    "form_completion": "Form Completion",
    "matching": "Matching",
    "gist_content": "Gist Content",
    "gist_purpose": "Gist Purpose",
    "function": "Function",
    "connecting": "Connecting Content",
}


def _normalize_question_type(value: Optional[str]) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "mc": "multiple_choice",
        "multiplechoice": "multiple_choice",
        "fill": "form_completion",
        "form": "form_completion",
        "note_completion": "form_completion",
        "organization_of_information": "organization",
    }
    return aliases.get(text, text)


def _parse_question_types(value) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = re.split(r"[,\|]", str(value or ""))
    items: list[str] = []
    for raw in raw_items:
        normalized = _normalize_question_type(raw)
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def _question_type_label(value: Optional[str]) -> str:
    normalized = _normalize_question_type(value)
    return _QUESTION_TYPE_LABELS.get(normalized, normalized.replace("_", " ").title())


def _extract_question_types(data: Optional[dict]) -> list[str]:
    if not isinstance(data, dict):
        return []
    explicit = _parse_question_types(data.get("question_types"))
    if explicit:
        return explicit
    derived: list[str] = []
    for question in data.get("questions", []) or []:
        qtype = _normalize_question_type(question.get("type"))
        if qtype and qtype not in derived:
            derived.append(qtype)
    return derived


def _question_type_matches(data: Optional[dict], question_type: Optional[str]) -> bool:
    normalized = _normalize_question_type(question_type)
    if not normalized:
        return True
    return normalized in _extract_question_types(data)


def _parse_builtin_file(path: Path) -> Optional[tuple[dict, str]]:
    try:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except Exception:
        return None
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm_match:
        return None
    meta: dict[str, object] = {}
    for line in fm_match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        meta[key] = _parse_question_types(value) if key == "question_types" else value
    return meta, text[fm_match.end():]


# ── TOEFL Listening Question Type Endpoints ──────────────────────────────────

class TOEFLListeningRequest(BaseModel):
    question_types: list[str]  # e.g., ["gist_content", "detail", "function"]
    dialogue_type: str = "conversation"  # "conversation" or "monologue"
    cefr_level: Optional[str] = None


@router.post("/toefl/generate-by-type")
def generate_toefl_listening_by_type(req: TOEFLListeningRequest):
    """
    Generate TOEFL listening exercise with specific question types.
    Supports all 8 TOEFL listening question types:
    - gist_content, gist_purpose, detail, function, attitude, organization, connecting, inference
    """
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    # Validate question types
    valid_types = {"gist_content", "gist_purpose", "detail", "function", "attitude", "organization", "connecting", "inference"}
    invalid = set(req.question_types) - valid_types
    if invalid:
        raise HTTPException(400, f"Invalid question types: {invalid}")

    try:
        result = ai.generate_listening_dialogue(
            cefr_level=cefr,
            exam="toefl",
            dialogue_type=req.dialogue_type,
            question_types=req.question_types,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


# ── Pool database ─────────────────────────────────────────────────────────────
# Pool lives in a SQLite file next to the app data directory.
# Each row is a fully-synthesised session ready to hand to the user.

_pool_db: Optional[sqlite3.Connection] = None
_pool_lock = threading.Lock()
_POOL_MIN   = 3   # start replenishing when below this
_POOL_TARGET = 6  # fill up to this many per (exam, type) combo
_replenish_task: Optional[asyncio.Task] = None


def _recent_listening_topics(user_model, user_id: str, exam: str, dialogue_type: str, days: int = 7) -> set[str]:
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = user_model._db.execute(
        """SELECT content_json
           FROM sessions
           WHERE user_id=? AND mode='listening' AND ended_at IS NOT NULL AND ended_at>=?
           ORDER BY ended_at DESC
           LIMIT 20""",
        (user_id, cutoff),
    ).fetchall()
    topics: set[str] = set()
    for row in rows:
        try:
            payload = json.loads(row["content_json"] or "{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("exam", "")).lower() != str(exam).lower():
            continue
        if str(payload.get("dialogue_type", "")).lower() != str(dialogue_type).lower():
            continue
        topic = str(payload.get("topic", "")).strip().lower()
        if topic:
            topics.add(topic)
    return topics


def _get_pool_db() -> sqlite3.Connection:
    global _pool_db
    if _pool_db is not None:
        return _pool_db
    try:
        from gui.deps import load_config, _CONFIG_PATH
        cfg = load_config()
        raw = cfg.get("data_dir", "data")
        from pathlib import Path as _P
        data_dir = _P(raw) if _P(raw).is_absolute() else _CONFIG_PATH.parent / raw
        # Only create directory if it doesn't exist (user may have set custom path)
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)
        db_path = data_dir / "listening_pool.db"
    except Exception:
        db_path = Path(tempfile.gettempdir()) / "listening_pool.db"

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pool (
            id          TEXT PRIMARY KEY,
            exam        TEXT NOT NULL,
            dtype       TEXT NOT NULL,
            difficulty  TEXT NOT NULL,
            topic       TEXT,
            source      TEXT,
            data_json   TEXT NOT NULL,
            audio_path  TEXT,
            timestamps_json TEXT,
            created_at  REAL DEFAULT (unixepoch())
        )
    """)
    conn.commit()
    _pool_db = conn
    return conn


def _pool_count(exam: str, dtype: str, question_type: Optional[str] = None) -> int:
    try:
        conn = _get_pool_db()
        with _pool_lock:
            rows = conn.execute(
                "SELECT data_json FROM pool WHERE exam=? AND dtype=?",
                (exam, dtype)
            ).fetchall()
        if not question_type:
            return len(rows)
        normalized = _normalize_question_type(question_type)
        count = 0
        for row in rows:
            try:
                data = json.loads(row[0] or "{}")
            except Exception:
                data = {}
            if _question_type_matches(data, normalized):
                count += 1
        return count
    except Exception:
        return 0


def _pool_pop(
    exam: str,
    dtype: str,
    difficulty: str,
    exclude_topics: Optional[set[str]] = None,
    question_type: Optional[str] = None,
) -> Optional[dict]:
    """Pop the best matching item from the pool.

    Priority: requested question type -> fresh topic -> exact difficulty.
    """
    try:
        conn = _get_pool_db()
        exclude_topics = {str(item).strip().lower() for item in (exclude_topics or set()) if str(item).strip()}
        requested_qtype = _normalize_question_type(question_type)
        with _pool_lock:
            rows = conn.execute(
                "SELECT id, data_json, audio_path, timestamps_json, topic, difficulty "
                "FROM pool WHERE exam=? AND dtype=? ORDER BY RANDOM()",
                (exam, dtype),
            ).fetchall()
            best_row = None
            best_score = None
            for row in rows:
                row_topic = str(row[4] or "").strip().lower()
                row_difficulty = str(row[5] or "").strip()
                try:
                    data = json.loads(row[1] or "{}")
                except Exception:
                    data = {}
                score = (
                    0 if _question_type_matches(data, requested_qtype) else 1,
                    0 if row_topic not in exclude_topics else 1,
                    0 if row_difficulty == difficulty else 1,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best_row = row
                    if score == (0, 0, 0):
                        break
            if not best_row:
                return None
            pid, data_json, audio_path, ts_json = best_row[:4]
            conn.execute("DELETE FROM pool WHERE id=?", (pid,))
            conn.commit()
        data = json.loads(data_json)
        if "question_types" not in data:
            data["question_types"] = _extract_question_types(data)
        timestamps = json.loads(ts_json) if ts_json else []
        # Verify audio still exists
        if audio_path and not Path(audio_path).exists():
            audio_path = None
            timestamps = []
        return {"data": data, "audio_path": audio_path, "timestamps": timestamps}
    except Exception:
        return None


def _pool_push(exam: str, dtype: str, difficulty: str, data: dict,
               audio_path: Optional[str], timestamps: list) -> None:
    try:
        conn = _get_pool_db()
        with _pool_lock:
            conn.execute(
                "INSERT INTO pool (id, exam, dtype, difficulty, topic, source, data_json, audio_path, timestamps_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), exam, dtype, difficulty,
                 data.get("topic", ""), data.get("source", "builtin"),
                 json.dumps(data), audio_path, json.dumps(timestamps))
            )
            conn.commit()
    except Exception:
        pass


# ── Built-in script loader ────────────────────────────────────────────────────

def _load_builtin_script(
    exam: str,
    dialogue_type: str,
    cefr: str,
    exclude_topics: Optional[set[str]] = None,
    question_type: Optional[str] = None,
) -> Optional[dict]:
    if not _CONTENT_DIR.exists():
        return None
    candidates = []
    exclude_topics = {str(item).strip().lower() for item in (exclude_topics or set()) if str(item).strip()}
    requested_qtype = _normalize_question_type(question_type)

    def _matches(meta: dict[str, object], *, strict_exam: bool, strict_topic: bool) -> bool:
        file_exam = str(meta.get("exam", "general") or "general")
        file_type = str(meta.get("dialogue_type", "conversation") or "conversation")
        file_diff = str(meta.get("difficulty", "B1") or "B1")
        meta_question_types = _parse_question_types(meta.get("question_types"))
        exam_match = (exam == "general" or file_exam == exam or file_exam == "general")
        type_match = (file_type == dialogue_type)
        cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        try:
            diff_match = abs(cefr_levels.index(cefr) - cefr_levels.index(file_diff)) <= 1
        except ValueError:
            diff_match = True
        topic = str(meta.get("topic", "")).strip().lower()
        if strict_exam and not (exam_match and diff_match):
            return False
        if not type_match:
            return False
        if strict_topic and topic in exclude_topics:
            return False
        if requested_qtype and requested_qtype not in meta_question_types:
            return False
        return True

    for f in _CONTENT_DIR.glob("*.md"):
        try:
            parsed = _parse_builtin_file(f)
            if not parsed:
                continue
            meta, body = parsed
            if _matches(meta, strict_exam=True, strict_topic=True):
                candidates.append((f, meta, body))
        except Exception:
            continue

    if not candidates:
        for f in _CONTENT_DIR.glob("*.md"):
            try:
                parsed = _parse_builtin_file(f)
                if not parsed:
                    continue
                meta, body = parsed
                if _matches(meta, strict_exam=False, strict_topic=True):
                    candidates.append((f, meta, body))
            except Exception:
                continue

    if not candidates:
        for f in _CONTENT_DIR.glob("*.md"):
            try:
                parsed = _parse_builtin_file(f)
                if not parsed:
                    continue
                meta, body = parsed
                if _matches(meta, strict_exam=False, strict_topic=False):
                    candidates.append((f, meta, body))
            except Exception:
                continue

    if not candidates:
        return None

    f, meta, body = random.choice(candidates)
    questions = []
    marker = re.search(r"\nquestions:\s*\n", body)
    if marker:
        script_text = body[:marker.start()].strip()
        questions_text = body[marker.end():].strip()
        try:
            parsed_questions = json.loads(questions_text)
            questions = parsed_questions if isinstance(parsed_questions, list) else []
        except Exception:
            questions = []
    else:
        script_text = body.strip()

    script = []
    for line in script_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([AB]):\s*(.+)$", line)
        if m:
            script.append({"speaker": m.group(1), "text": m.group(2).strip()})

    if not script or not questions:
        return None

    question_types = _parse_question_types(meta.get("question_types"))
    if not question_types:
        question_types = _extract_question_types({"questions": questions})

    return {
        "type": meta.get("dialogue_type", dialogue_type),
        "topic": meta.get("topic", ""),
        "difficulty": meta.get("difficulty", cefr),
        "script": script,
        "questions": questions,
        "question_types": question_types,
        "source": "builtin",
    }


# ── Audio synthesis ───────────────────────────────────────────────────────────

async def _synthesize_audio(script: list[dict], dialogue_type: str) -> tuple[Optional[str], list[dict]]:
    """Synthesize each line, return (mp3_path, timestamps)."""
    try:
        import edge_tts
        _MP3_BYTES_PER_MS = 16000 / 1000
        _PAUSE_MS    = 500
        _PAUSE_BYTES = int(_MP3_BYTES_PER_MS * _PAUSE_MS)

        all_chunks: list[bytes] = []
        timestamps: list[dict] = []
        cursor_bytes = 0

        for i, line in enumerate(script):
            speaker = line.get("speaker", "A")
            text    = line.get("text", "").strip()
            if not text:
                continue
            voice = _VOICE_B if speaker == "B" else (_VOICE_MONO if dialogue_type == "monologue" else _VOICE_A)
            communicate = edge_tts.Communicate(text, voice, rate="-10%")
            line_chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    line_chunks.append(chunk["data"])
            line_bytes = b"".join(line_chunks)
            line_len   = len(line_bytes)
            start_ms   = int(cursor_bytes / _MP3_BYTES_PER_MS)
            end_ms     = int((cursor_bytes + line_len) / _MP3_BYTES_PER_MS)
            timestamps.append({"index": i, "speaker": speaker, "text": text,
                                "start_ms": start_ms, "end_ms": end_ms})
            all_chunks.append(line_bytes)
            cursor_bytes += line_len
            pause = b"\x00" * _PAUSE_BYTES
            all_chunks.append(pause)
            cursor_bytes += _PAUSE_BYTES

        if not all_chunks:
            return None, []

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(b"".join(all_chunks))
        tmp.close()
        return tmp.name, timestamps
    except Exception:
        return None, []


# ── Pool replenishment ────────────────────────────────────────────────────────

_COMBOS = [
    ("general", "conversation"), ("general", "monologue"),
    ("toefl",   "conversation"), ("toefl",   "monologue"),
    ("ielts",   "conversation"), ("ielts",   "monologue"),
    ("cet",     "conversation"),
    ("gre",     "monologue"),
]

async def _replenish_pool(
    target_exam: str = "general",
    target_dtype: str = "conversation",
    cefr: str = "B1",
    question_type: Optional[str] = None,
) -> None:
    """Fill pool up to _POOL_TARGET for ONE (exam, dtype) combo only."""
    current = _pool_count(target_exam, target_dtype, question_type=question_type)
    needed  = _POOL_TARGET - current
    if needed <= 0:
        return
    for _ in range(needed):
        data = _load_builtin_script(target_exam, target_dtype, cefr, question_type=question_type)
        if not data:
            break
        audio_path, timestamps = await _synthesize_audio(data["script"], target_dtype)
        _pool_push(target_exam, target_dtype, data.get("difficulty", cefr), data, audio_path, timestamps)
        await asyncio.sleep(0)  # yield to event loop


async def _maybe_replenish(exam: str, dtype: str, cefr: str, question_type: Optional[str] = None) -> None:
    """Trigger background replenishment if pool is running low."""
    global _replenish_task
    current = _pool_count(exam, dtype, question_type=question_type)
    if current < _POOL_MIN:
        if _replenish_task is None or _replenish_task.done():
            _replenish_task = asyncio.create_task(_replenish_pool(exam, dtype, cefr, question_type=question_type))


# ── Startup pool seeding ──────────────────────────────────────────────────────

async def seed_pool_on_startup() -> None:
    """Pre-synthesise sessions in the background so first click is instant.
    Launches one concurrent task per (exam, dtype) combo that needs filling."""
    try:
        from gui.deps import get_components
        _, _, _, _, profile = get_components()
        target_exam = (profile.target_exam or "general").lower() if profile else "general"
        cefr = (profile.cefr_level or "B1") if profile else "B1"
    except Exception:
        target_exam = "general"
        cefr = "B1"

    # Build priority list: user's exam first, then general, then rest
    priority: list[tuple[str, str]] = []
    for dtype in ["conversation", "monologue"]:
        combo = (target_exam, dtype)
        if combo not in priority:
            priority.append(combo)
    for dtype in ["conversation", "monologue"]:
        combo = ("general", dtype)
        if combo not in priority:
            priority.append(combo)
    for exam, dtype in _COMBOS:
        combo = (exam, dtype)
        if combo not in priority:
            priority.append(combo)

    # Launch one independent background task per combo — they run concurrently
    for exam, dtype in priority:
        if _pool_count(exam, dtype) < _POOL_TARGET:
            asyncio.create_task(_replenish_pool(exam, dtype, cefr))


# ── API endpoints ─────────────────────────────────────────────────────────────

class AnswerRequest(BaseModel):
    question_index: int
    answer: str


@router.post("/start")
async def start_listening(
    exam: Optional[str] = None,
    difficulty: Optional[str] = None,
    dialogue_type: str = "conversation",
    question_type: Optional[str] = None,
):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile configured")

    cefr = difficulty or profile.cefr_level or "B1"
    target_exam = exam or profile.target_exam or "general"
    requested_qtype = _normalize_question_type(question_type)
    recent_topics = _recent_listening_topics(user_model, profile.user_id, target_exam, dialogue_type)

    data = None
    audio_path = None
    timestamps: list[dict] = []

    # Try pool first (instant)
    pooled = _pool_pop(
        target_exam,
        dialogue_type,
        cefr,
        exclude_topics=recent_topics,
        question_type=requested_qtype,
    )
    if pooled:
        data = pooled["data"]
        audio_path = pooled["audio_path"]
        timestamps = pooled["timestamps"]
        # If audio file was lost, re-synthesise quickly
        if not audio_path:
            audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)
    if not data and requested_qtype:
        data = _load_builtin_script(
            target_exam,
            dialogue_type,
            cefr,
            exclude_topics=recent_topics,
            question_type=requested_qtype,
        )
        if data:
            audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)
    if not data and requested_qtype and ai:
        generated = ai.generate_listening_dialogue(
            cefr,
            target_exam,
            dialogue_type,
            question_types=[requested_qtype],
        )
        if generated and generated.get("script"):
            data = generated
            data["question_types"] = _extract_question_types(data) or [requested_qtype]
            audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)
    if not data:
        pooled = _pool_pop(target_exam, dialogue_type, cefr, exclude_topics=recent_topics)
        if pooled:
            data = pooled["data"]
            audio_path = pooled["audio_path"]
            timestamps = pooled["timestamps"]
            if not audio_path:
                audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)
    if not data:
        data = _load_builtin_script(target_exam, dialogue_type, cefr, exclude_topics=recent_topics)
        if data:
            audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)
    if not data:
        if not ai:
            raise HTTPException(400, "No built-in script found and AI not configured")
        data = ai.generate_listening_dialogue(cefr, target_exam, dialogue_type)
        data["question_types"] = _extract_question_types(data)
        if not data or not data.get("script"):
            raise HTTPException(500, "Failed to generate listening content")
        audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)

    matched_qtype = requested_qtype if _question_type_matches(data, requested_qtype) else ""

    sid = str(uuid.uuid4())
    db_sid = user_model.start_session(profile.user_id, "listening")
    _sessions[sid] = {
        "data": data,
        "audio_path": audio_path,
        "timestamps": timestamps,
        "answers": {},
        "play_count": 0,
        "cefr": cefr,
        "exam": target_exam,
        "dialogue_type": dialogue_type,
        "requested_question_type": requested_qtype,
        "db_session_id": db_sid,
        "started_at": datetime.now().isoformat(),
        "completed": False,
    }

    # Replenish pool in background immediately after session starts
    asyncio.create_task(_maybe_replenish(target_exam, dialogue_type, cefr, question_type=requested_qtype or None))

    return {
        "session_id":     sid,
        "topic":          data.get("topic", ""),
        "type":           data.get("type", dialogue_type),
        "dialogue_type":  dialogue_type,
        "question_type":  matched_qtype or requested_qtype or "",
        "question_type_label": _question_type_label(matched_qtype or requested_qtype),
        "question_types": _extract_question_types(data),
        "difficulty":     cefr,
        "exam":           target_exam,
        "question_count": len(data.get("questions", [])),
        "audio_ready":    audio_path is not None,
        "source":         data.get("source", "builtin"),
        "timestamps":     timestamps,
    }


@router.get("/pool/status")
def pool_status():
    """Return current pool counts per combo (for debugging / UI indicator)."""
    try:
        conn = _get_pool_db()
        with _pool_lock:
            rows = conn.execute(
                "SELECT exam, dtype, COUNT(*) FROM pool GROUP BY exam, dtype"
            ).fetchall()
        return {"pool": [{"exam": r[0], "type": r[1], "count": r[2]} for r in rows]}
    except Exception as e:
        return {"pool": [], "error": str(e)}


@router.get("/audio/{session_id}")
async def get_audio(session_id: str):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    if not sess.get("audio_path") or not Path(sess["audio_path"]).exists():
        raise HTTPException(503, "Audio not ready")
    if sess["play_count"] >= _MAX_PLAYS:
        raise HTTPException(403, "Maximum plays reached")

    sess["play_count"] += 1
    path = sess["audio_path"]

    from fastapi.responses import FileResponse as _FileResponse
    return _FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"X-Play-Count": str(sess["play_count"]), "X-Max-Plays": str(_MAX_PLAYS)},
    )


@router.get("/question/{session_id}/{index}")
def get_question(session_id: str, index: int):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    questions = sess["data"].get("questions", [])
    if index < 0 or index >= len(questions):
        raise HTTPException(404, "Question not found")
    q = questions[index]
    return {
        "index":    index,
        "total":    len(questions),
        "question": q["question"],
        "options":  q["options"],
        "answered": index in sess["answers"],
    }


@router.post("/answer/{session_id}")
def submit_answer(session_id: str, req: AnswerRequest):
    kb, srs, user_model, ai, profile = get_components()
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    questions = sess["data"].get("questions", [])
    idx = req.question_index
    if idx < 0 or idx >= len(questions):
        raise HTTPException(404, "Question not found")
    q       = questions[idx]
    correct = q.get("answer", "A").upper()
    user_ans = req.answer.upper()
    is_correct = user_ans == correct
    sess["answers"][idx] = {"user": user_ans, "correct": correct, "is_correct": is_correct}
    all_answered = len(sess["answers"]) >= len(questions)
    if all_answered and not sess.get("completed") and profile:
        correct_count = sum(1 for item in sess["answers"].values() if item.get("is_correct"))
        accuracy = correct_count / max(len(questions), 1)
        available_qtypes = _extract_question_types(sess.get("data", {}))
        requested_qtype = str(sess.get("requested_question_type", "") or "").strip()
        recap = build_listening_recap(
            topic=sess["data"].get("topic", ""),
            correct=correct_count,
            total=len(questions),
            question_type=requested_qtype or (available_qtypes[0] if available_qtypes else ""),
            dialogue_type=sess.get("dialogue_type", ""),
        )
        content_json = json.dumps(
            {
                "exam": sess.get("exam", ""),
                "dialogue_type": sess.get("dialogue_type", ""),
                "question_type": requested_qtype,
                "question_types": available_qtypes,
                "topic": sess["data"].get("topic", ""),
                "source": sess["data"].get("source", "builtin"),
                "question_count": len(questions),
                "correct": correct_count,
                **recap,
            },
            ensure_ascii=False,
        )
        started_at = sess.get("started_at")
        duration_sec = 0
        if started_at:
            try:
                duration_sec = max(0, int((datetime.now() - datetime.fromisoformat(started_at)).total_seconds()))
            except ValueError:
                duration_sec = 0
        user_model.end_session(
            sess["db_session_id"],
            duration_sec,
            len(questions),
            accuracy,
            content_json=content_json,
        )
        sess["completed"] = True
    return {
        "correct":          is_correct,
        "correct_answer":   correct,
        "explanation":      q.get("explanation", ""),
        "session_complete": all_answered,
    }


@router.get("/transcript/{session_id}")
def get_transcript(session_id: str):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    questions = sess["data"].get("questions", [])
    if len(sess["answers"]) < len(questions):
        raise HTTPException(403, "Complete all questions first")
    return {
        "script":     sess["data"].get("script", []),
        "timestamps": sess.get("timestamps", []),
    }


@router.get("/status/{session_id}")
def get_status(session_id: str):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return {
        "play_count":     sess["play_count"],
        "max_plays":      _MAX_PLAYS,
        "plays_remaining": max(0, _MAX_PLAYS - sess["play_count"]),
        "answers_count":  len(sess["answers"]),
        "question_count": len(sess["data"].get("questions", [])),
        "audio_ready":    bool(sess.get("audio_path") and Path(sess["audio_path"]).exists()),
    }
