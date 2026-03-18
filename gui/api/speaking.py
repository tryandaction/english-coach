"""Speaking practice API."""
from __future__ import annotations

import json
import random
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/speaking", tags=["speaking"])


_TOEFL_PROMPTS = {
    "independent": {
        "label": "Independent Speaking",
        "prep_seconds": 15,
        "speak_seconds": 45,
        "instructions": "State your position clearly, give reasons, and support them with one or two examples.",
        "prompts": [
            "Do you prefer studying alone or in a group? Give specific reasons and examples.",
            "Should universities require students to take classes outside their major? Explain your view.",
            "Is it better to plan carefully before beginning a project, or start quickly and adjust later?",
            "Do you prefer reading printed books or digital books? Use reasons and examples.",
        ],
    },
    "listen_repeat": {
        "label": "Listen and Repeat",
        "prep_seconds": 5,
        "speak_seconds": 30,
        "instructions": "Listen to each sentence and repeat it as accurately and naturally as possible.",
        "fallback_sentences": [
            {"level": 1, "text": "The seminar begins at nine o'clock.", "difficulty": "easy"},
            {"level": 2, "text": "My professor recommended two articles on climate policy.", "difficulty": "easy"},
            {"level": 3, "text": "The library stays open later during exam week.", "difficulty": "medium"},
            {"level": 4, "text": "Students benefit when feedback is both specific and timely.", "difficulty": "medium"},
            {"level": 5, "text": "Technological innovation often changes how research is conducted.", "difficulty": "hard"},
        ],
    },
    "virtual_interview": {
        "label": "Virtual Interview",
        "prep_seconds": 10,
        "speak_seconds": 45,
        "instructions": "Answer each interview question naturally and keep your response focused and specific.",
        "fallback_questions": [
            {"question": "Tell me about a subject you enjoy studying and why.", "expected_length": "30-45 seconds", "topic": "academic"},
            {"question": "Describe a challenge you faced at school and how you handled it.", "expected_length": "30-45 seconds", "topic": "personal"},
            {"question": "What qualities make someone a good team member?", "expected_length": "20-30 seconds", "topic": "opinion"},
        ],
    },
}

_IELTS_PROMPTS = {
    "part1": {
        "label": "Part 1: Short Interview",
        "prep_seconds": 10,
        "speak_seconds": 45,
        "instructions": "Give direct, natural answers. Add a brief reason or example when possible.",
        "prompts": [
            "Do you prefer studying in the morning or at night? Why?",
            "What kind of books do you enjoy reading?",
            "How often do you use public transport?",
            "Do you think your hometown is a good place for young people?",
        ],
    },
    "part2": {
        "label": "Part 2: Cue Card",
        "prep_seconds": 60,
        "speak_seconds": 120,
        "instructions": "Use the cue points to organize a 1-2 minute response with a clear beginning, middle, and ending.",
        "prompts": [
            "Describe a teacher who helped you a lot.\n- who this person is\n- when you studied with them\n- what they did that was helpful\n- and explain why you still remember this teacher",
            "Describe a place where you like to study.\n- where it is\n- what it looks like\n- what you usually do there\n- and explain why it is a good place for you",
            "Describe a useful skill you learned.\n- what the skill is\n- when you learned it\n- how you learned it\n- and explain why it is useful",
        ],
    },
    "part3": {
        "label": "Part 3: Discussion",
        "prep_seconds": 20,
        "speak_seconds": 90,
        "instructions": "Develop your ideas. Compare options, explain causes, and discuss broader social impact.",
        "prompts": [
            "Why do some students learn more effectively in groups while others prefer to study alone?",
            "How has technology changed the way people communicate in professional settings?",
            "What are the advantages and disadvantages of working from home?",
        ],
    },
}


# ── TOEFL 2026 New Speaking Task Types ───────────────────────────────────────

class ListenRepeatRequest(BaseModel):
    num_sentences: int = 7
    cefr_level: Optional[str] = None


class VirtualInterviewRequest(BaseModel):
    num_questions: int = 5
    cefr_level: Optional[str] = None


class SpeakingSubmitRequest(BaseModel):
    transcript: str
    task_type: str
    exam: Optional[str] = None
    prompt: Optional[str] = None
    sample_response: Optional[str] = None


