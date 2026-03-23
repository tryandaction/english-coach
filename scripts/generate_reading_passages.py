"""
Professional reading passage generation script for TOEFL/IELTS preparation.

Generates 180+ passages with professional standards:
- TOEFL: 100+ passages (700±50 words, 10 questions each)
- IELTS: 80+ passages (800-900 words, 13-14 questions each)
- Subject-specific content with proper difficulty grading
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.client import AIClient
from core.knowledge_base.store import KnowledgeBase
from core.ingestion.pipeline import Chunk
from utils.paths import get_data_dir
import hashlib


# TOEFL subject distribution
TOEFL_SUBJECTS = {
    "biology": 16,
    "geology": 12,
    "astronomy": 10,
    "art_history": 8,
    "archaeology": 6,
    "psychology": 10,
    "sociology": 8,
    "linguistics": 6,
    "environmental_science": 12,
    "general_academic": 12,
}

# IELTS topic distribution
IELTS_TOPICS = {
    "environment": 12,
    "technology": 12,
    "education": 10,
    "health": 10,
    "society": 10,
    "business": 8,
    "culture": 8,
    "science": 10,
}

# TOEFL question type distribution (10 questions per passage)
TOEFL_QUESTION_DISTRIBUTION = {
    "factual": 3,
    "inference": 2,
    "vocabulary": 2,
    "rhetorical_purpose": 1,
    "negative_factual": 1,
    "reference": 1,
}

# IELTS question type distribution (13-14 questions per passage)
IELTS_QUESTION_TYPES = [
    "tfng",
    "matching_headings",
    "summary_completion",
    "matching_information",
    "short_answer",
]


def generate_toefl_passage(
    ai_client: AIClient,
    subject: str,
    difficulty_score: int,
    passage_number: int
) -> dict:
    """Generate a single TOEFL reading passage with questions."""

    # Map difficulty_score to CEFR
    if difficulty_score <= 3:
        cefr = "B1"
    elif difficulty_score <= 5:
        cefr = "B2"
    elif difficulty_score <= 7:
        cefr = "C1"
    else:
        cefr = "C2"

    prompt = f"""Generate a TOEFL reading passage for academic preparation.

Subject: {subject}
Difficulty: {difficulty_score}/10 (CEFR {cefr})
Target word count: 700 words (±50 words acceptable)

Requirements:
1. Academic style appropriate for university-level reading
2. Clear paragraph structure (4-6 paragraphs)
3. Include specific examples, data, or case studies
4. Use subject-specific vocabulary naturally
5. Maintain coherent flow and logical organization
6. Word count must be between 650-750 words

Generate 10 questions following this distribution:
- 3 Factual Information questions (directly stated in passage)
- 2 Inference questions (require logical deduction)
- 2 Vocabulary questions (word meaning in context)
- 1 Rhetorical Purpose question (why author mentions X)
- 1 Negative Factual question (which is NOT true)
- 1 Reference question (what pronoun refers to)

Return ONLY a JSON object with this structure:
{{
  "passage": "Full passage text here...",
  "title": "Passage title",
  "word_count": 700,
  "questions": [
    {{
      "question": "Question text",
      "type": "factual",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "B",
      "explanation": "Why B is correct"
    }}
  ]
}}"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=3500)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"Warning: No JSON found for {subject} passage {passage_number}")
            return None

        json_text = text[start:end]
        data = json.loads(json_text)

        # Validate
        if not data.get("passage") or not data.get("questions"):
            print(f"Warning: Invalid data structure for {subject} passage {passage_number}")
            return None

        if len(data["questions"]) != 10:
            print(f"Warning: Expected 10 questions, got {len(data['questions'])} for {subject} passage {passage_number}")

        # Add metadata
        data["subject"] = subject
        data["difficulty_score"] = difficulty_score
        data["cefr"] = cefr
        data["exam"] = "toefl"
        data["estimated_time"] = 20  # 20 minutes for TOEFL reading

        return data

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON for {subject} passage {passage_number}: {e}")
        return None
    except Exception as e:
        print(f"Error generating {subject} passage {passage_number}: {e}")
        return None


