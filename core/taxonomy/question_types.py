"""
Question Type Taxonomy for English Coach Platform

This module defines the comprehensive taxonomy of question types for all supported
exams (TOEFL iBT 2026, IELTS Academic, GRE General, CET-4/6).

Each question type includes:
- Unique identifier
- Display name
- Description
- Difficulty range
- Implementation status
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class QuestionStatus(Enum):
    """Implementation status of question types."""
    IMPLEMENTED = "implemented"
    IN_PROGRESS = "in_progress"
    PLANNED = "planned"
    NOT_STARTED = "not_started"


@dataclass
class QuestionType:
    """Represents a specific question type."""
    id: str
    name: str
    description: str
    difficulty_range: tuple  # (min, max) on 1-5 scale
    status: QuestionStatus
    exam: str
    section: str
    instructions: str = ""
    example: str = ""


# TOEFL iBT 2026 Question Types
TOEFL_READING_TYPES = {
    "factual": QuestionType(
        id="toefl_reading_factual",
        name="Factual Information",
        description="Identify specific facts or details explicitly stated in the passage",
        difficulty_range=(1, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="According to the passage, which of the following is true about X?"
    ),
    "negative_factual": QuestionType(
        id="toefl_reading_negative_factual",
        name="Negative Factual Information",
        description="Identify which statement is NOT true or NOT mentioned",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="All of the following are mentioned EXCEPT:"
    ),
    "inference": QuestionType(
        id="toefl_reading_inference",
        name="Inference",
        description="Draw logical conclusions from information in the passage",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="What can be inferred from paragraph X about Y?"
    ),
    "vocabulary": QuestionType(
        id="toefl_reading_vocabulary",
        name="Vocabulary",
        description="Determine the meaning of a word from context",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="The word 'X' in the passage is closest in meaning to:"
    ),
    "rhetorical_purpose": QuestionType(
        id="toefl_reading_rhetorical_purpose",
        name="Rhetorical Purpose",
        description="Understand why the author mentions something or uses a particular example",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Why does the author mention X in paragraph Y?"
    ),
    "reference": QuestionType(
        id="toefl_reading_reference",
        name="Reference",
        description="Identify what a pronoun or phrase refers to",
        difficulty_range=(2, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="The word 'it' in paragraph X refers to:"
    ),
    "sentence_simplification": QuestionType(
        id="toefl_reading_sentence_simplification",
        name="Sentence Simplification",
        description="Choose the sentence that best expresses the essential information",
        difficulty_range=(3, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Which sentence best expresses the essential information?"
    ),
    "insert_text": QuestionType(
        id="toefl_reading_insert_text",
        name="Insert Text",
        description="Determine where a sentence best fits in the passage",
        difficulty_range=(3, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Where would the following sentence best fit?"
    ),
    "prose_summary": QuestionType(
        id="toefl_reading_prose_summary",
        name="Prose Summary",
        description="Select major ideas to complete a summary (multiple answers)",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Select 3 answer choices that express the most important ideas."
    ),
    "fill_table": QuestionType(
        id="toefl_reading_fill_table",
        name="Fill in a Table",
        description="Categorize information from the passage into a table",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Complete the table by matching statements to categories."
    ),
    "complete_words": QuestionType(
        id="toefl_reading_complete_words",
        name="Complete the Words (NEW 2026)",
        description="Fill in missing letters to complete words in context",
        difficulty_range=(2, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Complete the words by filling in the missing letters."
    ),
    "daily_life": QuestionType(
        id="toefl_reading_daily_life",
        name="Read in Daily Life (NEW 2026)",
        description="Interpret practical texts like emails, notices, menus",
        difficulty_range=(1, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="reading",
        instructions="Read the email/notice and answer the questions."
    ),
}

TOEFL_LISTENING_TYPES = {
    "gist_content": QuestionType(
        id="toefl_listening_gist_content",
        name="Gist-Content",
        description="Understand the main idea or topic",
        difficulty_range=(2, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="What is the main topic of the lecture/conversation?"
    ),
    "gist_purpose": QuestionType(
        id="toefl_listening_gist_purpose",
        name="Gist-Purpose",
        description="Understand the speaker's purpose or reason",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="Why does the student visit the professor?"
    ),
    "detail": QuestionType(
        id="toefl_listening_detail",
        name="Detail",
        description="Identify specific facts or details mentioned",
        difficulty_range=(1, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="According to the professor, what is X?"
    ),
    "function": QuestionType(
        id="toefl_listening_function",
        name="Function",
        description="Understand why the speaker says something",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="Why does the professor say this: [replay]"
    ),
    "attitude": QuestionType(
        id="toefl_listening_attitude",
        name="Attitude",
        description="Identify the speaker's attitude or opinion",
        difficulty_range=(3, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="What is the professor's attitude toward X?"
    ),
    "organization": QuestionType(
        id="toefl_listening_organization",
        name="Organization",
        description="Understand how information is organized",
        difficulty_range=(3, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="How does the professor organize the information?"
    ),
    "connecting": QuestionType(
        id="toefl_listening_connecting",
        name="Connecting Content",
        description="Make connections between ideas or concepts",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="What is the relationship between X and Y?"
    ),
    "inference": QuestionType(
        id="toefl_listening_inference",
        name="Making Inferences",
        description="Draw conclusions from what is said",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="listening",
        instructions="What can be inferred about X?"
    ),
}

TOEFL_SPEAKING_TYPES = {
    "listen_repeat": QuestionType(
        id="toefl_speaking_listen_repeat",
        name="Listen & Repeat (NEW 2026)",
        description="Repeat sentences to test pronunciation",
        difficulty_range=(1, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="speaking",
        instructions="Listen and repeat each sentence exactly as you hear it."
    ),
    "virtual_interview": QuestionType(
        id="toefl_speaking_virtual_interview",
        name="Virtual Interview (NEW 2026)",
        description="Respond to conversational questions naturally",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="speaking",
        instructions="Answer the interviewer's questions naturally."
    ),
    "independent": QuestionType(
        id="toefl_speaking_independent",
        name="Independent Task",
        description="Express and support an opinion on a familiar topic",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="speaking",
        instructions="State your opinion and explain your reasons with examples."
    ),
    "integrated_campus": QuestionType(
        id="toefl_speaking_integrated_campus",
        name="Integrated - Campus Situation",
        description="Read announcement, listen to conversation, summarize opinion",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="speaking",
        instructions="Summarize the announcement and the student's opinion."
    ),
    "integrated_academic": QuestionType(
        id="toefl_speaking_integrated_academic",
        name="Integrated - Academic Concept",
        description="Read definition, listen to example, explain concept",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="speaking",
        instructions="Explain the concept using the example from the lecture."
    ),
    "integrated_lecture": QuestionType(
        id="toefl_speaking_integrated_lecture",
        name="Integrated - Lecture Summary",
        description="Listen to lecture and summarize main points",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="speaking",
        instructions="Summarize the lecture, explaining the main points."
    ),
}

TOEFL_WRITING_TYPES = {
    "build_sentence": QuestionType(
        id="toefl_writing_build_sentence",
        name="Build a Sentence (NEW 2026)",
        description="Construct grammatically correct sentences",
        difficulty_range=(1, 3),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="writing",
        instructions="Arrange the words to form a grammatically correct sentence."
    ),
    "write_email": QuestionType(
        id="toefl_writing_write_email",
        name="Write an Email (NEW 2026)",
        description="Write a practical email for a specific purpose",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="writing",
        instructions="Write an email responding to the situation described."
    ),
    "academic_discussion": QuestionType(
        id="toefl_writing_academic_discussion",
        name="Academic Discussion (NEW 2026)",
        description="Contribute to an online academic discussion",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="writing",
        instructions="Read the discussion and write a response contributing your ideas."
    ),
    "integrated": QuestionType(
        id="toefl_writing_integrated",
        name="Integrated Task",
        description="Read passage, listen to lecture, write response",
        difficulty_range=(4, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="writing",
        instructions="Summarize the points in the lecture and explain how they relate to the reading."
    ),
    "independent": QuestionType(
        id="toefl_writing_independent",
        name="Independent Essay",
        description="Write an essay expressing and supporting your opinion",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="toefl",
        section="writing",
        instructions="Do you agree or disagree? Use specific reasons and examples."
    ),
}

# IELTS Academic Question Types
IELTS_READING_TYPES = {
    "multiple_choice": QuestionType(
        id="ielts_reading_multiple_choice",
        name="Multiple Choice",
        description="Choose the correct answer from options",
        difficulty_range=(2, 4),
        status=QuestionStatus.IMPLEMENTED,
        exam="ielts",
        section="reading",
        instructions="Choose the correct letter, A, B, C or D."
    ),
    "true_false_ng": QuestionType(
        id="ielts_reading_true_false_ng",
        name="True/False/Not Given",
        description="Determine if statements agree with information in the passage",
        difficulty_range=(3, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Do the following statements agree with the information in the passage?"
    ),
    "yes_no_ng": QuestionType(
        id="ielts_reading_yes_no_ng",
        name="Yes/No/Not Given",
        description="Determine if statements agree with the writer's views/claims",
        difficulty_range=(3, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Do the following statements agree with the views of the writer?"
    ),
    "matching_headings": QuestionType(
        id="ielts_reading_matching_headings",
        name="Matching Headings",
        description="Match headings to paragraphs or sections",
        difficulty_range=(4, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Choose the correct heading for each paragraph from the list."
    ),
    "matching_information": QuestionType(
        id="ielts_reading_matching_information",
        name="Matching Information",
        description="Locate specific information in paragraphs",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Which paragraph contains the following information?"
    ),
    "matching_features": QuestionType(
        id="ielts_reading_matching_features",
        name="Matching Features",
        description="Match statements to features (people, theories, etc.)",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Match each statement with the correct person/theory."
    ),
    "matching_sentence_endings": QuestionType(
        id="ielts_reading_matching_sentence_endings",
        name="Matching Sentence Endings",
        description="Complete sentences by matching beginnings to endings",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Complete each sentence with the correct ending."
    ),
    "sentence_completion": QuestionType(
        id="ielts_reading_sentence_completion",
        name="Sentence Completion",
        description="Complete sentences with words from the passage",
        difficulty_range=(2, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Complete the sentences below with words from the passage."
    ),
    "summary_completion": QuestionType(
        id="ielts_reading_summary_completion",
        name="Summary Completion",
        description="Complete a summary with words from a list or passage",
        difficulty_range=(3, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Complete the summary using words from the box."
    ),
    "note_completion": QuestionType(
        id="ielts_reading_note_completion",
        name="Note Completion",
        description="Complete notes with words from the passage",
        difficulty_range=(2, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Complete the notes below with words from the passage."
    ),
    "table_completion": QuestionType(
        id="ielts_reading_table_completion",
        name="Table Completion",
        description="Complete a table with information from the passage",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Complete the table below with information from the passage."
    ),
    "flowchart_completion": QuestionType(
        id="ielts_reading_flowchart_completion",
        name="Flow-chart Completion",
        description="Complete a flow-chart with words from the passage",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Complete the flow-chart below with words from the passage."
    ),
    "diagram_label": QuestionType(
        id="ielts_reading_diagram_label",
        name="Diagram Label Completion",
        description="Label a diagram with words from the passage",
        difficulty_range=(2, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Label the diagram below with words from the passage."
    ),
    "short_answer": QuestionType(
        id="ielts_reading_short_answer",
        name="Short Answer Questions",
        description="Answer questions with words from the passage",
        difficulty_range=(2, 3),
        status=QuestionStatus.NOT_STARTED,
        exam="ielts",
        section="reading",
        instructions="Answer the questions below using NO MORE THAN THREE WORDS."
    ),
}

# GRE Question Types
GRE_VERBAL_TYPES = {
    "reading_comprehension": QuestionType(
        id="gre_verbal_reading_comprehension",
        name="Reading Comprehension",
        description="Answer questions about passages",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="gre",
        section="verbal",
        instructions="Select the correct answer based on the passage."
    ),
    "text_completion": QuestionType(
        id="gre_verbal_text_completion",
        name="Text Completion",
        description="Fill in 1-3 blanks to complete the text logically",
        difficulty_range=(4, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="gre",
        section="verbal",
        instructions="Select the word(s) that best complete the text."
    ),
    "sentence_equivalence": QuestionType(
        id="gre_verbal_sentence_equivalence",
        name="Sentence Equivalence",
        description="Choose two words that complete the sentence with similar meanings",
        difficulty_range=(4, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="gre",
        section="verbal",
        instructions="Select TWO answer choices that produce sentences with similar meanings."
    ),
}

# CET-4/6 Question Types
CET_LISTENING_TYPES = {
    "news_report": QuestionType(
        id="cet_listening_news_report",
        name="News Report Comprehension",
        description="Listen to news reports and answer questions (CET-4)",
        difficulty_range=(2, 3),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="listening",
        instructions="Listen to the news report and answer the questions."
    ),
    "long_conversation": QuestionType(
        id="cet_listening_long_conversation",
        name="Long Conversations",
        description="Listen to conversations and answer questions",
        difficulty_range=(2, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="listening",
        instructions="Listen to the conversation and answer the questions."
    ),
    "passage": QuestionType(
        id="cet_listening_passage",
        name="Passages/Lectures",
        description="Listen to passages or lectures and answer questions",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="listening",
        instructions="Listen to the passage and answer the questions."
    ),
    "dictation": QuestionType(
        id="cet_listening_dictation",
        name="Dictation (CET-6)",
        description="Listen and write down missing words",
        difficulty_range=(4, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="listening",
        instructions="Listen and fill in the blanks with the exact words you hear."
    ),
}

CET_READING_TYPES = {
    "vocabulary_fill": QuestionType(
        id="cet_reading_vocabulary_fill",
        name="Vocabulary (选词填空)",
        description="Fill in blanks by selecting words from a list",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="reading",
        instructions="Fill in the blanks by selecting suitable words from the word bank."
    ),
    "long_reading": QuestionType(
        id="cet_reading_long_reading",
        name="Long Reading (段落匹配)",
        description="Match statements to paragraphs",
        difficulty_range=(3, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="reading",
        instructions="Match each statement to the correct paragraph."
    ),
    "careful_reading": QuestionType(
        id="cet_reading_careful_reading",
        name="Careful Reading",
        description="Answer multiple-choice questions about passages",
        difficulty_range=(3, 4),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="reading",
        instructions="Choose the best answer for each question."
    ),
}

CET_WRITING_TYPES = {
    "translation": QuestionType(
        id="cet_writing_translation",
        name="Translation (Chinese to English)",
        description="Translate a Chinese paragraph to English",
        difficulty_range=(4, 5),
        status=QuestionStatus.NOT_STARTED,
        exam="cet",
        section="writing",
        instructions="Translate the following paragraph from Chinese to English."
    ),
    "essay": QuestionType(
        id="cet_writing_essay",
        name="Essay Writing",
        description="Write an essay on a given topic",
        difficulty_range=(3, 5),
        status=QuestionStatus.IMPLEMENTED,
        exam="cet",
        section="writing",
        instructions="Write an essay of 120-180 words on the topic."
    ),
}

# Consolidated taxonomy
QUESTION_TAXONOMY = {
    "toefl": {
        "reading": TOEFL_READING_TYPES,
        "listening": TOEFL_LISTENING_TYPES,
        "speaking": TOEFL_SPEAKING_TYPES,
        "writing": TOEFL_WRITING_TYPES,
    },
    "ielts": {
        "reading": IELTS_READING_TYPES,
        # listening, writing, speaking would be added similarly
    },
    "gre": {
        "verbal": GRE_VERBAL_TYPES,
        # quantitative, writing would be added
    },
    "cet": {
        "listening": CET_LISTENING_TYPES,
        "reading": CET_READING_TYPES,
        "writing": CET_WRITING_TYPES,
    },
}


def get_question_types(exam: str, section: Optional[str] = None) -> Dict:
    """Get question types for an exam and optional section."""
    if exam not in QUESTION_TAXONOMY:
        return {}

    if section:
        return QUESTION_TAXONOMY[exam].get(section, {})

    return QUESTION_TAXONOMY[exam]


def get_question_type(question_type_id: str) -> Optional[QuestionType]:
    """Get a specific question type by ID."""
    for exam_types in QUESTION_TAXONOMY.values():
        for section_types in exam_types.values():
            for qt in section_types.values():
                if qt.id == question_type_id:
                    return qt
    return None


def get_unimplemented_types(exam: Optional[str] = None) -> List[QuestionType]:
    """Get all unimplemented question types, optionally filtered by exam."""
    unimplemented = []

    for exam_name, exam_types in QUESTION_TAXONOMY.items():
        if exam and exam_name != exam:
            continue

        for section_types in exam_types.values():
            for qt in section_types.values():
                if qt.status != QuestionStatus.IMPLEMENTED:
                    unimplemented.append(qt)

    return unimplemented


def print_taxonomy_summary():
    """Print a summary of the question type taxonomy."""
    print("\n" + "="*80)
    print("QUESTION TYPE TAXONOMY SUMMARY")
    print("="*80 + "\n")

    for exam, sections in QUESTION_TAXONOMY.items():
        print(f"\n{exam.upper()}")
        print("-" * 40)

        for section, types in sections.items():
            implemented = sum(1 for qt in types.values() if qt.status == QuestionStatus.IMPLEMENTED)
            total = len(types)

            print(f"\n  {section.capitalize()}: {implemented}/{total} implemented")

            for type_id, qt in types.items():
                status_icon = "[X]" if qt.status == QuestionStatus.IMPLEMENTED else "[ ]"
                print(f"    {status_icon} {qt.name}")

    print("\n" + "="*80)


if __name__ == "__main__":
    print_taxonomy_summary()

    print("\n\nUNIMPLEMENTED QUESTION TYPES (Priority Order):")
    print("="*80)

    unimplemented = get_unimplemented_types()
    print(f"\nTotal unimplemented: {len(unimplemented)}")

    # Group by exam
    by_exam = {}
    for qt in unimplemented:
        if qt.exam not in by_exam:
            by_exam[qt.exam] = []
        by_exam[qt.exam].append(qt)

    for exam, types in by_exam.items():
        print(f"\n{exam.upper()}: {len(types)} types")
        for qt in types:
            print(f"  - {qt.section}/{qt.name}")
