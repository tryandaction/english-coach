"""
Unified Practice API for all skills with multi-dimensional filtering.

Provides a single entry point for starting practice sessions across
reading, listening, speaking, and writing with consistent filtering.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/practice", tags=["practice"])


_PRACTICE_CATALOG = {
    "toefl": {
        "reading": [
            {"id": "factual", "name": "Factual Information", "description": "定位文中明确信息", "badge": "Direct"},
            {"id": "inference", "name": "Inference", "description": "推断作者隐含信息"},
            {"id": "vocabulary", "name": "Vocabulary", "description": "词义上下文判断"},
            {"id": "negative_factual", "name": "Negative Factual", "description": "找出 NOT true 的信息"},
            {"id": "rhetorical_purpose", "name": "Rhetorical Purpose", "description": "作者为何提到某例子"},
            {"id": "reference", "name": "Reference", "description": "代词/指代对象判断"},
            {"id": "sentence_simplification", "name": "Sentence Simplification", "description": "长难句改写理解"},
            {"id": "insert_text", "name": "Insert Text", "description": "句子插入位置判断"},
            {"id": "prose_summary", "name": "Prose Summary", "description": "主旨与关键信息总结"},
            {"id": "fill_table", "name": "Fill in a Table", "description": "分类归纳信息"},
        ],
        "listening": [
            {"id": "detail", "name": "Detail", "description": "细节信息定位"},
            {"id": "inference", "name": "Inference", "description": "推断说话人意图"},
            {"id": "organization", "name": "Organization", "description": "讲座结构判断"},
            {"id": "attitude", "name": "Attitude", "description": "说话人口吻/态度"},
        ],
        "writing": [
            {"id": "integrated", "name": "Integrated Writing", "description": "读听写综合任务"},
            {"id": "independent", "name": "Independent Writing", "description": "独立议论文写作"},
        ],
        "speaking": [
            {"id": "independent", "name": "Independent", "description": "独立口语表达"},
            {"id": "listen_repeat", "name": "Listen & Repeat", "description": "句子复述训练"},
            {"id": "virtual_interview", "name": "Virtual Interview", "description": "采访式口语应答"},
        ],
    },
    "ielts": {
        "reading": [
            {"id": "tfng", "name": "True / False / Not Given", "description": "IELTS 高频判断题", "badge": "Direct"},
            {"id": "matching_headings", "name": "Matching Headings", "description": "段落标题匹配"},
            {"id": "summary_completion", "name": "Summary Completion", "description": "摘要填空"},
            {"id": "matching_information", "name": "Matching Information", "description": "信息定位匹配"},
            {"id": "short_answer", "name": "Short Answer", "description": "简答题"},
            {"id": "diagram_label", "name": "Diagram Label", "description": "图示标注"},
        ],
        "listening": [
            {"id": "multiple_choice", "name": "Multiple Choice", "description": "单选/多选"},
            {"id": "form_completion", "name": "Form Completion", "description": "表格/表单填空"},
            {"id": "matching", "name": "Matching", "description": "匹配题"},
        ],
        "writing": [
            {"id": "task1", "name": "Task 1", "description": "图表/流程图/信件"},
            {"id": "task2", "name": "Task 2", "description": "议论文"},
        ],
        "speaking": [
            {"id": "part1", "name": "Part 1", "description": "短答面试题"},
            {"id": "part2", "name": "Part 2", "description": "Cue Card 长回答"},
            {"id": "part3", "name": "Part 3", "description": "深入讨论题"},
        ],
    },
}


def _row_value(row, key: str, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        return default


def _has_content(kb, content_type: str, exam: str) -> bool:
    try:
        rows = kb.get_by_type(
            content_type=content_type,
            exam=exam,
            limit=1,
            random_order=True,
        )
        return bool(rows)
    except Exception:
        return False


def _listening_state(exam: str, cefr: str, has_ai: bool) -> tuple[str, bool, str]:
    try:
        from gui.api.listening import _load_builtin_script

        has_builtin = bool(
            _load_builtin_script(exam, "conversation", cefr)
            or _load_builtin_script(exam, "monologue", cefr)
            or _load_builtin_script("general", "conversation", cefr)
            or _load_builtin_script("general", "monologue", cefr)
        )
    except Exception:
        has_builtin = False

    if has_builtin:
        return (
            "direct",
            True,
            "可直接进入 Listening 实战页；当前按题型映射到 conversation / lecture 预设，尚未做到严格按题型抽题。",
        )
    if has_ai:
        return (
            "needs_ai",
            True,
            "本地内置听力素材不足，将改用 AI 生成；当前仍按 conversation / lecture 预设进入。",
        )
    return (
        "construction",
        False,
        "当前没有可用的内置听力素材，且未配置 AI，暂不可用。",
    )


def _direct_reading_state(reading_ready: bool, has_ai: bool) -> tuple[str, bool, str]:
    if reading_ready:
        return ("direct", True, "离线题库与本地 fallback 已接通，可直接练习。")
    if has_ai:
        return ("needs_ai", True, "当前数据目录缺少对应阅读素材，将改用 AI 生成。")
    return ("construction", False, "当前数据目录没有对应阅读素材，暂不可用。")


def _practice_item(section: str, item: dict, mode: str, available: bool, reason: str) -> dict:
    return {
        "section": section,
        "id": item["id"],
        "name": item["name"],
        "description": item["description"],
        "badge": item.get("badge"),
        "mode": mode,
        "available": available,
        "reason": reason,
    }


def _task_page_state(section: str, has_ai: bool) -> tuple[str, bool, str]:
    if section == "speaking":
        if has_ai:
            return ("direct", True, "可直接进入口语任务并获得 AI 评分反馈。")
        return ("direct", True, "可直接进入口语任务做练习；评分反馈需配置 AI。")
    if has_ai:
        return ("direct", True, "可直接进入写作任务并获得 AI 反馈。")
    return ("direct", True, "可直接进入写作题面练习；反馈需配置 AI。")


@router.get("/catalog")
def get_practice_catalog():
    kb, srs, user_model, ai, profile = get_components()
    has_ai = ai is not None
    cefr = (profile.cefr_level or "B2") if profile else "B2"
    exams = {}

    for exam, sections in _PRACTICE_CATALOG.items():
        reading_ready = _has_content(kb, "reading", exam)
        reading_mode, reading_available, reading_reason = _direct_reading_state(reading_ready, has_ai)
        listening_mode, listening_available, listening_reason = _listening_state(exam, cefr, has_ai)
        exam_sections = {}

        for section, items in sections.items():
            if section == "reading":
                exam_sections[section] = [
                    _practice_item(section, item, reading_mode, reading_available, reading_reason)
                    for item in items
                ]
                continue

            if section == "listening":
                exam_sections[section] = [
                    _practice_item(section, item, listening_mode, listening_available, listening_reason)
                    for item in items
                ]
                continue

            if section == "speaking":
                mode, available, reason = _task_page_state(section, has_ai)
                exam_sections[section] = [
                    _practice_item(section, item, mode, available, reason)
                    for item in items
                ]
                continue

            mode, available, reason = _task_page_state(section, has_ai)
            exam_sections[section] = [
                _practice_item(section, item, mode, available, reason)
                for item in items
            ]

        exams[exam] = {
            "reading_ready": reading_ready,
            "sections": exam_sections,
        }

    return {
        "active_exam": (profile.target_exam or "toefl").lower() if profile else "toefl",
        "has_ai": has_ai,
        "exams": exams,
    }


class PracticeRequest(BaseModel):
    exam: str  # toefl/ielts/gre/cet
    skill: str  # reading/listening/speaking/writing
    difficulty: Optional[int] = None  # 1-10 scale
    question_types: Optional[list[str]] = None
    subject: Optional[str] = None
    practice_mode: str = "single"  # single/mock/targeted/error_review
    time_limit: Optional[int] = None  # minutes, for mock mode


@router.post("/start-practice")
def start_practice_session(req: PracticeRequest):
    """
    Start a practice session for any skill with multi-dimensional filtering.

    Routes to appropriate skill API based on parameters.
    """
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    # Validate parameters
    valid_exams = ["toefl", "ielts", "gre", "cet", "general"]
    valid_skills = ["reading", "listening", "speaking", "writing", "vocab", "grammar"]
    valid_modes = ["single", "mock", "targeted", "error_review"]

    if req.exam not in valid_exams:
        raise HTTPException(400, f"Invalid exam type. Must be one of: {', '.join(valid_exams)}")

    if req.skill not in valid_skills:
        raise HTTPException(400, f"Invalid skill. Must be one of: {', '.join(valid_skills)}")

    if req.practice_mode not in valid_modes:
        raise HTTPException(400, f"Invalid practice mode. Must be one of: {', '.join(valid_modes)}")

    # Route to appropriate skill API
    if req.skill == "reading":
        return _start_reading_practice(req, kb, srs, user_model, ai, profile)
    elif req.skill == "listening":
        return _start_listening_practice(req, kb, srs, user_model, ai, profile)
    elif req.skill == "speaking":
        return _start_speaking_practice(req, kb, srs, user_model, ai, profile)
    elif req.skill == "writing":
        return _start_writing_practice(req, kb, srs, user_model, ai, profile)
    elif req.skill == "vocab":
        return _start_vocab_practice(req, kb, srs, user_model, ai, profile)
    elif req.skill == "grammar":
        return _start_grammar_practice(req, kb, srs, user_model, ai, profile)


def _start_reading_practice(req, kb, srs, user_model, ai, profile):
    """Start reading practice session."""
    from gui.api.reading import FilteredPracticeRequest, start_filtered_session

    filtered_req = FilteredPracticeRequest(
        exam=req.exam,
        difficulty=req.difficulty,
        subject=req.subject,
        question_types=req.question_types,
        practice_mode=req.practice_mode,
    )

    result = start_filtered_session(filtered_req)
    result["skill"] = "reading"
    result["time_limit"] = req.time_limit

    return result


def _start_listening_practice(req, kb, srs, user_model, ai, profile):
    """Start listening practice session."""
    # Determine CEFR level from difficulty
    if req.difficulty:
        if req.difficulty <= 3:
            cefr = "B1"
        elif req.difficulty <= 5:
            cefr = "B2"
        elif req.difficulty <= 7:
            cefr = "C1"
        else:
            cefr = "C2"
    else:
        cefr = profile.cefr_level or "B2"

    # Query listening content
    seen = user_model.get_seen_ids(profile.user_id)

    query_params = {
        "content_type": "listening",
        "difficulty": cefr,
        "exam": req.exam,
        "exclude_ids": seen,
        "limit": 5,
        "random_order": True,
    }

    rows = kb.get_by_type(**query_params)

    if not rows:
        raise HTTPException(404, "No listening content found matching filters")

    # Select first item
    row = rows[0]

    try:
        import json
        metadata = json.loads(_row_value(row, "metadata_json", "{}") or "{}")

        return {
            "session_id": uuid.uuid4().hex[:12],
            "skill": "listening",
            "exam": req.exam,
            "difficulty": cefr,
            "difficulty_score": req.difficulty,
            "practice_mode": req.practice_mode,
            "time_limit": req.time_limit,
            "content": {
                "title": metadata.get("title", ""),
                "duration_seconds": metadata.get("duration_seconds", 0),
                "script": metadata.get("script", []),
                "questions": metadata.get("questions", []),
                "accent": metadata.get("accent", "American"),
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Error loading listening content: {e}")


def _start_speaking_practice(req, kb, srs, user_model, ai, profile):
    """Start speaking practice session."""
    from gui.api.speaking import get_speaking_prompt

    task_type = (req.question_types or [None])[0]
    result = get_speaking_prompt(exam=req.exam, task_type=task_type)
    result["session_id"] = uuid.uuid4().hex[:12]
    result["skill"] = "speaking"
    result["practice_mode"] = req.practice_mode
    result["time_limit"] = req.time_limit
    result["feedback_requires_ai"] = ai is None
    return result


def _start_writing_practice(req, kb, srs, user_model, ai, profile):
    """Start writing practice session."""
    from gui.api.writing import get_prompt

    task_type = (req.question_types or [None])[0]
    result = get_prompt(exam=req.exam, task_type=task_type)
    result["session_id"] = uuid.uuid4().hex[:12]
    result["skill"] = "writing"
    result["practice_mode"] = req.practice_mode
    result["time_limit"] = req.time_limit
    result["feedback_requires_ai"] = ai is None
    return result


def _start_vocab_practice(req, kb, srs, user_model, ai, profile):
    """Start vocabulary practice session."""
    # Get words based on filters
    words = srs.get_new_words(
        user_id=profile.user_id,
        exam=req.exam,
        difficulty_score_min=req.difficulty - 1 if req.difficulty else None,
        difficulty_score_max=req.difficulty + 1 if req.difficulty else None,
        subject_domain=req.subject,
        limit=20,
    )

    if not words:
        raise HTTPException(404, "No vocabulary words found matching filters")

    return {
        "session_id": uuid.uuid4().hex[:12],
        "skill": "vocab",
        "exam": req.exam,
        "difficulty_score": req.difficulty,
        "subject": req.subject,
        "practice_mode": req.practice_mode,
        "word_count": len(words),
        "words": words[:10],  # Return first 10 for preview
    }


def _start_grammar_practice(req, kb, srs, user_model, ai, profile):
    """Start grammar practice session."""
    # Query grammar content
    seen = user_model.get_seen_ids(profile.user_id)

    rows = kb.get_by_type(
        content_type="grammar",
        difficulty=profile.cefr_level or "B2",
        exclude_ids=seen,
        limit=10,
        random_order=True,
    )

    if rows:
        return {
            "session_id": uuid.uuid4().hex[:12],
            "skill": "grammar",
            "exam": req.exam,
            "practice_mode": req.practice_mode,
            "exercise_count": len(rows),
            "source": "kb",
        }

    from modes.grammar import _DRILLS, _EXAM_CATEGORIES

    general_categories = ["articles", "prepositions", "tense", "subject_verb", "passive"]
    categories = [cat for cat in general_categories if cat in _DRILLS]
    if req.exam in _EXAM_CATEGORIES:
        categories.extend(cat for cat in _EXAM_CATEGORIES[req.exam] if cat in _DRILLS)
    categories = list(dict.fromkeys(categories))

    if not categories:
        raise HTTPException(404, "No grammar exercises found")

    return {
        "session_id": uuid.uuid4().hex[:12],
        "skill": "grammar",
        "exam": req.exam,
        "practice_mode": req.practice_mode,
        "exercise_count": sum(len(_DRILLS[cat]) for cat in categories),
        "categories": categories,
        "source": "builtin_drills",
        "fallback_reason": "当前数据目录没有 grammar 内容分块，已回退到内置 grammar drills。",
    }


@router.get("/practice-history")
def get_practice_history(
    user_id: Optional[str] = None,
    skill: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get practice history with optional filters."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    uid = user_id or profile.user_id

    # Build query
    conditions = ["user_id = ?"]
    params = [uid]

    if skill:
        conditions.append("mode = ?")
        params.append(skill)

    if date_from:
        conditions.append("started_at >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("started_at <= ?")
        params.append(date_to)

    params.extend([limit, offset])

    query = f"""
        SELECT session_id, mode, duration_sec, items_done, accuracy,
               started_at, ended_at, starred
        FROM sessions
        WHERE {' AND '.join(conditions)}
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
    """

    rows = user_model._db.execute(query, params).fetchall()

    sessions = [dict(row) for row in rows]

    # Get total count
    count_query = f"""
        SELECT COUNT(*) as total
        FROM sessions
        WHERE {' AND '.join(conditions)}
    """
    total = user_model._db.execute(count_query, params[:-2]).fetchone()["total"]

    return {
        "sessions": sessions,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/error-analysis")
def get_error_analysis(skill: str):
    """Get error analysis for a specific skill."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    # Get skill scores
    skill_prefix = f"{skill}_"
    rows = user_model._db.execute(
        """SELECT skill, score, sample_count
           FROM skill_scores
           WHERE user_id = ? AND skill LIKE ?
           ORDER BY score ASC""",
        (profile.user_id, f"{skill_prefix}%")
    ).fetchall()

    weak_skills = []
    for row in rows:
        if row["score"] < 0.60 and row["sample_count"] >= 3:
            weak_skills.append({
                "skill": row["skill"],
                "score": round(row["score"] * 100, 1),
                "sample_count": row["sample_count"],
                "status": "needs_improvement"
            })

    # Get recent errors from sessions
    recent_sessions = user_model._db.execute(
        """SELECT mode, accuracy, items_done, started_at
           FROM sessions
           WHERE user_id = ? AND mode = ?
           ORDER BY started_at DESC
           LIMIT 10""",
        (profile.user_id, skill)
    ).fetchall()

    error_rate = 0
    if recent_sessions:
        total_accuracy = sum(s["accuracy"] for s in recent_sessions)
        error_rate = 1.0 - (total_accuracy / len(recent_sessions))

    return {
        "skill": skill,
        "weak_areas": weak_skills,
        "recent_error_rate": round(error_rate * 100, 1),
        "recent_sessions": len(recent_sessions),
        "recommendations": _generate_recommendations(weak_skills, error_rate),
    }


def _generate_recommendations(weak_skills: list, error_rate: float) -> list[str]:
    """Generate practice recommendations based on weak areas."""
    recommendations = []

    if error_rate > 0.4:
        recommendations.append("Consider practicing at a lower difficulty level")

    if weak_skills:
        top_weak = weak_skills[0]["skill"]
        recommendations.append(f"Focus on {top_weak.replace('_', ' ')} exercises")

    if len(weak_skills) >= 3:
        recommendations.append("Use targeted practice mode to address multiple weak areas")

    if not recommendations:
        recommendations.append("Continue with current practice routine")

    return recommendations
