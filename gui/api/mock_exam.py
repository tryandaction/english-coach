"""
Mock Exam Mode implementation with timing and comprehensive scoring.

Provides realistic exam simulation with:
- Strict timing per section
- No immediate feedback during exam
- Comprehensive score report after completion
- Percentile ranking based on historical data
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.coach.recap import build_mock_exam_recap, build_mock_section_recap
from gui.deps import get_components

router = APIRouter(prefix="/api/mock-exam", tags=["mock-exam"])


def _row_value(row, key: str, default=None):
    if row is None:
        return default
    try:
        return row[key]
    except Exception:
        return default


def _parse_questions(value) -> list[dict]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        import json
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


@dataclass
class MockExamSession:
    session_id: str
    db_session_id: str
    user_id: str
    exam: str  # toefl/ielts
    sections: list[dict]  # List of section data
    current_section: int = 0
    answers: dict = field(default_factory=dict)  # section_id -> [answers]
    start_time: float = field(default_factory=time.time)
    section_times: dict = field(default_factory=dict)  # section_id -> duration_sec
    completed_sections: dict = field(default_factory=dict)  # section_index -> summary
    report: Optional[dict] = None


_mock_sessions: dict[str, MockExamSession] = {}

_MOCK_SECTION_BLUEPRINTS = {
    "toefl": {
        "reading": {"item_count": 10, "time_limit": 18},
        "listening": {"item_count": 6, "time_limit": 10},
        "speaking": {"item_count": 1, "time_limit": 4},
        "writing": {"item_count": 1, "time_limit": 20},
    },
    "ielts": {
        "reading": {"item_count": 10, "time_limit": 20},
        "listening": {"item_count": 10, "time_limit": 10},
        "speaking": {"item_count": 1, "time_limit": 5},
        "writing": {"item_count": 1, "time_limit": 20},
    },
}


def _section_status(session: MockExamSession, index: int) -> str:
    if index < session.current_section:
        return "done"
    if index == session.current_section and session.report is None:
        return "current"
    return "locked"


def _serialize_session(session: MockExamSession) -> dict:
    current_index = min(session.current_section, max(len(session.sections) - 1, 0))
    return {
        "session_id": session.session_id,
        "exam": session.exam,
        "current_section": session.current_section,
        "current_section_name": session.sections[current_index]["section"] if session.sections else None,
        "total_sections": len(session.sections),
        "completed_sections": len(session.completed_sections),
        "elapsed_time": int(time.time() - session.start_time),
        "total_time": sum(section["time_limit"] for section in session.sections),
        "instructions": _get_exam_instructions(session.exam),
        "exam_complete": session.report is not None,
        "sections": [
            {
                "name": section["section"],
                "time_limit": section["time_limit"],
                "item_count": section.get("item_count", 0),
                "status": _section_status(session, index),
                "available": index <= session.current_section and session.report is None,
                "summary": session.completed_sections.get(index),
            }
            for index, section in enumerate(session.sections)
        ],
        "report": session.report,
    }


# TOEFL iBT timing (minutes)
TOEFL_TIMING = {
    "reading": 54,  # 3 passages, 18 minutes each
    "listening": 41,  # 3 conversations + 4 lectures
    "speaking": 17,  # 4 tasks
    "writing": 30,  # 2 tasks (20 + 10 minutes)
}

# IELTS timing (minutes)
IELTS_TIMING = {
    "listening": 30,  # + 10 minutes transfer time
    "reading": 60,
    "writing": 60,  # Task 1: 20 min, Task 2: 40 min
    "speaking": 14,  # Part 1: 5 min, Part 2: 4 min, Part 3: 5 min
}


class StartMockExamRequest(BaseModel):
    exam: str  # toefl/ielts
    sections: list[str]  # ["reading", "listening", "speaking", "writing"]


@router.post("/start")
def start_mock_exam(req: StartMockExamRequest):
    """Start a mock exam session."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    if req.exam not in ["toefl", "ielts"]:
        raise HTTPException(400, "Invalid exam type")

    # Validate sections
    valid_sections = ["reading", "listening", "speaking", "writing"]
    for section in req.sections:
        if section not in valid_sections:
            raise HTTPException(400, f"Invalid section: {section}")

    sections_data = []
    timing = TOEFL_TIMING if req.exam == "toefl" else IELTS_TIMING
    blueprints = _MOCK_SECTION_BLUEPRINTS.get(req.exam, {})

    for section in req.sections:
        blueprint = blueprints.get(section, {})
        section_data = {
            "section": section,
            # Start instantly, then let the destination section page generate the
            # actual task content. The launcher still shows realistic micro-section
            # expectations for item count and time.
            "item_count": int(blueprint.get("item_count", 1) or 1),
            "time_limit": int(blueprint.get("time_limit", timing.get(section, 60)) or 60),
        }
        sections_data.append(section_data)

    # Create session
    session_id = uuid.uuid4().hex[:12]
    db_session_id = user_model.start_session(profile.user_id, f"mock_{req.exam}")

    _mock_sessions[session_id] = MockExamSession(
        session_id=session_id,
        db_session_id=db_session_id,
        user_id=profile.user_id,
        exam=req.exam,
        sections=sections_data,
    )

    return _serialize_session(_mock_sessions[session_id])


