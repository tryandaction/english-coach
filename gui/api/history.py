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
    "listening": "🎧",
    "writing": "📝",
    "speaking": "🗣",
    "chat":    "💬",
    "mock":    "⏱",
}


def _normalize_mode(mode: str | None) -> str:
    text = str(mode or "").strip().lower()
    if text.startswith("mock_"):
        return "mock"
    return text or "other"


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
        mode_key = _normalize_mode(d["mode"])
        d["mode"] = mode_key
        d["icon"] = _MODE_ICONS.get(mode_key, "📋")
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


@router.get("/daily")
def daily_history(limit_days: int = 14):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        return {"days": []}

    plan_rows = user_model._db.execute(
        """SELECT plan_date, stage, status, plan_json, summary_json
           FROM coach_daily_plan
           WHERE user_id=?
           ORDER BY plan_date DESC
           LIMIT ?""",
        (profile.user_id, limit_days),
    ).fetchall()
    session_day_rows = user_model._db.execute(
        """SELECT DISTINCT date(COALESCE(ended_at, started_at)) AS day
           FROM sessions
           WHERE user_id=? AND COALESCE(ended_at, started_at) IS NOT NULL
           ORDER BY day DESC
           LIMIT ?""",
        (profile.user_id, limit_days),
    ).fetchall()
    plan_map = {row["plan_date"]: row for row in plan_rows}
    ordered_days = []
    seen_days = set()
    for source in [list(plan_map.keys()), [row["day"] for row in session_day_rows if row["day"]]]:
        for day in source:
            if day and day not in seen_days:
                seen_days.add(day)
                ordered_days.append(day)
    ordered_days = sorted(ordered_days, reverse=True)[:limit_days]
    days = []
    for day_key in ordered_days:
        row = plan_map.get(day_key)
        sessions = user_model._db.execute(
            """SELECT session_id, mode, duration_sec, items_done, accuracy,
                      started_at, ended_at, starred, content_json
               FROM sessions
               WHERE user_id=? AND date(COALESCE(ended_at, started_at))=?
               ORDER BY COALESCE(ended_at, started_at) DESC""",
            (profile.user_id, day_key),
        ).fetchall()
        notification_count = user_model._db.execute(
            """SELECT COUNT(*) AS count
               FROM coach_notification_log
               WHERE user_id=? AND date(scheduled_for)=?""",
            (profile.user_id, day_key),
        ).fetchone()["count"]
        session_items = []
        for session in sessions:
            data = dict(session)
            mode_key = _normalize_mode(data["mode"])
            data["mode"] = mode_key
            data["icon"] = _MODE_ICONS.get(mode_key, "📋")
            data["accuracy_pct"] = round((data["accuracy"] or 0) * 100)
            if data.get("content_json"):
                try:
                    data["content"] = json.loads(data["content_json"])
                except Exception:
                    data["content"] = None
            data.pop("content_json", None)
            session_items.append(data)
        if row:
          summary = json.loads(row["summary_json"] or "{}")
          plan = json.loads(row["plan_json"] or "{}")
          stage = row["stage"]
          status = row["status"]
        else:
          total_minutes = int(sum(int(item["duration_sec"] or 0) for item in session_items) // 60)
          total_items = int(sum(int(item["items_done"] or 0) for item in session_items))
          summary = {
              "tasks_total": 0,
              "tasks_done": 0,
              "tasks_in_progress": 0,
              "completion_rate": 0,
              "due_now": 0,
              "today_sessions": len(session_items),
              "today_minutes": total_minutes,
              "today_items": total_items,
              "result_card": "这是升级前的历史训练记录，当前没有对应的 coach 计划快照。",
              "tomorrow_reason": "",
          }
          plan = {"tasks": []}
          stage = "growth"
          status = "done" if session_items else "planned"
        days.append(
            {
                "day": day_key,
                "stage": stage,
                "status": status,
                "plan": {
                    "tasks": plan.get("tasks", []),
                    "summary": summary,
                },
                "notification_count": int(notification_count or 0),
                "sessions": session_items,
            }
        )
    return {"days": days}