@router.get("/prompt")
def get_speaking_prompt(exam: Optional[str] = None, task_type: Optional[str] = None):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    target = (exam or profile.target_exam or "toefl").lower()
    task = (task_type or ("independent" if target == "toefl" else "part1")).lower()
    cefr = profile.cefr_level or "B2"

    if target == "toefl":
        if task == "listen_repeat":
            if ai:
                try:
                    result = ai.generate_listen_repeat_task(cefr, num_sentences=5)
                except Exception:
                    result = {
                        "task": "Listen and repeat each sentence exactly as you hear it.",
                        "type": "listen_repeat",
                        "sentences": _TOEFL_PROMPTS["listen_repeat"]["fallback_sentences"],
                        "scoring_criteria": "Pronunciation accuracy, intonation, fluency",
                    }
            else:
                result = {
                    "task": "Listen and repeat each sentence exactly as you hear it.",
                    "type": "listen_repeat",
                    "sentences": _TOEFL_PROMPTS["listen_repeat"]["fallback_sentences"],
                    "scoring_criteria": "Pronunciation accuracy, intonation, fluency",
                }
            return {
                "exam": "toefl",
                "task_type": "listen_repeat",
                "task_label": _TOEFL_PROMPTS["listen_repeat"]["label"],
                "prep_seconds": _TOEFL_PROMPTS["listen_repeat"]["prep_seconds"],
                "speak_seconds": _TOEFL_PROMPTS["listen_repeat"]["speak_seconds"],
                "instructions": _TOEFL_PROMPTS["listen_repeat"]["instructions"],
                "prompt": result.get("task", ""),
                "sentences": result.get("sentences", []),
                "scoring_criteria": result.get("scoring_criteria", ""),
            }

        if task == "virtual_interview":
            if ai:
                try:
                    result = ai.generate_virtual_interview_task(cefr, num_questions=4)
                except Exception:
                    result = {
                        "task": "Answer the interviewer's questions naturally.",
                        "type": "virtual_interview",
                        "questions": _TOEFL_PROMPTS["virtual_interview"]["fallback_questions"],
                        "scoring_criteria": "Fluency, naturalness, grammatical accuracy",
                    }
            else:
                result = {
                    "task": "Answer the interviewer's questions naturally.",
                    "type": "virtual_interview",
                    "questions": _TOEFL_PROMPTS["virtual_interview"]["fallback_questions"],
                    "scoring_criteria": "Fluency, naturalness, grammatical accuracy",
                }
            return {
                "exam": "toefl",
                "task_type": "virtual_interview",
                "task_label": _TOEFL_PROMPTS["virtual_interview"]["label"],
                "prep_seconds": _TOEFL_PROMPTS["virtual_interview"]["prep_seconds"],
                "speak_seconds": _TOEFL_PROMPTS["virtual_interview"]["speak_seconds"],
                "instructions": _TOEFL_PROMPTS["virtual_interview"]["instructions"],
                "prompt": result.get("task", ""),
                "questions": result.get("questions", []),
                "scoring_criteria": result.get("scoring_criteria", ""),
            }

        prompt_def = _TOEFL_PROMPTS["independent"]
        return {
            "exam": "toefl",
            "task_type": "independent",
            "task_label": prompt_def["label"],
            "prep_seconds": prompt_def["prep_seconds"],
            "speak_seconds": prompt_def["speak_seconds"],
            "instructions": prompt_def["instructions"],
            "prompt": random.choice(prompt_def["prompts"]),
            "scoring_criteria": "Delivery, language use, topic development",
        }

    if target == "ielts":
        prompt_def = _IELTS_PROMPTS.get(task, _IELTS_PROMPTS["part1"])
        return {
            "exam": "ielts",
            "task_type": task if task in _IELTS_PROMPTS else "part1",
            "task_label": prompt_def["label"],
            "prep_seconds": prompt_def["prep_seconds"],
            "speak_seconds": prompt_def["speak_seconds"],
            "instructions": prompt_def["instructions"],
            "prompt": random.choice(prompt_def["prompts"]),
            "scoring_criteria": "Fluency, coherence, vocabulary range, grammar control",
        }

    raise HTTPException(400, f"Unsupported speaking exam: {target}")


@router.post("/toefl2026/listen-repeat")
def generate_listen_repeat(req: ListenRepeatRequest):
    """Generate TOEFL 2026 'Listen & Repeat' speaking task."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    try:
        result = ai.generate_listen_repeat_task(cefr, req.num_sentences)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl2026/virtual-interview")
def generate_virtual_interview(req: VirtualInterviewRequest):
    """Generate TOEFL 2026 'Virtual Interview' speaking task."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    try:
        result = ai.generate_virtual_interview_task(cefr, req.num_questions)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/submit")
def submit_speaking(req: SpeakingSubmitRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    transcript = (req.transcript or "").strip()
    if not transcript:
        raise HTTPException(400, "Transcript is required")

    exam = (req.exam or profile.target_exam or "toefl").lower()
    task_type = (req.task_type or "independent").lower()

    try:
        result = ai.evaluate_speaking(
            transcript=transcript,
            task_type=f"{exam}_{task_type}",
            cefr_level=profile.cefr_level or "B2",
            sample_response=req.sample_response,
        )
    except Exception as e:
        raise HTTPException(500, f"Evaluation failed: {e}")

    overall = float(result.get("overall", 0) or 0)
    score_ratio = max(0.0, min(1.0, overall / 4.0))
    db_sid = user_model.start_session(profile.user_id, "speaking")
    user_model.record_answer(profile.user_id, "speaking_structure", score_ratio >= 0.6)
    user_model.record_answer(profile.user_id, "speaking_vocabulary", score_ratio >= 0.6)
    user_model.end_session(
        db_sid,
        0,
        1,
        score_ratio,
        content_json=json.dumps({
            "exam": exam,
            "task_type": task_type,
            "prompt": req.prompt or "",
            "overall": overall,
        }),
    )

    return {
        "exam": exam,
        "task_type": task_type,
        "score_max": 4,
        "score_label": "/ 4",
        **result,
    }
