from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.memory.service import LearnerMemoryService
from gui.deps import get_user_components

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryFactRequest(BaseModel):
    fact_type: str
    fact_key: str
    value: Any
    source: str = "manual"
    confidence: float = 1.0


def _service() -> tuple[LearnerMemoryService, Any]:
    user_model, profile = get_user_components()
    if not profile:
        raise HTTPException(400, "No profile")
    return LearnerMemoryService(user_model._db, profile), profile


def _empty_status() -> dict:
    return {
        "has_profile": False,
        "summary": {
            "facts_count": 0,
            "review_due_count": 0,
            "frequent_forgetting_count": 0,
            "known_words": 0,
            "unsure_words": 0,
            "unknown_words": 0,
            "last_event_at": "",
            "last_daily_snapshot": {},
        },
        "facts": [],
        "review_due": [],
        "frequent_forgetting": [],
    }


@router.get("/status")
def get_memory_status():
    try:
        service, profile = _service()
    except HTTPException:
        return _empty_status()
    return {
        "has_profile": True,
        "profile": {
            "user_id": profile.user_id,
            "preferred_style": getattr(profile, "preferred_style", "direct"),
            "study_preferences": list(getattr(profile, "study_preferences", []) or []),
            "long_term_goal": getattr(profile, "long_term_goal", "") or "",
            "target_exam": getattr(profile, "target_exam", "general"),
        },
        "summary": service.memory_summary(),
        "facts": [
            {
                "fact_type": item.fact_type,
                "fact_key": item.fact_key,
                "value": item.value,
                "source": item.source,
                "confidence": item.confidence,
                "updated_at": item.updated_at,
            }
            for item in service.facts(limit=20)
        ],
        "review_due": [
            {
                "word": item.word,
                "word_id": item.word_id,
                "status": item.status,
                "due_for_review": item.due_for_review,
                "wrong_count": item.wrong_count,
                "success_count": item.success_count,
                "tags": item.tags,
            }
            for item in service.review_due_list(limit=20)
        ],
        "frequent_forgetting": [
            {
                "word": item.word,
                "word_id": item.word_id,
                "status": item.status,
                "wrong_count": item.wrong_count,
                "success_count": item.success_count,
                "tags": item.tags,
            }
            for item in service.frequent_forgetting_list(limit=20)
        ],
    }


@router.get("/facts")
def get_facts(fact_type: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    service, _ = _service()
    return {
        "facts": [
            {
                "fact_type": item.fact_type,
                "fact_key": item.fact_key,
                "value": item.value,
                "source": item.source,
                "confidence": item.confidence,
                "updated_at": item.updated_at,
            }
            for item in service.facts(fact_type=fact_type, limit=limit)
        ]
    }


@router.post("/facts")
def remember_fact(req: MemoryFactRequest):
    service, _ = _service()
    fact = service.remember_fact(
        req.fact_type,
        req.fact_key,
        req.value,
        source=req.source,
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
            "updated_at": fact.updated_at,
        },
        "summary": service.memory_summary(),
    }
