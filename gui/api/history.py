"""History API — session list, detail, star, delete."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException

from gui.deps import get_components, load_config

router = APIRouter(prefix="/api/history", tags=["history"])

_MODE_ICONS = {
    "vocab":   "🃏",
    "grammar": "✏️",
    "reading": "📖",
    "writing": "📝",
    "chat":    "💬",
}


def _auto_cleanup(user_model, user_id: str, retention_days: int) -> None:
    """Delete non-starred sessions older than retention_days (0 = never)."""
    if retention_days <= 0:
        return
    cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
    user_model._db.execute(
        "DELETE FROM sessions WHERE user_id=? AND starred=0 AND started_at < ?",
        (user_id, cutoff),
    )
    user_model._db.commit()


@router.get("/list")
def list_history(mode: Optional[str] = None, limit: int = 50):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    cfg = load_config()
    retention = int(cfg.get("history_retention_days", 30))
    _auto_cleanup(user_model, profile.user_id, retention)

    q = (
        "SELECT session_id, mode, duration_sec, items_done, accuracy, "
        "started_at, ended_at, starred "
        "FROM sessions WHERE user_id=? AND ended_at IS NOT NULL"
    )
    params: list = [profile.user_id]
    if mode:
        q += " AND mode=?"
        params.append(mode)
    q += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)

    rows = user_model._db.execute(q, params).fetchall()
    sessions = []
    for r in rows:
        d = dict(r)
        d["icon"] = _MODE_ICONS.get(d["mode"], "📋")
        d["accuracy_pct"] = round((d["accuracy"] or 0) * 100)
        sessions.append(d)
    return {"sessions": sessions, "retention_days": retention}


@router.get("/detail/{session_id}")
def get_detail(session_id: str):
    kb, srs, user_model, ai, profile = get_components()
    row = user_model._db.execute(
        "SELECT * FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    d = dict(row)
    if d.get("content_json"):
        d["content"] = json.loads(d["content_json"])
        del d["content_json"]
    d["accuracy_pct"] = round((d.get("accuracy") or 0) * 100)
    return d


@router.post("/star/{session_id}")
def toggle_star(session_id: str):
    kb, srs, user_model, ai, profile = get_components()
    row = user_model._db.execute(
        "SELECT starred FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    new_val = 0 if row["starred"] else 1
    user_model._db.execute(
        "UPDATE sessions SET starred=? WHERE session_id=?", (new_val, session_id)
    )
    user_model._db.commit()
    return {"ok": True, "starred": bool(new_val)}


@router.delete("/{session_id}")
def delete_session(session_id: str):
    kb, srs, user_model, ai, profile = get_components()
    user_model._db.execute(
        "DELETE FROM sessions WHERE session_id=?", (session_id,)
    )
    user_model._db.commit()
    return {"ok": True}
