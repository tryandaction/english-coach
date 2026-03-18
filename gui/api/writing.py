"""Writing feedback API with SSE streaming."""
from __future__ import annotations

import json
import random
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/writing", tags=["writing"])

# task_type → list of prompts
_PROMPTS: dict[str, dict[str, list[str]]] = {
    "toefl": {
        "independent": [
            "Do you agree or disagree: Universities should require all students to take courses outside their major field of study?",
            "Some people believe that the best way to learn about life is by listening to the advice of family and friends. Others believe that experience is the best teacher. Which do you prefer and why?",
            "A company is going to give some money to help the community. Should it support the arts, protect the environment, or help the poor?",
            "Do you agree or disagree: It is more important to have a good relationship with your coworkers than to earn a high salary?",
            "Some people think that children should begin their formal education at a very early age. Others believe that children should not begin school until age seven. Which view do you agree with?",
            "Do you agree or disagree: The most important characteristic of a successful politician is the ability to compromise?",
            "Some people prefer to work for a large company. Others prefer to work for a small company. Which would you prefer?",
            "Do you agree or disagree: Advertising has had a mostly negative effect on society?",
        ],
        "integrated": [
            "Summarize the points made in the lecture, being sure to explain how they cast doubt on specific points made in the reading passage.",
            "The professor discusses the challenges of implementing renewable energy. Summarize the key points and explain how they relate to the reading.",
            "Explain how the examples from the lecture support or challenge the claims in the reading about urban planning.",
        ],
    },
    "ielts": {
        "task2": [
            "Some people think that the government should provide free university education for all citizens. To what extent do you agree or disagree?",
            "In many countries, the number of people choosing to live alone is increasing. What are the reasons for this? Is it a positive or negative development?",
            "Technology is making communication easier in today's world, but at the expense of personal contact. How far do you agree?",
            "Some people believe that it is best to accept a bad situation, such as an unsatisfactory job or shortage of money. Others argue that it is better to try to improve such situations. Discuss both views and give your opinion.",
            "Many people believe that social networking sites have had a huge negative impact on both individuals and society. To what extent do you agree?",
            "Some people think that a sense of competition in children should be encouraged. Others believe that children who are taught to cooperate rather than compete become more useful adults. Discuss both views and give your own opinion.",
            "The increasing use of technology in the workplace has changed the way people work. Some believe this is a positive development, while others disagree. Discuss both views and give your opinion.",
            "In some countries, young people are encouraged to work or travel for a year between finishing high school and starting university. Discuss the advantages and disadvantages.",
        ],
        "task1": [
            "The graph below shows the percentage of households with internet access in three countries between 2000 and 2020. Summarize the information by selecting and reporting the main features, and make comparisons where relevant.",
            "The bar chart below shows the number of students enrolled in different types of higher education institutions in 2015. Summarize the information and make comparisons where relevant.",
            "The pie charts below show the main reasons why people moved to and from the UK in 2019. Summarize the information by selecting and reporting the main features.",
            "The line graph below shows changes in the amount of fish caught in four countries between 1980 and 2010. Summarize the information and make comparisons where relevant.",
        ],
    },
    "gre": {
        "issue": [
            "The best way to teach is to praise positive actions and ignore negative ones.",
            "Governments should place few, if any, restrictions on scientific research and development.",
            "In any field of inquiry, the beginner is more likely than the expert to make important contributions.",
            "The well-being of a society is enhanced when many of its people question authority.",
            "Educational institutions have a responsibility to dissuade students from pursuing fields of study in which they are unlikely to succeed.",
            "Claim: Governments must ensure that their major cities receive the financial support they need in order to thrive. Reason: It is primarily in cities that a nation's cultural traditions are preserved and generated.",
            "Some people believe that competition for high grades motivates students to excel in the classroom. Others believe that such competition seriously limits the quality of real learning.",
            "The most effective way to understand contemporary culture is to analyze the trends of its youth.",
        ],
        "argument": [
            "The following appeared in a memo from the director of a large group of hospitals: 'In a recent study, those who reported eating three or more servings of fresh fruits and vegetables daily were significantly less likely to have heart disease than those who ate little or no fresh produce. Therefore, in order to reduce the incidence of heart disease among our patients, we should provide fresh fruits and vegetables in our hospital cafeterias.' Write a response in which you examine the stated and/or unstated assumptions of the argument.",
            "The following appeared in a letter to the editor of a local newspaper: 'The Grandview Recreational Center, which has been in operation for ten years, should be replaced by a new facility. The current center is outdated and its equipment is in poor condition. Moreover, the center has seen a 20% decline in membership over the past two years.' Write a response in which you discuss what questions would need to be answered in order to decide whether the recommendation is likely to have the predicted result.",
            "The following is a recommendation from the personnel director of Acme Publishing Company: 'Acme should immediately hire ten new salespeople. Our competitor, Consolidated Book Publishers, recently hired fifteen new salespeople and has seen a 10% increase in sales.' Write a response in which you examine the stated and/or unstated assumptions of the argument.",
        ],
    },
    "cet": {
        "essay": [
            "Directions: For this part, you are allowed 30 minutes to write an essay on the importance of reading in the digital age. You should write at least 120 words but no more than 180 words.",
            "Directions: For this part, you are allowed 30 minutes to write an essay commenting on the saying 'Failure is the mother of success.' You should write at least 120 words but no more than 180 words.",
            "Directions: For this part, you are allowed 30 minutes to write an essay on the topic of online education. You should write at least 120 words but no more than 180 words.",
            "Directions: For this part, you are allowed 30 minutes to write an essay discussing the advantages and disadvantages of living in a big city. You should write at least 120 words but no more than 180 words.",
            "Directions: For this part, you are allowed 30 minutes to write an essay on the role of social media in modern communication. You should write at least 120 words but no more than 180 words.",
            "Directions: For this part, you are allowed 30 minutes to write an essay on the importance of physical exercise for college students. You should write at least 120 words but no more than 180 words.",
        ],
        "translation": [
            "Directions: For this part, you are allowed 30 minutes to translate a passage from Chinese into English. 中国的高铁网络是世界上最大的，连接了数百个城市，极大地促进了经济发展和人员流动。",
            "Directions: Translate the following passage into English. 随着人工智能技术的快速发展，越来越多的行业开始采用自动化系统来提高生产效率。",
            "Directions: Translate the following passage into English. 中国传统节日如春节、中秋节不仅是家庭团聚的时刻，也是传承文化遗产的重要方式。",
        ],
    },
    "general": {
        "essay": [
            "Describe a challenge you have overcome and what you learned from it.",
            "What is the most important invention of the last 100 years? Explain your choice.",
            "Should social media platforms be responsible for the content users post?",
            "Do you think artificial intelligence will have a positive or negative impact on employment? Explain your view.",
            "Some people argue that learning a foreign language is essential in today's world. Do you agree?",
            "Describe a person who has had a significant influence on your life and explain why.",
        ],
    },
}

