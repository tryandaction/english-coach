"""
Question type distribution control for professional reading practice.

Provides functions to generate questions with precise type distribution
matching TOEFL/IELTS standards.
"""

from __future__ import annotations
import json
from typing import Optional


def generate_questions_with_distribution(
    passage: str,
    question_types: list[str],
    distribution: dict[str, int],
    difficulty: int,
    exam: str,
    cefr_level: str,
    ai_client,
) -> list[dict]:
    """
    Generate questions with precise type distribution control.

    Args:
        passage: The reading passage text
        question_types: List of question types to generate
        distribution: Dict mapping question type to count, e.g. {"factual": 3, "inference": 2}
        difficulty: Difficulty score 1-10
        exam: "toefl" or "ielts"
        cefr_level: CEFR level (A1-C2)
        ai_client: AI client instance

    Returns:
        List of question dicts with specified distribution
    """
    from ai.reading_question_generators import (
        generate_negative_factual_question,
        generate_rhetorical_purpose_question,
        generate_reference_question,
        generate_sentence_simplification_question,
        generate_insert_text_question,
        generate_prose_summary_question,
        generate_fill_table_question,
        generate_ielts_tfng_question,
        generate_ielts_matching_headings,
        generate_ielts_completion_question,
        generate_ielts_matching_question,
        generate_ielts_short_answer,
        generate_ielts_diagram_label,
    )

    questions = []

    # Map question types to generator functions
    toefl_generators = {
        "factual": lambda: generate_factual_question(passage, cefr_level, ai_client),
        "inference": lambda: generate_inference_question(passage, cefr_level, ai_client),
        "vocabulary": lambda: generate_vocabulary_question(passage, cefr_level, ai_client),
        "negative_factual": lambda: generate_negative_factual_question(passage, cefr_level, ai_client),
        "rhetorical_purpose": lambda: generate_rhetorical_purpose_question(passage, cefr_level, ai_client),
        "reference": lambda: generate_reference_question(passage, cefr_level, ai_client),
        "sentence_simplification": lambda: generate_sentence_simplification_question(passage, cefr_level, ai_client),
        "insert_text": lambda: generate_insert_text_question(passage, cefr_level, ai_client),
        "prose_summary": lambda: generate_prose_summary_question(passage, cefr_level, ai_client),
        "fill_table": lambda: generate_fill_table_question(passage, cefr_level, ai_client),
    }

    ielts_generators = {
        "tfng": lambda: generate_ielts_tfng_question(passage, cefr_level, ai_client),
        "matching_headings": lambda: generate_ielts_matching_headings(passage, cefr_level, ai_client),
        "summary_completion": lambda: generate_ielts_completion_question(passage, "summary", cefr_level, ai_client),
        "note_completion": lambda: generate_ielts_completion_question(passage, "note", cefr_level, ai_client),
        "table_completion": lambda: generate_ielts_completion_question(passage, "table", cefr_level, ai_client),
        "matching_information": lambda: generate_ielts_matching_question(passage, "information", cefr_level, ai_client),
        "matching_features": lambda: generate_ielts_matching_question(passage, "features", cefr_level, ai_client),
        "sentence_endings": lambda: generate_ielts_matching_question(passage, "sentence_endings", cefr_level, ai_client),
        "short_answer": lambda: generate_ielts_short_answer(passage, cefr_level, ai_client),
        "diagram_label": lambda: generate_ielts_diagram_label(passage, cefr_level, ai_client),
    }

    generators = toefl_generators if exam == "toefl" else ielts_generators

    # Generate questions according to distribution
    for q_type, count in distribution.items():
        if q_type not in generators:
            print(f"Warning: Unknown question type '{q_type}' for {exam}")
            continue

        for i in range(count):
            try:
                question = generators[q_type]()
                if question and "error" not in question:
                    questions.append(question)
                else:
                    print(f"Warning: Failed to generate {q_type} question (attempt {i+1}/{count})")
            except Exception as e:
                print(f"Error generating {q_type} question: {e}")

    return questions


def generate_factual_question(passage: str, cefr_level: str, ai_client) -> dict:
    """Generate a basic factual information question."""
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Factual Information' question:\n"
        f"1. Ask about information directly stated in the passage\n"
        f"2. Provide 4 options (A-D)\n"
        f"3. One correct answer, three plausible distractors\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"According to the passage, what is...?",'
        f'"type":"factual",'
        f'"options":["A. ...","B. ...","C. ...","D. ..."],'
        f'"answer":"B",'
        f'"explanation":"The passage states in paragraph X that..."}}'
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


def generate_inference_question(passage: str, cefr_level: str, ai_client) -> dict:
    """Generate an inference question."""
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate an 'Inference' question:\n"
        f"1. Ask about something implied but not directly stated\n"
        f"2. Require logical deduction from passage information\n"
        f"3. Provide 4 options (A-D)\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"What can be inferred about...?",'
        f'"type":"inference",'
        f'"options":["A. ...","B. ...","C. ...","D. ..."],'
        f'"answer":"C",'
        f'"explanation":"The passage implies this by stating... which suggests..."}}'
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


def generate_vocabulary_question(passage: str, cefr_level: str, ai_client) -> dict:
    """Generate a vocabulary in context question."""
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Vocabulary' question:\n"
        f"1. Select a word from the passage\n"
        f"2. Ask for its meaning in context\n"
        f"3. Provide 4 synonym options (A-D)\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"The word \'X\' in paragraph Y is closest in meaning to:",'
        f'"type":"vocabulary",'
        f'"word":"X",'
        f'"context":"...sentence containing the word...",'
        f'"options":["A. synonym1","B. correct synonym","C. synonym3","D. synonym4"],'
        f'"answer":"B",'
        f'"explanation":"In this context, X means..."}}'
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


# Standard TOEFL question distribution (10 questions per passage)
TOEFL_STANDARD_DISTRIBUTION = {
    "factual": 3,
    "inference": 2,
    "vocabulary": 2,
    "rhetorical_purpose": 1,
    "negative_factual": 1,
    "reference": 1,
}

# Standard IELTS question distribution (13-14 questions per passage)
IELTS_STANDARD_DISTRIBUTION = {
    "tfng": 4,
    "matching_headings": 4,
    "summary_completion": 3,
    "matching_information": 2,
}
