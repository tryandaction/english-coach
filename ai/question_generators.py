"""
Question generators for TOEFL 2026 new question types.
Handles: Complete the Words, Read in Daily Life, Listen & Repeat, Virtual Interview,
Build a Sentence, Write an Email, Academic Discussion.
"""

from __future__ import annotations
import json
import random
from typing import Optional


def generate_complete_words_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL 2026 "Complete the Words" question.
    Selects 3-5 words from the passage and removes 2-4 letters from each.

    Returns: {
        "question": "Complete the words by filling in the missing letters.",
        "type": "complete_words",
        "items": [
            {"incomplete": "env_r_nment", "complete": "environment", "context": "...sentence from passage..."},
            ...
        ],
        "answer": ["environment", "scientific", "research"],
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Complete the Words' question for TOEFL 2026 format:\n"
        f"1. Select 3-5 words from the passage (6-12 letters long, appropriate for {cefr_level})\n"
        f"2. For each word, remove 2-4 letters (replace with underscores)\n"
        f"3. Provide the context sentence where the word appears\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Complete the words by filling in the missing letters.",'
        f'"type":"complete_words",'
        f'"items":[{{"incomplete":"env_r_nment","complete":"environment","context":"...sentence..."}}],'
        f'"answer":["environment","scientific","research"],'
        f'"explanation":"These words test vocabulary recognition and spelling."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=600)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_daily_life_question(
    cefr_level: str,
    ai_client,
    text_type: str = "email",
) -> dict:
    """
    Generate a TOEFL 2026 "Read in Daily Life" question.
    Creates practical texts: emails, notices, menus, schedules, advertisements.

    Args:
        text_type: "email", "notice", "menu", "schedule", "advertisement"

    Returns: {
        "question": "Read the email and answer the questions.",
        "type": "daily_life",
        "text_type": "email",
        "text": "...email content...",
        "questions": [
            {"question": "What is the main purpose?", "options": [...], "answer": "B"},
            ...
        ],
        "explanation": "..."
    }
    """
    text_types_examples = {
        "email": "a work email about a meeting change or project update",
        "notice": "a community notice about an event or policy change",
        "menu": "a restaurant menu with descriptions and prices",
        "schedule": "a class schedule or event timetable",
        "advertisement": "a product or service advertisement with details",
    }

    example = text_types_examples.get(text_type, text_types_examples["email"])

    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"Generate a 'Read in Daily Life' question for TOEFL 2026 format:\n"
        f"1. Create {example} (100-150 words)\n"
        f"2. Generate 2-3 practical comprehension questions (4 options each)\n"
        f"3. Questions should test: main purpose, specific details, implied meaning\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Read the {text_type} and answer the questions.",'
        f'"type":"daily_life",'
        f'"text_type":"{text_type}",'
        f'"text":"...{text_type} content...",'
        f'"questions":[{{"question":"What is the main purpose?","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"B","explanation":"..."}}],'
        f'"explanation":"This tests practical reading comprehension."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=800)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_listen_repeat_task(
    cefr_level: str,
    ai_client,
    num_sentences: int = 7,
) -> dict:
    """
    Generate a TOEFL 2026 "Listen & Repeat" speaking task.
    Creates 7 progressively difficult sentences for pronunciation testing.

    Returns: {
        "task": "Listen and repeat each sentence exactly as you hear it.",
        "type": "listen_repeat",
        "sentences": [
            {"level": 1, "text": "Hello, how are you?", "difficulty": "easy"},
            {"level": 2, "text": "I'm studying English at the university.", "difficulty": "easy"},
            ...
            {"level": 7, "text": "The phenomenon demonstrates...", "difficulty": "hard"}
        ],
        "scoring_criteria": "Pronunciation, intonation, fluency"
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"Generate a 'Listen & Repeat' speaking task for TOEFL 2026 format:\n"
        f"Create {num_sentences} sentences with progressive difficulty:\n"
        f"- Levels 1-2: Simple everyday phrases (5-8 words)\n"
        f"- Levels 3-4: Common academic sentences (8-12 words)\n"
        f"- Levels 5-6: Complex academic sentences (12-15 words)\n"
        f"- Level 7: Advanced academic sentence with challenging pronunciation (15-20 words)\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"task":"Listen and repeat each sentence exactly as you hear it.",'
        f'"type":"listen_repeat",'
        f'"sentences":[{{"level":1,"text":"Hello, how are you?","difficulty":"easy"}}],'
        f'"scoring_criteria":"Pronunciation accuracy, intonation, fluency, stress patterns"}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=700)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse task", "raw": text}


def generate_virtual_interview_task(
    cefr_level: str,
    ai_client,
    num_questions: int = 5,
) -> dict:
    """
    Generate a TOEFL 2026 "Virtual Interview" speaking task.
    Creates conversational questions testing fluency and natural responses.

    Returns: {
        "task": "Answer the interviewer's questions naturally.",
        "type": "virtual_interview",
        "questions": [
            {"question": "Tell me about yourself.", "expected_length": "30-45 seconds"},
            {"question": "What are your hobbies?", "expected_length": "20-30 seconds"},
            ...
        ],
        "scoring_criteria": "Fluency, naturalness, content relevance"
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"Generate a 'Virtual Interview' speaking task for TOEFL 2026 format:\n"
        f"Create {num_questions} conversational interview questions:\n"
        f"- Mix personal, academic, and opinion questions\n"
        f"- Questions should feel natural and conversational\n"
        f"- Appropriate for {cefr_level} level\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"task":"Answer the interviewer\'s questions naturally.",'
        f'"type":"virtual_interview",'
        f'"questions":[{{"question":"Tell me about yourself.","expected_length":"30-45 seconds","topic":"personal"}}],'
        f'"scoring_criteria":"Fluency, naturalness, grammatical accuracy, vocabulary range, content relevance"}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=600)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse task", "raw": text}


def generate_build_sentence_task(
    cefr_level: str,
    ai_client,
    num_items: int = 5,
) -> dict:
    """
    Generate a TOEFL 2026 "Build a Sentence" writing task.
    Provides scrambled words that must be arranged into grammatically correct sentences.

    Returns: {
        "task": "Arrange the words to form grammatically correct sentences.",
        "type": "build_sentence",
        "items": [
            {
                "words": ["the", "students", "library", "in", "studying", "are", "the"],
                "correct": "The students are studying in the library.",
                "explanation": "Present continuous tense with proper article usage."
            },
            ...
        ]
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"Generate a 'Build a Sentence' writing task for TOEFL 2026 format:\n"
        f"Create {num_items} sentence-building exercises:\n"
        f"- Each has 6-12 scrambled words\n"
        f"- Test grammar: tenses, articles, word order, prepositions\n"
        f"- Appropriate for {cefr_level} level\n"
        f"- Include the correct sentence and brief explanation\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"task":"Arrange the words to form grammatically correct sentences.",'
        f'"type":"build_sentence",'
        f'"items":[{{"words":["the","students","library","in","studying","are","the"],"correct":"The students are studying in the library.","explanation":"Present continuous tense."}}]}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=800)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse task", "raw": text}


def generate_write_email_task(
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL 2026 "Write an Email" writing task.
    Creates a practical scenario requiring an email response.

    Returns: {
        "task": "Write an email responding to the situation described.",
        "type": "write_email",
        "scenario": "Your professor has postponed tomorrow's exam...",
        "requirements": [
            "Acknowledge the change",
            "Ask about the new date",
            "Request study materials"
        ],
        "word_limit": "80-100 words",
        "scoring_criteria": "Task completion, organization, language accuracy"
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"Generate a 'Write an Email' writing task for TOEFL 2026 format:\n"
        f"1. Create a realistic scenario (academic or professional)\n"
        f"2. List 3 specific requirements the email must address\n"
        f"3. Set word limit: 80-100 words\n"
        f"4. Appropriate for {cefr_level} level\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"task":"Write an email responding to the situation described.",'
        f'"type":"write_email",'
        f'"scenario":"Your professor has postponed tomorrow\'s exam due to a scheduling conflict. Write an email to your professor.",'
        f'"requirements":["Acknowledge the change","Ask about the new date","Request study materials"],'
        f'"word_limit":"80-100 words",'
        f'"scoring_criteria":"Task completion, organization, tone appropriateness, language accuracy"}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=500)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse task", "raw": text}


def generate_academic_discussion_task(
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL 2026 "Academic Discussion" writing task.
    Creates a forum-style discussion with professor question and student responses.

    Returns: {
        "task": "Read the discussion and write a response contributing your ideas.",
        "type": "academic_discussion",
        "professor_question": "What are the main challenges facing renewable energy adoption?",
        "student_responses": [
            {"name": "Student A", "response": "I think cost is the biggest barrier..."},
            {"name": "Student B", "response": "Infrastructure limitations are critical..."}
        ],
        "requirements": [
            "State your position",
            "Provide specific examples",
            "Respond to at least one other student's point"
        ],
        "word_limit": "100-120 words",
        "scoring_criteria": "Contribution quality, idea development, language use"
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL 2026.\n\n"
        f"Generate an 'Academic Discussion' writing task for TOEFL 2026 format:\n"
        f"1. Create a professor's discussion question (academic topic)\n"
        f"2. Write 2 student responses with different perspectives (30-40 words each)\n"
        f"3. List requirements for the test-taker's response\n"
        f"4. Word limit: 100-120 words\n"
        f"5. Appropriate for {cefr_level} level\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"task":"Read the discussion and write a response contributing your ideas.",'
        f'"type":"academic_discussion",'
        f'"professor_question":"What are the main challenges facing renewable energy adoption?",'
        f'"student_responses":[{{"name":"Student A","response":"I think cost is the biggest barrier..."}}],'
        f'"requirements":["State your position","Provide specific examples","Respond to at least one other student\'s point"],'
        f'"word_limit":"100-120 words",'
        f'"scoring_criteria":"Contribution quality, idea development, coherence, language accuracy"}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=900)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse task", "raw": text}
