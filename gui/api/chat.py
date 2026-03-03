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

from gui.deps import get_components, load_config
from modes.chat import _TOPIC_STARTERS, EXAM_MODES

router = APIRouter(prefix="/api/chat", tags=["chat"])


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    db_session_id: str
    history: list = field(default_factory=list)
    turns: int = 0
    ai_override: Any = None


_sessions: dict[str, ChatSession] = {}


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
    sess = ChatSession(session_id=sid, user_id=profile.user_id, db_session_id=db_sid)
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
            full_response = client.chat(
                messages=sess.history,
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

    # Cloud license covers DeepSeek
    if not key and req.backend == "deepseek":
        from gui.license import get_cloud_api_key
        key = get_cloud_api_key() or ""

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
        base_url=_BACKENDS[req.backend],
    )
    return {"ok": True, "backend": req.backend}


@router.get("/topic")
def get_topic(exam: Optional[str] = None):
    kb, srs, user_model, ai, profile = get_components()
    target = exam or (profile.target_exam if profile else "general") or "general"
    starters = _TOPIC_STARTERS.get(target, _TOPIC_STARTERS["general"])
    return {"topic": random.choice(starters)}