def _generate_section_content(section: str, exam: str, profile, kb, srs, user_model, ai):
    """Generate content for a specific exam section."""
    cefr = profile.cefr_level or "B2"

    if section == "reading":
        from gui.api.reading import (
            _cache_passage_questions,
            _coalesce_passages,
            _needs_ai_passage_upgrade,
            _offline_fallback_questions,
        )

        # Generate 3 passages for TOEFL, 3 passages for IELTS
        passage_count = 3
        passages = []
        seen = user_model.get_seen_ids(profile.user_id)
        rows = kb.get_by_type(
            content_type="reading",
            difficulty=cefr,
            exam=exam,
            exclude_ids=seen,
            limit=36,
            random_order=True,
        )
        passage_records = _coalesce_passages(kb, rows, seen_chunk_ids=seen, limit=passage_count)
        if len(passage_records) < passage_count:
            extra_rows = kb.get_by_type(
                content_type="reading",
                difficulty=cefr,
                exam=exam,
                limit=36,
                random_order=True,
            )
            existing = {record.chunk_id for record in passage_records}
            for record in _coalesce_passages(kb, extra_rows, limit=passage_count * 2):
                if record.chunk_id in existing:
                    continue
                passage_records.append(record)
                existing.add(record.chunk_id)
                if len(passage_records) >= passage_count:
                    break

        for record in passage_records[:passage_count]:
            passage_text = record.passage_text
            word_count = record.word_count
            questions = list(record.questions)

            if ai and _needs_ai_passage_upgrade(exam, record.word_count):
                try:
                    gen = ai.generate_reading_passage(
                        cefr_level=record.difficulty or cefr,
                        exam=exam,
                        topic=record.topic,
                    )
                    passage_text = gen["passage"]
                    word_count = len(passage_text.split())
                    questions = ai.generate_comprehension_questions(
                        passage=passage_text,
                        cefr_level=gen["difficulty"],
                        num_questions=10 if exam == "toefl" else 13,
                        exam=exam,
                    ) or []
                except Exception:
                    questions = []

            if not questions and ai:
                try:
                    questions = ai.generate_comprehension_questions(
                        passage=passage_text,
                        cefr_level=record.difficulty or cefr,
                        num_questions=10 if exam == "toefl" else 13,
                        exam=exam,
                    ) or []
                    if questions and passage_text == record.passage_text:
                        _cache_passage_questions(kb, record, questions)
                except Exception:
                    questions = []
            if not questions:
                questions = _offline_fallback_questions(passage_text, None, exam)

            if record.chunk_ids or record.chunk_id:
                user_model.mark_seen(profile.user_id, record.chunk_ids or [record.chunk_id])

            passages.append({
                "passage": passage_text,
                "questions": questions,
                "word_count": word_count,
            })

        return {
            "section": "reading",
            "passages": passages,
            "item_count": sum(len(p["questions"]) for p in passages),
        }

    elif section == "listening":
        from gui.api.listening import _load_builtin_script

        # Generate listening items
        items = []
        item_count = 7 if exam == "toefl" else 4  # 3 conv + 4 lec for TOEFL, 4 sections for IELTS

        rows = kb.get_by_type(
            content_type="listening",
            difficulty=cefr,
            exam=exam,
            limit=item_count,
            random_order=True,
        )

        for row in rows:
            import json
            metadata = json.loads(_row_value(row, "metadata_json", "{}") or "{}")
            questions = _parse_questions(metadata.get("questions"))
            script = metadata.get("script", [])
            if not questions or not script:
                continue
            items.append({
                "script": script,
                "questions": questions,
                "duration": metadata.get("duration_seconds", 0),
            })

        while len(items) < item_count:
            dialogue_type = "conversation" if len(items) % 2 == 0 else "monologue"
            builtin = _load_builtin_script(exam, dialogue_type, cefr) or _load_builtin_script("general", dialogue_type, cefr)
            if not builtin:
                break
            items.append({
                "script": builtin.get("script", []),
                "questions": builtin.get("questions", []),
                "duration": max(60, len(" ".join(line.get("text", "") for line in builtin.get("script", [])).split()) * 2),
            })

        return {
            "section": "listening",
            "items": items,
            "item_count": sum(len(item["questions"]) for item in items),
        }

    elif section == "speaking":
        # Generate speaking tasks
        task_count = 4 if exam == "toefl" else 3  # 4 tasks for TOEFL, 3 parts for IELTS

        return {
            "section": "speaking",
            "tasks": [{"task_number": i + 1} for i in range(task_count)],
            "item_count": task_count,
        }

    elif section == "writing":
        # Generate writing tasks
        task_count = 2  # Both TOEFL and IELTS have 2 writing tasks

        return {
            "section": "writing",
            "tasks": [{"task_number": i + 1} for i in range(task_count)],
            "item_count": task_count,
        }

    return {"section": section, "item_count": 0}