# Scoring scales per exam
_SCORE_SCALES = {
    "toefl":   {"max": 5,  "label": "/ 5"},
    "ielts":   {"max": 9,  "label": "Band"},
    "gre":     {"max": 6,  "label": "/ 6"},
    "cet":     {"max": 15, "label": "/ 15"},
    "general": {"max": 5,  "label": "/ 5"},
}

# Word count targets per exam+task
_WORD_TARGETS = {
    "toefl":   {"independent": 300, "integrated": 150, "default": 300},
    "ielts":   {"task2": 250, "task1": 150, "default": 250},
    "gre":     {"issue": 400, "argument": 400, "default": 400},
    "cet":     {"essay": 120, "translation": 80, "default": 120},
    "general": {"essay": 200, "default": 200},
}

# Task type labels per exam
_TASK_TYPES = {
    "toefl":   [("independent", "Independent (Task 2)"), ("integrated", "Integrated (Task 1)"), ("build_sentence", "Build a Sentence (NEW 2026)"), ("write_email", "Write an Email (NEW 2026)"), ("academic_discussion", "Academic Discussion (NEW 2026)")],
    "ielts":   [("task2", "Task 2: Essay"), ("task1", "Task 1: Report")],
    "gre":     [("issue", "Issue Essay"), ("argument", "Argument Essay")],
    "cet":     [("essay", "作文 Essay"), ("translation", "翻译 Translation")],
    "general": [("essay", "Essay")],
}


@router.get("/prompt")
def get_prompt(exam: Optional[str] = None, task_type: Optional[str] = None):
    kb, srs, user_model, ai, profile = get_components()
    target = exam or (profile.target_exam if profile else "general") or "general"
    exam_prompts = _PROMPTS.get(target, _PROMPTS["general"])

    # Pick task type
    if task_type and task_type in exam_prompts:
        tt = task_type
    else:
        tt = list(exam_prompts.keys())[0]

    prompts = exam_prompts[tt]
    word_target = _WORD_TARGETS.get(target, {}).get(tt) or _WORD_TARGETS.get(target, {}).get("default", 200)
    scale = _SCORE_SCALES.get(target, _SCORE_SCALES["general"])
    task_types = _TASK_TYPES.get(target, _TASK_TYPES["general"])

    # Try to get an AI-generated prompt from warehouse first.
    # Important: when task_type is explicitly requested (e.g., tab switching),
    # do not use warehouse prompts because they are not task-specific.
    ai_prompt = None
    use_ai_prompt = ai and not task_type
    if use_ai_prompt:
        try:
            rows = kb.get_by_type(
                content_type="writing",
                difficulty=profile.cefr_level if profile else "B1",
                exam=target,
                limit=5,
                random_order=True,
            )
            if rows:
                ai_prompt = rows[0]["text"]
        except Exception:
            pass

    chosen_prompt = ai_prompt if ai_prompt else random.choice(prompts)

    return {
        "prompt": chosen_prompt,
        "exam": target,
        "task_type": tt,
        "task_types": task_types,
        "word_target": word_target,
        "score_max": scale["max"],
        "score_label": scale["label"],
    }