def generate_ielts_passage(
    ai_client: AIClient,
    topic: str,
    difficulty_score: int,
    passage_number: int
) -> dict:
    """Generate a single IELTS reading passage with questions."""

    # Map difficulty_score to IELTS band
    if difficulty_score <= 3:
        band = "5.0-6.0"
        cefr = "B1-B2"
    elif difficulty_score <= 6:
        band = "6.5-7.0"
        cefr = "B2-C1"
    else:
        band = "7.5-9.0"
        cefr = "C1-C2"

    prompt = f"""Generate an IELTS Academic reading passage.

Topic: {topic}
Difficulty: {difficulty_score}/10 (Band {band}, CEFR {cefr})
Target word count: 850 words (800-900 acceptable)

Requirements:
1. Academic style suitable for IELTS Academic module
2. Clear paragraph structure (5-7 paragraphs)
3. Include specific examples, research findings, or expert opinions
4. Use topic-specific vocabulary naturally
5. Maintain coherent flow with clear topic sentences
6. Word count must be between 800-900 words

Generate 13-14 questions using a mix of these types:
- True/False/Not Given (3-4 questions)
- Matching Headings (3-4 questions)
- Summary/Note Completion (2-3 questions)
- Matching Information (2-3 questions)
- Short Answer (1-2 questions)

Return ONLY a JSON object with this structure:
{{
  "passage": "Full passage text here...",
  "title": "Passage title",
  "word_count": 850,
  "questions": [
    {{
      "question": "Question text",
      "type": "tfng",
      "statements": [{{"text": "Statement", "answer": "TRUE"}}],
      "explanation": "Explanation"
    }},
    {{
      "question": "Match headings to paragraphs",
      "type": "matching_headings",
      "headings": [{{"id": "i", "text": "Heading"}}],
      "paragraphs": [{{"id": "A", "answer": "i"}}],
      "explanation": "Explanation"
    }}
  ]
}}"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=4000)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"Warning: No JSON found for {topic} passage {passage_number}")
            return None

        json_text = text[start:end]
        data = json.loads(json_text)

        # Validate
        if not data.get("passage") or not data.get("questions"):
            print(f"Warning: Invalid data structure for {topic} passage {passage_number}")
            return None

        if len(data["questions"]) < 13 or len(data["questions"]) > 14:
            print(f"Warning: Expected 13-14 questions, got {len(data['questions'])} for {topic} passage {passage_number}")

        # Add metadata
        data["topic"] = topic
        data["difficulty_score"] = difficulty_score
        data["band"] = band
        data["cefr"] = cefr.split("-")[0]  # Use lower bound
        data["exam"] = "ielts"
        data["estimated_time"] = 20  # 20 minutes for IELTS reading

        return data

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON for {topic} passage {passage_number}: {e}")
        return None
    except Exception as e:
        print(f"Error generating {topic} passage {passage_number}: {e}")
        return None


def save_passage_to_kb(kb: KnowledgeBase, passage_data: dict) -> bool:
    """Save generated passage to knowledge base."""
    try:
        # Create chunk for passage
        passage_text = passage_data["passage"]
        chunk_id = hashlib.sha256(passage_text.encode()).hexdigest()[:16]

        # Extract question types
        question_types = [q.get("type", "unknown") for q in passage_data.get("questions", [])]

        chunk = Chunk(
            chunk_id=chunk_id,
            source_file=f"ai_generated_{passage_data['exam']}_{passage_data.get('subject', passage_data.get('topic'))}",
            content_type="reading",
            text=passage_text,
            difficulty=passage_data.get("cefr", "B2"),
            topic=passage_data.get("subject", passage_data.get("topic", "general")),
            exam=passage_data["exam"],
            language="en",
            metadata={
                "title": passage_data.get("title", ""),
                "word_count": passage_data.get("word_count", 0),
                "questions": passage_data.get("questions", []),
                "difficulty_score": passage_data.get("difficulty_score", 5),
                "estimated_time": passage_data.get("estimated_time", 20),
                "subject_category": passage_data.get("subject", passage_data.get("topic", "general")),
                "question_types": question_types,
                "source_quality": "ai_generated",
            }
        )

        kb.add_chunks([chunk])
        return True

    except Exception as e:
        print(f"Error saving passage to KB: {e}")
        return False


def main():
    """Main generation workflow."""
    print("=" * 70)
    print("Professional Reading Passage Generation for TOEFL/IELTS")
    print("=" * 70)

    # Initialize components
    ai_client = AIClient()
    data_dir = get_data_dir()
    kb = KnowledgeBase(data_dir)

    total_generated = 0

    # Generate TOEFL passages (100 total)
    print("\n[1/2] Generating TOEFL reading passages...")
    print("-" * 70)

    for subject, count in TOEFL_SUBJECTS.items():
        print(f"\n{subject.replace('_', ' ').title()}: {count} passages")

        for i in range(count):
            # Vary difficulty across passages
            difficulty_score = 3 + (i % 7)  # Range 3-9

            print(f"  Passage {i+1}/{count} (difficulty {difficulty_score}/10)...", end=" ")

            passage_data = generate_toefl_passage(ai_client, subject, difficulty_score, i+1)

            if passage_data:
                if save_passage_to_kb(kb, passage_data):
                    total_generated += 1
                    print(f"✓ ({passage_data.get('word_count', 0)} words, {len(passage_data.get('questions', []))} questions)")
                else:
                    print("✗ (save failed)")
            else:
                print("✗ (generation failed)")

    # Generate IELTS passages (80 total)
    print("\n[2/2] Generating IELTS reading passages...")
    print("-" * 70)

    for topic, count in IELTS_TOPICS.items():
        print(f"\n{topic.replace('_', ' ').title()}: {count} passages")

        for i in range(count):
            # Vary difficulty across passages
            difficulty_score = 3 + (i % 7)  # Range 3-9

            print(f"  Passage {i+1}/{count} (difficulty {difficulty_score}/10)...", end=" ")

            passage_data = generate_ielts_passage(ai_client, topic, difficulty_score, i+1)

            if passage_data:
                if save_passage_to_kb(kb, passage_data):
                    total_generated += 1
                    print(f"✓ ({passage_data.get('word_count', 0)} words, {len(passage_data.get('questions', []))} questions)")
                else:
                    print("✗ (save failed)")
            else:
                print("✗ (generation failed)")

    # Summary
    print("\n" + "=" * 70)
    print(f"Generation complete!")
    print(f"Total passages added to knowledge base: {total_generated}")
    print(f"Target: 180 passages (100 TOEFL + 80 IELTS)")
    print(f"Achievement: {total_generated/180*100:.1f}%")
    print("=" * 70)


if __name__ == "__main__":
    main()
