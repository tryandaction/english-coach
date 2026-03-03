"""Grammar drill API — stateless per question, imports drill bank from modes/grammar.py."""
from __future__ import annotations

import random
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/grammar", tags=["grammar"])

from modes.grammar import _DRILLS, _EXAM_CATEGORIES, _CATEGORY_LABELS, _SKILL_MAP

_GENERAL_CATEGORIES = ["articles", "prepositions", "tense", "subject_verb", "passive"]


@router.get("/categories")
def list_categories(exam: Optional[str] = None):
    general = [
        {"key": k, "label": _CATEGORY_LABELS.get(k, k), "group": "General"}
        for k in _GENERAL_CATEGORIES if k in _DRILLS
    ]
    exam_specific = []
    if exam and exam in _EXAM_CATEGORIES:
        exam_specific = [
            {"key": k, "label": _CATEGORY_LABELS.get(k, k), "group": exam.upper()}
            for k in _EXAM_CATEGORIES[exam] if k in _DRILLS
        ]
    return {"categories": general + exam_specific, "exam": exam or "general"}


@router.get("/question")
def get_question(category: Optional[str] = None, exam: Optional[str] = None):
    # Build available categories based on exam
    if category and category in _DRILLS:
        cat = category
    elif exam and exam in _EXAM_CATEGORIES and _EXAM_CATEGORIES[exam]:
        # Mix general + exam-specific
        pool = _GENERAL_CATEGORIES + _EXAM_CATEGORIES[exam]
        pool = [c for c in pool if c in _DRILLS]
        cat = random.choice(pool)
    else:
        cat = random.choice(_GENERAL_CATEGORIES)

    drills = _DRILLS[cat]
    sentence, choices, correct_idx, explanation = random.choice(drills)
    return {
        "category": cat,
        "category_label": _CATEGORY_LABELS.get(cat, cat),
        "sentence": sentence,
        "choices": choices,
        "correct_index": correct_idx,
        "explanation": explanation,
    }


@router.get("/pool")
def get_question_pool(category: Optional[str] = None, exam: Optional[str] = None, n: int = 5):
    questions = []
    for _ in range(n):
        if category and category in _DRILLS:
            cat = category
        elif exam and exam in _EXAM_CATEGORIES and _EXAM_CATEGORIES[exam]:
            pool = _GENERAL_CATEGORIES + _EXAM_CATEGORIES[exam]
            pool = [c for c in pool if c in _DRILLS]
            cat = random.choice(pool)
        else:
            cat = random.choice(_GENERAL_CATEGORIES)
        sentence, choices, correct_idx, explanation = random.choice(_DRILLS[cat])
        questions.append({
            "category": cat,
            "category_label": _CATEGORY_LABELS.get(cat, cat),
            "sentence": sentence,
            "choices": choices,
            "correct_index": correct_idx,
            "explanation": explanation,
        })
    return {"questions": questions}


class AnswerRequest(BaseModel):
    category: str
    sentence: str
    user_index: int
    correct_index: int
    explanation: str


@router.post("/answer")
def submit_answer(req: AnswerRequest):
    kb, srs, user_model, ai, profile = get_components()
    correct = req.user_index == req.correct_index

    if profile:
        skill = _SKILL_MAP.get(req.category, "grammar_tense")
        user_model.record_answer(profile.user_id, skill, correct)

    return {
        "correct": correct,
        "correct_index": req.correct_index,
        "explanation": req.explanation,
    }