def _get_exam_instructions(exam: str) -> str:
    """Get exam-specific instructions."""
    if exam == "toefl":
        return """TOEFL iBT Mock Exam Instructions:

1. This is a timed exam. You must complete each section within the time limit.
2. You cannot return to previous sections once completed.
3. No feedback will be provided during the exam.
4. You will receive a comprehensive score report after completing all sections.
5. Take a 10-minute break after the Listening section.

Good luck!"""
    else:
        return """IELTS Academic Mock Exam Instructions:

1. This is a timed exam. You must complete each section within the time limit.
2. For Listening, you will have 10 minutes at the end to transfer answers.
3. You cannot return to previous sections once completed.
4. No feedback will be provided during the exam.
5. You will receive a comprehensive score report after completing all sections.

Good luck!"""


class SubmitAnswerRequest(BaseModel):
    section_index: int
    answers: list[dict]  # [{"question_id": "1", "answer": "B"}]


class CompleteSectionRequest(BaseModel):
    section_index: int
    answers: Optional[list[dict]] = None
    result: Optional[dict] = None


def _complete_section(session: MockExamSession, req: CompleteSectionRequest) -> dict:
    if req.section_index >= len(session.sections):
        raise HTTPException(400, "Invalid section index")
    if req.section_index != session.current_section:
        raise HTTPException(400, "Section is not the current active section")

    section_id = f"section_{req.section_index}"
    if req.answers:
        session.answers[section_id] = req.answers
    elif section_id not in session.answers:
        session.answers[section_id] = []

    section_duration = max(0, int(time.time() - session.start_time) - sum(session.section_times.values()))
    session.section_times[section_id] = section_duration

    if req.result:
        summary = dict(req.result)
    else:
        summary = {"completed": True}
    if "result_card" not in summary or "improved_point" not in summary or "tomorrow_reason" not in summary:
        recap = build_mock_section_recap(
            section=session.sections[req.section_index]["section"],
            correct=int(summary.get("correct", 0) or 0),
            total=int(summary.get("total", 0) or 0),
            overall=float(summary.get("overall", 0) or 0),
            score_max=float(summary.get("score_max", 0) or 0),
        )
        for key, value in recap.items():
            summary.setdefault(key, value)
    session.completed_sections[req.section_index] = summary

    session.current_section = req.section_index + 1
    if session.current_section >= len(session.sections):
        session.report = _generate_score_report(session)

    return _serialize_session(session)


@router.post("/submit-section/{session_id}")
def submit_section(session_id: str, req: SubmitAnswerRequest):
    """Submit answers for a section (no immediate feedback in mock mode)."""
    session = _mock_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return _complete_section(
        session,
        CompleteSectionRequest(section_index=req.section_index, answers=req.answers),
    )


@router.post("/complete-section/{session_id}")
def complete_section(session_id: str, req: CompleteSectionRequest):
    session = _mock_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return _complete_section(session, req)


