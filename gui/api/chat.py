"""Chat API with SSE streaming responses."""
from __future__ import annotations

import json
import os
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.coach.service import CoachService
from core.memory.service import LearnerMemoryService
from core.review.service import ReviewPoolService
from core.vocab.catalog import normalize_word
from gui.deps import _CONFIG_PATH, get_components, load_config
from modes.chat import _TOPIC_STARTERS, EXAM_MODES

router = APIRouter(prefix="/api/chat", tags=["chat"])


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    db_session_id: str
    exam: str
    history: list = field(default_factory=list)
    turns: int = 0
    ai_override: Any = None


_sessions: dict[str, ChatSession] = {}


class RememberRequest(BaseModel):
    fact_type: str
    fact_key: str
    value: Any
    source: str = "chat"
    confidence: float = 1.0


class WordStatusRequest(BaseModel):
    word: str
    status: str
    definition_en: str = ""
    definition_zh: str = ""
    topic: str = "general"
    difficulty: str = "B1"
    tags: list[str] = []


def _memory_prompt(profile, user_model) -> str:
    memory = LearnerMemoryService(user_model._db, profile)
    review = ReviewPoolService(user_model._db, profile)
    facts = memory.facts(limit=6)
    summary = memory.memory_summary()
    review_batch = review.recommended_batch(profile.user_id, size=3)
    lines = [
        "You are the learner's long-term private English coach.",
        f"Target exam: {getattr(profile, 'target_exam', 'general') or 'general'}",
        f"CEFR: {getattr(profile, 'cefr_level', 'B1') or 'B1'}",
        f"Preferred style: {getattr(profile, 'preferred_style', 'direct') or 'direct'}",
    ]
    long_term_goal = str(getattr(profile, "long_term_goal", "") or "").strip()
    if long_term_goal:
        lines.append(f"Long-term goal: {long_term_goal}")
    prefs = list(getattr(profile, "study_preferences", []) or [])
    if prefs:
        lines.append("Study preferences: " + ", ".join(str(item) for item in prefs[:5]))
    if getattr(profile, "weak_areas", None):
        lines.append("Weak areas: " + ", ".join(list(profile.weak_areas)[:5]))
    if facts:
        compact = []
        for fact in facts[:5]:
            compact.append(f"{fact.fact_type}:{fact.fact_key}={fact.value}")
        lines.append("Known learner facts: " + " | ".join(compact))
    if int(summary.get("review_due_count", 0) or 0) > 0:
        lines.append(f"Review due count: {int(summary.get('review_due_count', 0) or 0)}")
    if int(summary.get("frequent_forgetting_count", 0) or 0) > 0:
        lines.append(f"Frequent forgetting count: {int(summary.get('frequent_forgetting_count', 0) or 0)}")
    if review_batch:
        lines.append("Words that likely need attention: " + ", ".join(item.word for item in review_batch))
    lines.append("Use this context to keep continuity, avoid overly easy repetition, and prefer one small useful next step.")
    lines.append("Do not dump internal memory metadata unless it helps the learner directly.")
    return "\n".join(lines)


def _session_memory_summary(profile, user_model) -> dict:
    memory = LearnerMemoryService(user_model._db, profile)
    summary = memory.memory_summary()
    coach = CoachService(user_model, profile, {"ai_ready": True})
    return {
        "facts_count": int(summary.get("facts_count", 0) or 0),
        "review_due_count": int(summary.get("review_due_count", 0) or 0),
        "frequent_forgetting_count": int(summary.get("frequent_forgetting_count", 0) or 0),
        "next_action": coach.next_action().as_dict(),
    }


@router.post("/start")
def start_chat(exam: Optional[str] = None, topic: Optional[str] = None):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    if not ai:
        raise HTTPException(400, "No API key configured")

    cfg = load_config()
    target = exam or profile.target_exam or "general"
    starters = _TOPIC_STARTERS.get(target, _TOPIC_STARTERS["general"])
    opener = topic or random.choice(starters)

    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "chat")
    sess = ChatSession(session_id=sid, user_id=profile.user_id, db_session_id=db_sid, exam=target)
    sess.history.append({"role": "assistant", "content": opener})
    _sessions[sid] = sess

    mode = EXAM_MODES.get(target, EXAM_MODES["general"])
    return {
        "session_id": sid,
        "opener": opener,
        "exam": target,
        "backend": cfg.get("backend", "deepseek"),
        "mode_name": mode["name"],
        "mode_description": mode["description"],
        "mode_tips": mode["tips"],
        "memory_summary": _session_memory_summary(profile, user_model),
    }


class MessageRequest(BaseModel):
    message: str


@router.post("/message/{session_id}")
def send_message(session_id: str, req: MessageRequest):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    kb, srs, user_model, ai, profile = get_components()
    client = sess.ai_override or ai
    sess.history.append({"role": "user", "content": req.message})
    sess.turns += 1

    def generate():
        try:
            memory_context = {"role": "system", "content": _memory_prompt(profile, user_model)}
            full_response = client.chat(
                messages=[memory_context] + sess.history,
                cefr_level=profile.cefr_level,
            )
            sess.history.append({"role": "assistant", "content": full_response})
            yield f"data: {json.dumps({'type': 'token', 'data': full_response})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/end/{session_id}")
