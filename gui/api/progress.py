"""Progress summary and skill scores API."""
from __future__ import annotations

from fastapi import APIRouter
from gui.deps import get_components, load_config

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("")
def get_progress():
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        return {"error": "no_profile"}

    summary = user_model.progress_summary(profile.user_id)
    deck = srs.deck_stats(profile.user_id)

    # Session history last 14 days
    rows = srs._db.execute(
        """SELECT date(started_at) as day, COUNT(*) as sessions,
                  SUM(items_done) as items, AVG(accuracy) as acc
           FROM sessions WHERE user_id=?
           AND started_at >= date('now','-14 days')
           GROUP BY day ORDER BY day""",
        (profile.user_id,),
    ).fetchall()
    history = [{"day": r[0], "sessions": r[1], "items": r[2], "accuracy": round((r[3] or 0) * 100)} for r in rows]

    return {
        "name": profile.name,
        "cefr_level": profile.cefr_level,
        "target_exam": profile.target_exam,
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
    }