def _generate_score_report(session: MockExamSession):
    """Generate comprehensive score report for completed mock exam."""
    kb, srs, user_model, ai, profile = get_components()

    # Calculate scores for each section
    section_scores = []
    total_correct = 0
    total_questions = 0

    for i, section_data in enumerate(session.sections):
        section_id = f"section_{i}"
        answers = session.answers.get(section_id, [])
        summary = session.completed_sections.get(i, {})

        # Calculate section score
        correct = int(summary.get("correct", 0) or 0)
        total = int(summary.get("total", 0) or 0)

        if total == 0 and section_data["section"] == "reading":
            for passage in section_data.get("passages", []):
                for q in passage.get("questions", []):
                    total += 1
                    # Check if answer is correct (simplified)
                    user_answer = next((a["answer"] for a in answers if a.get("question_id") == q.get("id")), None)
                    if user_answer and user_answer == q.get("answer"):
                        correct += 1

        elif total == 0 and section_data["section"] == "listening":
            for item in section_data.get("items", []):
                for q in item.get("questions", []):
                    total += 1
                    user_answer = next((a["answer"] for a in answers if a.get("question_id") == q.get("id")), None)
                    if user_answer and user_answer == q.get("answer"):
                        correct += 1

        accuracy = correct / total if total > 0 else 0

        section_scores.append({
            "section": section_data["section"],
            "correct": correct,
            "total": total,
            "accuracy": round(accuracy * 100, 1),
            "time_taken": session.section_times.get(section_id, 0),
            "time_limit": section_data["time_limit"] * 60,
        })

        total_correct += correct
        total_questions += total

    # Calculate overall score
    overall_accuracy = total_correct / total_questions if total_questions > 0 else 0

    # Map to exam-specific score
    if session.exam == "toefl":
        # TOEFL: 0-30 per section, 0-120 total
        scaled_score = int(overall_accuracy * 120)
        score_label = f"{scaled_score}/120"
    else:
        # IELTS: Band 0-9
        band_score = 4.0 + (overall_accuracy * 5.0)  # Map 0-100% to 4.0-9.0
        score_label = f"Band {band_score:.1f}"

    # Calculate percentile (simplified - would use historical data in production)
    percentile = int(overall_accuracy * 100)
    weak_areas = _identify_weak_areas(section_scores)
    recap = build_mock_exam_recap(
        exam=session.exam,
        total_correct=total_correct,
        total_questions=total_questions,
        weak_areas=weak_areas,
    )

    # Record session
    total_duration = int(time.time() - session.start_time)
    user_model.end_session(
        session_id=session.db_session_id,
        duration_sec=total_duration,
        items_done=total_questions,
        accuracy=overall_accuracy,
        content_json=json.dumps(
            {
                "exam": session.exam,
                "overall_score": score_label,
                "overall_accuracy": round(overall_accuracy * 100, 1),
                "total_correct": total_correct,
                "total_questions": total_questions,
                "section_scores": section_scores,
                "weak_areas": weak_areas,
                **recap,
            },
            ensure_ascii=False,
        ),
    )

    return {
        "exam_complete": True,
        "exam": session.exam,
        "overall_score": score_label,
        "overall_accuracy": round(overall_accuracy * 100, 1),
        "total_correct": total_correct,
        "total_questions": total_questions,
        "percentile": percentile,
        "section_scores": section_scores,
        "total_time": total_duration,
        "weak_areas": weak_areas,
        "recommendations": _generate_exam_recommendations(section_scores, overall_accuracy),
        **recap,
    }


def _identify_weak_areas(section_scores: list[dict]) -> list[str]:
    """Identify weak areas based on section performance."""
    weak_areas = []

    for section in section_scores:
        if section["accuracy"] < 60:
            weak_areas.append(f"{section['section']} (accuracy: {section['accuracy']}%)")

    return weak_areas


def _generate_exam_recommendations(section_scores: list[dict], overall_accuracy: float) -> list[str]:
    """Generate recommendations based on mock exam performance."""
    recommendations = []

    # Overall performance
    if overall_accuracy < 0.6:
        recommendations.append("Consider reviewing fundamental concepts before taking another mock exam")
    elif overall_accuracy < 0.75:
        recommendations.append("Focus on targeted practice for weak areas")
    else:
        recommendations.append("Strong performance! Continue with regular practice to maintain skills")

    # Section-specific
    weakest_section = min(section_scores, key=lambda s: s["accuracy"])
    if weakest_section["accuracy"] < 70:
        recommendations.append(f"Prioritize {weakest_section['section']} practice")

    # Time management
    for section in section_scores:
        if section["time_taken"] > section["time_limit"]:
            recommendations.append(f"Work on time management for {section['section']} section")

    return recommendations


@router.get("/session/{session_id}")
def get_mock_session(session_id: str):
    """Get mock exam session details."""
    session = _mock_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return _serialize_session(session)