def end_chat(session_id: str):
    sess = _sessions.pop(session_id, None)
    if not sess:
        return {"ok": True}
    kb, srs, user_model, ai, profile = get_components()
    content = json.dumps(sess.history, ensure_ascii=False)
    user_model.end_session(sess.db_session_id, 0, sess.turns, 1.0, content_json=content)
    return {"ok": True, "turns": sess.turns}


@router.get("/context/{session_id}")
def get_chat_context(session_id: str):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    kb, srs, user_model, ai, profile = get_components()
    memory = LearnerMemoryService(user_model._db, profile)
    review = ReviewPoolService(user_model._db, profile)
    return {
        "session_id": session_id,
        "prompt_context": _memory_prompt(profile, user_model),
        "memory_summary": memory.memory_summary(),
        "facts": [
            {
                "fact_type": item.fact_type,
                "fact_key": item.fact_key,
                "value": item.value,
                "source": item.source,
            }
            for item in memory.facts(limit=10)
        ],
        "review_words": [item.word for item in review.recommended_batch(profile.user_id, size=5)],
    }


@router.post("/remember/{session_id}")
def remember_from_chat(session_id: str, req: RememberRequest):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    kb, srs, user_model, ai, profile = get_components()
    memory = LearnerMemoryService(user_model._db, profile)
    fact = memory.remember_fact(
        req.fact_type,
        req.fact_key,
        req.value,
        source=req.source or "chat",
        confidence=req.confidence,
    )
    return {
        "ok": True,
        "fact": {
            "fact_type": fact.fact_type,
            "fact_key": fact.fact_key,
            "value": fact.value,
            "source": fact.source,
            "confidence": fact.confidence,
        },
        "memory_summary": memory.memory_summary(),
    }


@router.post("/word-status/{session_id}")
def update_word_status_from_chat(session_id: str, req: WordStatusRequest):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    kb, srs, user_model, ai, profile = get_components()
    word = normalize_word(req.word)
    if not word:
        raise HTTPException(400, "Word is required")
    row = srs._db.execute("SELECT word_id FROM vocabulary WHERE word=?", (word,)).fetchone()
    if row:
        word_id = row["word_id"]
    else:
        word_id = srs.add_word(
            word,
            req.definition_en or "",
            req.definition_zh or "",
            topic=req.topic or "general",
            difficulty=req.difficulty or profile.cefr_level or "B1",
            source="chat",
            exam_type=profile.target_exam or "general",
            subject_domain="general",
        )
    srs.enroll_words(profile.user_id, [word_id])
    memory = LearnerMemoryService(user_model._db, profile)
    due_for_review = "" if req.status == "known" else __import__("datetime").date.today().isoformat()
    state = memory.set_vocab_status(
        profile.user_id,
        word_id,
        req.status,
        source="chat",
        topic=req.topic or "general",
        difficulty=req.difficulty or profile.cefr_level or "B1",
        tags=list(req.tags or []),
        due_for_review=due_for_review,
    )
    if not state:
        raise HTTPException(500, "Failed to update vocab state")
    return {
        "ok": True,
        "word": state.word,
        "word_id": state.word_id,
        "status": state.status,
        "due_for_review": state.due_for_review,
        "memory_summary": memory.memory_summary(),
    }


class ConfigRequest(BaseModel):
    backend: str


@router.post("/config/{session_id}")
def update_config(session_id: str, req: ConfigRequest):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    kb, srs, user_model, ai, profile = get_components()
    cfg = load_config()

    _KEY_ENV = {
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen":     "DASHSCOPE_API_KEY",
        "openai":   "OPENAI_API_KEY",
        "anthropic":"ANTHROPIC_API_KEY",
    }
    env_var = _KEY_ENV.get(req.backend)
    key = os.environ.get(env_var, "") if env_var else ""

    license_cfg = None
    # Cloud license covers DeepSeek
    if not key and req.backend == "deepseek":
        from gui.license import get_license_ai_config

        data_dir = Path(cfg.get("data_dir", "data"))
        if not data_dir.is_absolute():
            data_dir = _CONFIG_PATH.parent / data_dir
        license_cfg = get_license_ai_config(data_dir)
        if license_cfg:
            key = license_cfg["api_key"]

    if not key:
        current = cfg.get("backend", "deepseek")
        return {"ok": False, "error": f"请先在设置中配置 {req.backend} 的 API Key", "current_backend": current}

    from ai.client import AIClient, _BACKENDS, _DEFAULT_MODELS
    data_dir = cfg.get("data_dir", "data")
    default_m, writing_m = _DEFAULT_MODELS.get(req.backend, _DEFAULT_MODELS["deepseek"])
    sess.ai_override = AIClient(
        api_key=key,
        cache_db_path=str(Path(data_dir) / "ai_cache.db"),
        default_model=default_m,
        writing_model=writing_m,
        base_url=license_cfg["base_url"] if license_cfg else _BACKENDS[req.backend],
    )
    return {"ok": True, "backend": req.backend}


@router.get("/topic")
def get_topic(exam: Optional[str] = None):
    kb, srs, user_model, ai, profile = get_components()
    target = exam or (profile.target_exam if profile else "general") or "general"
    starters = _TOPIC_STARTERS.get(target, _TOPIC_STARTERS["general"])
    return {"topic": random.choice(starters)}
