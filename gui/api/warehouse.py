"""Content warehouse API — pre-generate and cache AI content locally."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/warehouse", tags=["warehouse"])


def _save_reading_passage(kb, ai, cefr_level: str, exam: str) -> bool:
    """Generate one reading passage and save to KB. Returns True on success."""
    try:
        gen = ai.generate_reading_passage(cefr_level=cefr_level, exam=exam)
        passage_text = gen["passage"]
        chunk_id = f"ai_warehouse_{uuid.uuid4().hex[:12]}"
        questions = []
        try:
            questions = ai.generate_comprehension_questions(
                passage=passage_text,
                cefr_level=cefr_level,
                num_questions=3,
                exam=exam,
            ) or []
        except Exception:
            pass
        from core.ingestion.pipeline import Chunk, ContentType
        chunk = Chunk(
            chunk_id=chunk_id,
            source_file="ai_warehouse",
            content_type=ContentType.READING,
            difficulty=gen["difficulty"],
            topic=gen["topic"],
            exam=exam,
            language="en",
            text=passage_text,
            metadata={"questions": json.dumps(questions), "ai_generated": True},
        )
        kb.add_chunks([chunk])
        return True
    except Exception:
        return False


def _save_writing_prompt(kb, ai, cefr_level: str, exam: str) -> bool:
    """Generate one writing prompt and save to KB. Returns True on success."""
    try:
        prompt_text = ai.generate_writing_prompt(cefr_level=cefr_level, exam=exam)
        if not prompt_text:
            return False
        chunk_id = f"ai_writing_{uuid.uuid4().hex[:12]}"
        from core.ingestion.pipeline import Chunk, ContentType
        chunk = Chunk(
            chunk_id=chunk_id,
            source_file="ai_warehouse",
            content_type=ContentType.WRITING,
            difficulty=cefr_level,
            topic="writing_prompt",
            exam=exam,
            language="en",
            text=prompt_text,
            metadata={"ai_generated": True},
        )
        kb.add_chunks([chunk])
        return True
    except Exception:
        return False


@router.post("/populate")
def populate_warehouse(target_per_level: int = 2):
    """
    Background task: generate AI reading passages and writing prompts
    for the current user's exam and CEFR level, store in KB warehouse.
    Safe to call repeatedly — skips if enough content already exists.
    """
    kb, srs, user_model, ai, profile = get_components()
    if not ai or not profile:
        return {"ok": False, "reason": "No AI client or profile"}

    exam = profile.target_exam or "general"
    cefr = profile.cefr_level or "B1"

    # Count existing warehouse reading passages
    existing_reading = kb._sql.execute(
        "SELECT COUNT(*) FROM chunks WHERE content_type='reading' AND source_file='ai_warehouse' AND exam IN (?, 'general') AND difficulty=?",
        (exam, cefr),
    ).fetchone()[0]

    existing_writing = kb._sql.execute(
        "SELECT COUNT(*) FROM chunks WHERE content_type='writing' AND source_file='ai_warehouse' AND exam IN (?, 'general') AND difficulty=?",
        (exam, cefr),
    ).fetchone()[0]

    reading_added = 0
    writing_added = 0

    needed_reading = max(0, target_per_level - existing_reading)
    needed_writing = max(0, target_per_level - existing_writing)

    for _ in range(needed_reading):
        if _save_reading_passage(kb, ai, cefr, exam):
            reading_added += 1

    for _ in range(needed_writing):
        if _save_writing_prompt(kb, ai, cefr, exam):
            writing_added += 1

    return {
        "ok": True,
        "reading_added": reading_added,
        "writing_added": writing_added,
        "reading_total": existing_reading + reading_added,
        "writing_total": existing_writing + writing_added,
    }


@router.get("/status")
def warehouse_status():
    """Return counts of pre-generated content in the warehouse."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        return {"reading": 0, "writing": 0}
    exam = profile.target_exam or "general"
    cefr = profile.cefr_level or "B1"
    reading = kb._sql.execute(
        "SELECT COUNT(*) FROM chunks WHERE content_type='reading' AND exam IN (?, 'general') AND difficulty=?",
        (exam, cefr),
    ).fetchone()[0]
    writing = kb._sql.execute(
        "SELECT COUNT(*) FROM chunks WHERE content_type='writing' AND exam IN (?, 'general') AND difficulty=?",
        (exam, cefr),
    ).fetchone()[0]
    return {"reading": reading, "writing": writing, "exam": exam, "cefr": cefr}