@router.get("/pool")
def get_prompt_pool(exam: Optional[str] = None, task_type: Optional[str] = None, n: int = 3):
    kb, srs, user_model, ai, profile = get_components()
    target = exam or (profile.target_exam if profile else "general") or "general"
    exam_prompts = _PROMPTS.get(target, _PROMPTS["general"])
    tt = task_type if task_type and task_type in exam_prompts else list(exam_prompts.keys())[0]
    prompts = exam_prompts[tt]
    word_target = _WORD_TARGETS.get(target, {}).get(tt) or _WORD_TARGETS.get(target, {}).get("default", 200)
    scale = _SCORE_SCALES.get(target, _SCORE_SCALES["general"])
    task_types = _TASK_TYPES.get(target, _TASK_TYPES["general"])
    chosen = random.sample(prompts, min(n, len(prompts)))
    return {"prompts": [{"prompt": p, "exam": target, "task_type": tt,
                         "task_types": task_types, "word_target": word_target,
                         "score_max": scale["max"], "score_label": scale["label"]}
                        for p in chosen]}


class WriteRequest(BaseModel):
    essay: str
    prompt: str
    exam: Optional[str] = None
    task_type: Optional[str] = None


@router.post("/submit")
def submit_essay(req: WriteRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "No API key configured")
    if not profile:
        raise HTTPException(400, "No profile")

    exam = req.exam or profile.target_exam or "general"
    scale = _SCORE_SCALES.get(exam, _SCORE_SCALES["general"])

    def generate():
        try:
            result = ai.evaluate_writing(
                essay=req.essay,
                prompt=req.prompt,
                cefr_level=profile.cefr_level,
                exam=exam,
            )
            yield f"data: {json.dumps({'type': 'scores', 'data': result.get('scores', {})})}\n\n"
            yield f"data: {json.dumps({'type': 'overall', 'data': result.get('overall', 0), 'score_max': scale['max'], 'score_label': scale['label']})}\n\n"

            for s in result.get("strengths", []):
                yield f"data: {json.dumps({'type': 'strength', 'data': s})}\n\n"

            for item in result.get("improvements", []):
                yield f"data: {json.dumps({'type': 'improvement', 'data': item})}\n\n"

            if result.get("revised_intro"):
                yield f"data: {json.dumps({'type': 'revised_intro', 'data': result['revised_intro']})}\n\n"

            scores = result.get("scores", {})
            max_val = scale["max"]
            for skill_key, api_key in [
                ("writing_coherence", "coherence"),
                ("writing_grammar", "grammar_accuracy"),
                ("writing_vocabulary", "lexical_resource"),
            ]:
                val = scores.get(api_key, 0)
                user_model.record_answer(profile.user_id, skill_key, val >= max_val * 0.6)

            db_sid = user_model.start_session(profile.user_id, "writing")
            user_model.end_session(db_sid, 0, 1, result.get("overall", 0) / max_val)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── TOEFL 2026 New Writing Task Types ────────────────────────────────────────

class BuildSentenceRequest(BaseModel):
    num_items: int = 5
    cefr_level: Optional[str] = None


class WriteEmailRequest(BaseModel):
    cefr_level: Optional[str] = None


class AcademicDiscussionRequest(BaseModel):
    cefr_level: Optional[str] = None


@router.post("/toefl2026/build-sentence")
def generate_build_sentence(req: BuildSentenceRequest):
    """Generate TOEFL 2026 'Build a Sentence' writing task."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    try:
        result = ai.generate_build_sentence_task(cefr, req.num_items)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl2026/write-email")
def generate_write_email(req: WriteEmailRequest):
    """Generate TOEFL 2026 'Write an Email' writing task."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    try:
        result = ai.generate_write_email_task(cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")


@router.post("/toefl2026/academic-discussion")
def generate_academic_discussion(req: AcademicDiscussionRequest):
    """Generate TOEFL 2026 'Academic Discussion' writing task."""
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "AI client not configured")
    if not profile:
        raise HTTPException(400, "No profile")

    cefr = req.cefr_level or profile.cefr_level or "B2"

    try:
        result = ai.generate_academic_discussion_task(cefr)
        return result
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")

