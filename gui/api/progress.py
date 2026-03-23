"""Progress summary and skill scores API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from core.srs.engine import SM2Engine
from core.coach.service import CoachService
from gui.coach_runtime import build_coach_runtime
from gui.deps import _CONFIG_PATH, get_user_components, load_config

router = APIRouter(prefix="/api/progress", tags=["progress"])


_MODE_DEFAULTS = {
    "vocab": 0,
    "grammar": 0,
    "reading": 0,
    "listening": 0,
    "writing": 0,
    "speaking": 0,
    "chat": 0,
    "mock": 0,
}


def _normalize_mode(mode: str | None) -> str:
    mode = str(mode or "").strip().lower()
    if mode.startswith("mock_"):
        return "mock"
    return mode or "other"


def _empty_progress(ai_ready: bool) -> dict:
    return {
        "error": "no_profile",
        "configured": False,
        "has_profile": False,
        "name": "",
        "cefr_level": "B1",
        "target_exam": "general",
        "has_ai": ai_ready,
        "streak_days": 0,
        "total_sessions": 0,
        "total_items": 0,
        "avg_accuracy": 0,
        "skill_scores": {},
        "weak_areas": [],
        "srs_total": 0,
        "srs_due": 0,
        "srs_mature": 0,
        "history": [],
        "mode_counts": dict(_MODE_DEFAULTS),
        "recent_sessions": [],
        "today_summary": {"sessions": 0, "minutes": 0, "items": 0},
        "total_study_minutes": 0,
        "learning_days": 0,
        "target_exam_date": "",
        "coach_summary": {},
    }


def _resolve_data_dir() -> str:
    cfg = load_config() or {}
    raw = cfg.get("data_dir", "data")
    path = Path(raw)
    resolved = path if path.is_absolute() else _CONFIG_PATH.parent / raw
    return str(resolved.resolve())


@router.get("")
def get_progress():
    runtime = build_coach_runtime()
    user_model, profile = get_user_components()
    if not profile:
        return _empty_progress(bool(runtime.get("ai_ready")))

    coach_service = CoachService(user_model, profile, runtime)
    coach_summary = coach_service.coach_summary()

    summary = user_model.progress_summary(profile.user_id)
    deck = {"total": 0, "due_today": 0, "mature": 0}
    srs = None
    try:
        srs = SM2Engine(Path(_resolve_data_dir()) / "user.db")
        deck = srs.deck_stats(profile.user_id)
    finally:
        if srs is not None:
            try:
                srs._db.close()
            except Exception:
                pass

    # Session history last 14 days
    rows = user_model._db.execute(
        """SELECT date(started_at) as day, COUNT(*) as sessions,
                  SUM(items_done) as items, AVG(accuracy) as acc
           FROM sessions WHERE user_id=?
           AND date(started_at) >= date('now','localtime','-14 days')
           GROUP BY day ORDER BY day""",
        (profile.user_id,),
    ).fetchall()
    history = [{"day": r[0], "sessions": r[1], "items": r[2], "accuracy": round((r[3] or 0) * 100)} for r in rows]

    counts = dict(_MODE_DEFAULTS)
    mode_rows = user_model._db.execute(
        """SELECT mode, COUNT(*) AS count
           FROM sessions
           WHERE user_id=?
           GROUP BY mode""",
        (profile.user_id,),
    ).fetchall()
    for row in mode_rows:
        key = _normalize_mode(row["mode"])
        counts[key] = counts.get(key, 0) + int(row["count"] or 0)

    recent_rows = user_model._db.execute(
        """SELECT mode, accuracy, items_done, duration_sec, started_at, ended_at
           FROM sessions
           WHERE user_id=? AND ended_at IS NOT NULL
           ORDER BY ended_at DESC
           LIMIT 5""",
        (profile.user_id,),
    ).fetchall()
    recent_sessions = [
        {
            "mode": _normalize_mode(row["mode"]),
            "accuracy": round((row["accuracy"] or 0) * 100),
            "items_done": int(row["items_done"] or 0),
            "duration_sec": int(row["duration_sec"] or 0),
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
        }
        for row in recent_rows
    ]

    today_row = user_model._db.execute(
        """SELECT COUNT(*) AS sessions,
                  COALESCE(SUM(duration_sec), 0) AS duration_sec,
                  COALESCE(SUM(items_done), 0) AS items_done
           FROM sessions
           WHERE user_id=? AND date(COALESCE(ended_at, started_at)) = date('now','localtime')""",
        (profile.user_id,),
    ).fetchone()
    learning_days = user_model._db.execute(
        """SELECT COUNT(DISTINCT date(ended_at))
           FROM sessions
           WHERE user_id=? AND ended_at IS NOT NULL""",
        (profile.user_id,),
    ).fetchone()[0]

    return {
        "configured": True,
        "has_profile": True,
        "name": profile.name,
        "cefr_level": profile.cefr_level,
        "target_exam": profile.target_exam,
        "has_ai": bool(runtime.get("ai_ready")),
        "streak_days": summary.get("streak_days", 0),
        "total_sessions": summary.get("total_sessions", 0),
        "total_items": summary.get("total_items", 0),
        "avg_accuracy": summary.get("avg_accuracy", 0),
        "skill_scores": summary.get("skill_scores", {}),
        "weak_areas": summary.get("weak_areas", []),
        "srs_total": deck["total"],
        "srs_due": deck["due_today"],
        "srs_mature": deck["mature"],
        "history": history,
        "mode_counts": counts,
        "recent_sessions": recent_sessions,
        "today_summary": {
            "sessions": int(today_row["sessions"] or 0),
            "minutes": int((today_row["duration_sec"] or 0) // 60),
            "items": int(today_row["items_done"] or 0),
        },
        "total_study_minutes": int(profile.total_study_minutes or 0),
        "learning_days": int(learning_days or 0),
        "target_exam_date": getattr(profile, "target_exam_date", "") or "",
        "coach_summary": coach_summary,
    }
