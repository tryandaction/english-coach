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
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from gui.deps import get_components, get_content_dir

router = APIRouter(prefix="/api/listening", tags=["listening"])

_sessions: dict[str, dict] = {}
_MAX_PLAYS = 3
_VOICE_A    = "en-US-AriaNeural"
_VOICE_B    = "en-US-GuyNeural"
_VOICE_MONO = "en-GB-SoniaNeural"

_CONTENT_DIR = get_content_dir() / "listening"


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


def _pool_count(exam: str, dtype: str) -> int:
    try:
        conn = _get_pool_db()
        with _pool_lock:
            row = conn.execute(
                "SELECT COUNT(*) FROM pool WHERE exam=? AND dtype=?",
                (exam, dtype)
            ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def _pool_pop(exam: str, dtype: str, difficulty: str) -> Optional[dict]:
    """Pop the best matching item from the pool (exact difficulty first, then any)."""
    try:
        conn = _get_pool_db()
        with _pool_lock:
            # Try exact difficulty first
            row = conn.execute(
                "SELECT id, data_json, audio_path, timestamps_json FROM pool "
                "WHERE exam=? AND dtype=? AND difficulty=? ORDER BY RANDOM() LIMIT 1",
                (exam, dtype, difficulty)
            ).fetchone()
            if not row:
                # Fallback: any difficulty
                row = conn.execute(
                    "SELECT id, data_json, audio_path, timestamps_json FROM pool "
                    "WHERE exam=? AND dtype=? ORDER BY RANDOM() LIMIT 1",
                    (exam, dtype)
                ).fetchone()
            if not row:
                return None
            pid, data_json, audio_path, ts_json = row
            conn.execute("DELETE FROM pool WHERE id=?", (pid,))
            conn.commit()
        data = json.loads(data_json)
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

def _load_builtin_script(exam: str, dialogue_type: str, cefr: str) -> Optional[dict]:
    if not _CONTENT_DIR.exists():
        return None
    candidates = []
    for f in _CONTENT_DIR.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8").replace("\r\n", "\n")
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if not fm_match:
                continue
            meta = {}
            for line in fm_match.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
            file_exam  = meta.get("exam", "general")
            file_type  = meta.get("dialogue_type", "conversation")
            file_diff  = meta.get("difficulty", "B1")
            exam_match = (exam == "general" or file_exam == exam or file_exam == "general")
            type_match = (file_type == dialogue_type)
            cefr_levels = ["A1","A2","B1","B2","C1","C2"]
            try:
                diff_match = abs(cefr_levels.index(cefr) - cefr_levels.index(file_diff)) <= 1
            except ValueError:
                diff_match = True
            if exam_match and type_match and diff_match:
                candidates.append((f, meta, text[fm_match.end():]))
        except Exception:
            continue

    if not candidates:
        for f in _CONTENT_DIR.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8").replace("\r\n", "\n")
                fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
                if not fm_match:
                    continue
                meta = {}
                for line in fm_match.group(1).splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        meta[k.strip()] = v.strip()
                if meta.get("dialogue_type", "conversation") == dialogue_type:
                    candidates.append((f, meta, text[fm_match.end():]))
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

    return {
        "type": meta.get("dialogue_type", dialogue_type),
        "topic": meta.get("topic", ""),
        "difficulty": meta.get("difficulty", cefr),
        "script": script,
        "questions": questions,
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

async def _replenish_pool(target_exam: str = "general", target_dtype: str = "conversation",
                          cefr: str = "B1") -> None:
    """Fill pool up to _POOL_TARGET for ONE (exam, dtype) combo only."""
    current = _pool_count(target_exam, target_dtype)
    needed  = _POOL_TARGET - current
    if needed <= 0:
        return
    for _ in range(needed):
        data = _load_builtin_script(target_exam, target_dtype, cefr)
        if not data:
            break
        audio_path, timestamps = await _synthesize_audio(data["script"], target_dtype)
        _pool_push(target_exam, target_dtype, data.get("difficulty", cefr), data, audio_path, timestamps)
        await asyncio.sleep(0)  # yield to event loop


async def _maybe_replenish(exam: str, dtype: str, cefr: str) -> None:
    """Trigger background replenishment if pool is running low."""
    global _replenish_task
    current = _pool_count(exam, dtype)
    if current < _POOL_MIN:
        if _replenish_task is None or _replenish_task.done():
            _replenish_task = asyncio.create_task(_replenish_pool(exam, dtype, cefr))


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
):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile configured")

    cefr        = difficulty or profile.cefr_level or "B1"
    target_exam = exam or profile.target_exam or "general"

    # Try pool first (instant)
    pooled = _pool_pop(target_exam, dialogue_type, cefr)
    if pooled:
        data       = pooled["data"]
        audio_path = pooled["audio_path"]
        timestamps = pooled["timestamps"]
        # If audio file was lost, re-synthesise quickly
        if not audio_path:
            audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)
    else:
        # Pool empty — generate on demand (built-in first, AI fallback)
        data = _load_builtin_script(target_exam, dialogue_type, cefr)
        if not data:
            if not ai:
                raise HTTPException(400, "No built-in script found and AI not configured")
            data = ai.generate_listening_dialogue(cefr, target_exam, dialogue_type)
        if not data or not data.get("script"):
            raise HTTPException(500, "Failed to generate listening content")
        audio_path, timestamps = await _synthesize_audio(data["script"], dialogue_type)

    sid = str(uuid.uuid4())
    _sessions[sid] = {
        "data": data,
        "audio_path": audio_path,
        "timestamps": timestamps,
        "answers": {},
        "play_count": 0,
        "cefr": cefr,
        "exam": target_exam,
    }

    # Replenish pool in background immediately after session starts
    asyncio.create_task(_maybe_replenish(target_exam, dialogue_type, cefr))

    return {
        "session_id":     sid,
        "topic":          data.get("topic", ""),
        "type":           data.get("type", dialogue_type),
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
