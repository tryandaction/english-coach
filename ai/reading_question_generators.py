"""
Additional TOEFL Reading question generators for remaining 7 types.
Handles: Negative Factual, Rhetorical Purpose, Reference, Sentence Simplification,
Insert Text, Prose Summary, Fill in a Table.
"""

from __future__ import annotations
import json
from typing import Optional


def generate_negative_factual_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Negative Factual Information" question.
    Asks which statement is NOT true or NOT mentioned according to the passage.

    Returns: {
        "question": "According to the passage, which of the following is NOT true about X?",
        "type": "negative_factual",
        "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
        "answer": "C",
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Negative Factual Information' question for TOEFL format:\n"
        f"1. Ask which statement is NOT true or NOT mentioned in the passage\n"
        f"2. Three options should be true/mentioned, one should be false/not mentioned\n"
        f"3. The false option should be plausible but clearly contradicted or absent\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"According to the passage, which of the following is NOT true about X?",'
        f'"type":"negative_factual",'
        f'"options":["A. ...","B. ...","C. ...","D. ..."],'
        f'"answer":"C",'
        f'"explanation":"Option C is not mentioned/contradicted in the passage."}}'
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


def generate_rhetorical_purpose_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Rhetorical Purpose" question.
    Asks why the author mentions a specific detail or example.

    Returns: {
        "question": "Why does the author mention X in paragraph Y?",
        "type": "rhetorical_purpose",
        "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
        "answer": "B",
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Rhetorical Purpose' question for TOEFL format:\n"
        f"1. Identify a specific detail, example, or fact mentioned in the passage\n"
        f"2. Ask why the author mentions it (to illustrate, to contrast, to support, etc.)\n"
        f"3. Options should reflect different rhetorical purposes\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Why does the author mention X?",'
        f'"type":"rhetorical_purpose",'
        f'"options":["A. To illustrate...","B. To contrast...","C. To support...","D. To question..."],'
        f'"answer":"B",'
        f'"explanation":"The author mentions X to achieve this rhetorical purpose."}}'
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


def generate_reference_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Reference" question.
    Asks what a pronoun (it, they, this, etc.) refers to.

    Returns: {
        "question": "The word 'it' in paragraph X refers to:",
        "type": "reference",
        "pronoun": "it",
        "context": "...sentence containing the pronoun...",
        "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
        "answer": "A",
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Reference' question for TOEFL format:\n"
        f"1. Identify a pronoun (it, they, this, these, that, those) in the passage\n"
        f"2. Ask what the pronoun refers to\n"
        f"3. Provide the sentence containing the pronoun as context\n"
        f"4. Options should be plausible nouns/noun phrases from nearby text\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"The word \'it\' in the passage refers to:",'
        f'"type":"reference",'
        f'"pronoun":"it",'
        f'"context":"...sentence containing it...",'
        f'"options":["A. ...","B. ...","C. ...","D. ..."],'
        f'"answer":"A",'
        f'"explanation":"\'It\' refers to [noun] mentioned earlier."}}'
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


def generate_sentence_simplification_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Sentence Simplification" question.
    Asks which sentence best expresses the essential information of a complex sentence.

    Returns: {
        "question": "Which sentence best expresses the essential information?",
        "type": "sentence_simplification",
        "original_sentence": "...complex sentence from passage...",
        "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
        "answer": "B",
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Sentence Simplification' question for TOEFL format:\n"
        f"1. Select a complex sentence from the passage (15-25 words, with clauses)\n"
        f"2. Create 4 simplified versions\n"
        f"3. One should preserve essential meaning, others should omit key info or add incorrect info\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Which sentence best expresses the essential information in the highlighted sentence?",'
        f'"type":"sentence_simplification",'
        f'"original_sentence":"...complex sentence...",'
        f'"options":["A. Simplified version 1","B. Correct simplified version","C. Omits key info","D. Adds incorrect info"],'
        f'"answer":"B",'
        f'"explanation":"Option B preserves all essential information without adding or omitting key details."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=700)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_insert_text_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Insert Text" question.
    Asks where a given sentence best fits in the passage.

    Returns: {
        "question": "Where would the following sentence best fit?",
        "type": "insert_text",
        "sentence_to_insert": "...",
        "passage_with_markers": "...passage with [A], [B], [C], [D] markers...",
        "answer": "C",
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate an 'Insert Text' question for TOEFL format:\n"
        f"1. Create a sentence that logically fits somewhere in the passage\n"
        f"2. Mark 4 possible insertion points in the passage as [A], [B], [C], [D]\n"
        f"3. One position should be clearly best based on logical flow and cohesion\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Where would the following sentence best fit?",'
        f'"type":"insert_text",'
        f'"sentence_to_insert":"This new sentence provides additional information.",'
        f'"passage_with_markers":"...passage text... [A] ...more text... [B] ...etc...",'
        f'"answer":"C",'
        f'"explanation":"Position C is best because it maintains logical flow and cohesion."}}'
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


def generate_prose_summary_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Prose Summary" question.
    Asks to select 3 major ideas from 6 options to complete a summary.

    Returns: {
        "question": "Select 3 answer choices that express the most important ideas.",
        "type": "prose_summary",
        "intro_sentence": "The passage discusses...",
        "options": ["A. ...", "B. ...", "C. ...", "D. ...", "E. ...", "F. ..."],
        "correct_answers": ["A", "C", "E"],
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Prose Summary' question for TOEFL format:\n"
        f"1. Write an introductory sentence summarizing the passage topic\n"
        f"2. Create 6 statements: 3 major ideas (correct) and 3 minor/incorrect details\n"
        f"3. Major ideas should cover main points; minor details should be too specific or incorrect\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Select 3 answer choices that express the most important ideas in the passage.",'
        f'"type":"prose_summary",'
        f'"intro_sentence":"The passage discusses...",'
        f'"options":["A. Major idea 1","B. Minor detail","C. Major idea 2","D. Incorrect","E. Major idea 3","F. Too specific"],'
        f'"correct_answers":["A","C","E"],'
        f'"explanation":"A, C, and E are the major ideas; B and F are minor details; D is incorrect."}}'
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


def generate_fill_table_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate a TOEFL "Fill in a Table" question.
    Asks to categorize information from the passage into a table.

    Returns: {
        "question": "Complete the table by matching statements to categories.",
        "type": "fill_table",
        "categories": ["Category A", "Category B"],
        "statements": [
            {"id": "1", "text": "Statement 1", "category": "A"},
            {"id": "2", "text": "Statement 2", "category": "B"},
            ...
        ],
        "answer": {"A": ["1", "3", "5"], "B": ["2", "4", "6"]},
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: TOEFL.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Fill in a Table' question for TOEFL format:\n"
        f"1. Identify 2 main categories discussed in the passage\n"
        f"2. Create 6-7 statements from the passage\n"
        f"3. Each statement should clearly belong to one category\n"
        f"4. Mix the order of statements\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Complete the table by matching statements to the correct category.",'
        f'"type":"fill_table",'
        f'"categories":["Category A","Category B"],'
        f'"statements":[{{"id":"1","text":"Statement about A","category":"A"}},{{"id":"2","text":"Statement about B","category":"B"}}],'
        f'"answer":{{"A":["1","3","5"],"B":["2","4","6"]}},'
        f'"explanation":"Statements are categorized based on their content in the passage."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=900)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


# ============================================================================
# IELTS Reading Question Generators
# ============================================================================

def generate_ielts_tfng_question(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate an IELTS "True/False/Not Given" question.

    Returns: {
        "question": "Do the following statements agree with the information in the passage?",
        "type": "ielts_tfng",
        "instructions": "Write TRUE if the statement agrees with the information, FALSE if..., NOT GIVEN if...",
        "statements": [
            {"id": 1, "text": "Statement 1", "answer": "TRUE"},
            {"id": 2, "text": "Statement 2", "answer": "FALSE"},
            {"id": 3, "text": "Statement 3", "answer": "NOT GIVEN"},
            ...
        ],
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: IELTS.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'True/False/Not Given' question set for IELTS format:\n"
        f"1. Create 5-7 statements about the passage\n"
        f"2. TRUE: statement agrees with information in passage\n"
        f"3. FALSE: statement contradicts information in passage\n"
        f"4. NOT GIVEN: information is not mentioned in passage\n"
        f"5. Mix the order (don't group by answer type)\n"
        f"6. Ensure at least one of each type (TRUE, FALSE, NOT GIVEN)\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Do the following statements agree with the information in the passage?",'
        f'"type":"ielts_tfng",'
        f'"instructions":"Write TRUE if the statement agrees with the information, FALSE if the statement contradicts the information, NOT GIVEN if there is no information on this.",'
        f'"statements":[{{"id":1,"text":"Statement text","answer":"TRUE"}},{{"id":2,"text":"Another statement","answer":"FALSE"}}],'
        f'"explanation":"Detailed explanation for each statement."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=1000)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_ielts_matching_headings(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate an IELTS "Matching Headings" question.

    Returns: {
        "question": "Choose the correct heading for each paragraph from the list of headings.",
        "type": "ielts_matching_headings",
        "headings": [
            {"id": "i", "text": "Heading 1"},
            {"id": "ii", "text": "Heading 2"},
            ...
        ],
        "paragraphs": [
            {"id": "A", "answer": "iii"},
            {"id": "B", "answer": "i"},
            ...
        ],
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: IELTS.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Matching Headings' question for IELTS format:\n"
        f"1. Identify 4-6 distinct paragraphs/sections in the passage\n"
        f"2. Create a heading for each paragraph that captures its main idea\n"
        f"3. Add 2-3 extra distractor headings (plausible but incorrect)\n"
        f"4. Use Roman numerals for headings (i, ii, iii, etc.)\n"
        f"5. Use letters for paragraphs (A, B, C, etc.)\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Choose the correct heading for each paragraph from the list of headings below.",'
        f'"type":"ielts_matching_headings",'
        f'"headings":[{{"id":"i","text":"First heading"}},{{"id":"ii","text":"Second heading"}}],'
        f'"paragraphs":[{{"id":"A","answer":"ii"}},{{"id":"B","answer":"i"}}],'
        f'"explanation":"Paragraph A matches heading ii because... Paragraph B matches heading i because..."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=1000)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_ielts_completion_question(
    passage: str,
    completion_type: str,  # "summary", "note", "table"
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate an IELTS completion question (Summary/Note/Table).

    Returns: {
        "question": "Complete the summary/notes/table using words from the passage.",
        "type": "ielts_completion",
        "completion_type": "summary",
        "instructions": "Use NO MORE THAN TWO WORDS from the passage for each answer.",
        "text_with_blanks": "Text with (1)_____ and (2)_____ blanks.",
        "answers": {
            "1": "answer one",
            "2": "answer two"
        },
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: IELTS.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a '{completion_type} completion' question for IELTS format:\n"
        f"1. Create a {completion_type} of part of the passage\n"
        f"2. Remove 5-7 key words/phrases and replace with numbered blanks: (1)_____, (2)_____, etc.\n"
        f"3. Answers must be words taken directly from the passage\n"
        f"4. Each answer should be 1-2 words maximum\n"
        f"5. Blanks should test understanding of key concepts\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Complete the {completion_type} using words from the passage.",'
        f'"type":"ielts_completion",'
        f'"completion_type":"{completion_type}",'
        f'"instructions":"Use NO MORE THAN TWO WORDS from the passage for each answer.",'
        f'"text_with_blanks":"The passage discusses (1)_____ which affects (2)_____.",'
        f'"answers":{{"1":"answer one","2":"answer two"}},'
        f'"explanation":"Answer 1 is found in paragraph X where it states... Answer 2 is mentioned in paragraph Y..."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=1000)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_ielts_matching_question(
    passage: str,
    matching_type: str,  # "information", "features", "sentence_endings"
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate an IELTS matching question (Information/Features/Sentence Endings).

    Returns: {
        "question": "Match each statement with the correct paragraph/person/ending.",
        "type": "ielts_matching",
        "matching_type": "information",
        "items": [
            {"id": 1, "text": "Item to match", "answer": "C"}
        ],
        "options": ["A", "B", "C", "D", "E"],
        "explanation": "..."
    }
    """
    if matching_type == "information":
        question_text = "Which paragraph contains the following information?"
        instructions = "Match each piece of information to the correct paragraph (A-E)."
    elif matching_type == "features":
        question_text = "Match each statement to the correct person/theory/feature."
        instructions = "Match each statement to the correct option (A-E)."
    else:  # sentence_endings
        question_text = "Complete each sentence with the correct ending."
        instructions = "Match each sentence beginning to the correct ending (A-G)."

    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: IELTS.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a '{matching_type} matching' question for IELTS format:\n"
        f"1. Create 5-6 items to match\n"
        f"2. Provide 5-7 options (some may be used more than once or not at all)\n"
        f"3. Ensure clear, unambiguous matches based on passage content\n"
        f"4. For sentence endings: provide incomplete sentences and matching endings\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"{question_text}",'
        f'"type":"ielts_matching",'
        f'"matching_type":"{matching_type}",'
        f'"instructions":"{instructions}",'
        f'"items":[{{"id":1,"text":"Item text","answer":"C"}}],'
        f'"options":["A","B","C","D","E"],'
        f'"explanation":"Item 1 matches C because..."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=1000)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_ielts_short_answer(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate an IELTS "Short Answer" question.

    Returns: {
        "question": "Answer the questions below using words from the passage.",
        "type": "ielts_short_answer",
        "instructions": "Use NO MORE THAN THREE WORDS for each answer.",
        "questions": [
            {"id": 1, "text": "What is...?", "answer": "the correct answer"},
            {"id": 2, "text": "When did...?", "answer": "in 1995"}
        ],
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: IELTS.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Short Answer' question set for IELTS format:\n"
        f"1. Create 5-7 questions about specific details in the passage\n"
        f"2. Questions should use: What, When, Where, Who, How, Why\n"
        f"3. Answers must be 1-3 words taken directly from the passage\n"
        f"4. Questions should follow the order of information in the passage\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Answer the questions below using words from the passage.",'
        f'"type":"ielts_short_answer",'
        f'"instructions":"Use NO MORE THAN THREE WORDS from the passage for each answer.",'
        f'"questions":[{{"id":1,"text":"What is the main purpose?","answer":"to inform readers"}},{{"id":2,"text":"When did this occur?","answer":"in 2010"}}],'
        f'"explanation":"Question 1: The answer is found in paragraph 1... Question 2: Paragraph 3 states..."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=1000)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}


def generate_ielts_diagram_label(
    passage: str,
    cefr_level: str,
    ai_client,
) -> dict:
    """
    Generate an IELTS "Diagram Label" question.

    Returns: {
        "question": "Label the diagram using words from the passage.",
        "type": "ielts_diagram_label",
        "instructions": "Use NO MORE THAN TWO WORDS for each label.",
        "diagram_description": "A diagram showing the process of...",
        "labels": [
            {"id": 1, "position": "top left", "answer": "input stage"},
            {"id": 2, "position": "center", "answer": "processing unit"}
        ],
        "explanation": "..."
    }
    """
    prompt = (
        f"Student CEFR level: {cefr_level}. Exam: IELTS.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"Generate a 'Diagram Label' question for IELTS format:\n"
        f"1. Describe a diagram/process/system mentioned in the passage\n"
        f"2. Create 5-7 labels for key parts of the diagram\n"
        f"3. Answers must be 1-2 words taken directly from the passage\n"
        f"4. Include position descriptions (top, bottom, left, right, center)\n\n"
        f'Return ONLY a JSON object:\n'
        f'{{"question":"Label the diagram below using words from the passage.",'
        f'"type":"ielts_diagram_label",'
        f'"instructions":"Use NO MORE THAN TWO WORDS from the passage for each label.",'
        f'"diagram_description":"A diagram showing the structure of...",'
        f'"labels":[{{"id":1,"position":"top","answer":"main component"}},{{"id":2,"position":"bottom","answer":"base layer"}}],'
        f'"explanation":"Label 1 (top) refers to the main component mentioned in paragraph 2... Label 2 (bottom) is the base layer described in paragraph 3..."}}'
    )

    response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=1000)
    text = response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    result_json = text[start:end] if start != -1 else "{}"

    try:
        return json.loads(result_json)
    except json.JSONDecodeError:
        return {"error": "Could not parse question", "raw": text}

