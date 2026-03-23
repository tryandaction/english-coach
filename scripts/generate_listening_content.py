"""
Professional listening content generation script for TOEFL/IELTS preparation.

Generates 240+ listening items with professional standards:
- TOEFL: 160+ items (60 conversations + 100 lectures)
- IELTS: 80+ sets (4 sections each, 320 total items)
- Accent variation and speed control
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


# TOEFL conversation scenarios
TOEFL_CONVERSATION_SCENARIOS = {
    "office_hours": 15,
    "academic_advising": 10,
    "library_services": 8,
    "campus_facilities": 7,
    "student_services": 10,
    "course_registration": 10,
}

# TOEFL lecture topics
TOEFL_LECTURE_TOPICS = {
    "biology": 20,
    "geology": 15,
    "astronomy": 12,
    "psychology": 15,
    "art_history": 10,
    "archaeology": 8,
    "linguistics": 10,
    "environmental_science": 10,
}

# IELTS section types
IELTS_SECTIONS = {
    "section1_social": 20,  # Social conversation
    "section2_monologue": 20,  # Monologue
    "section3_academic_discussion": 20,  # Academic discussion
    "section4_academic_lecture": 20,  # Academic lecture
}


def generate_toefl_conversation(
    ai_client: AIClient,
    scenario: str,
    difficulty_score: int,
    item_number: int
) -> dict:
    """Generate a TOEFL conversation with 5 questions."""

    # Map difficulty to CEFR
    if difficulty_score <= 3:
        cefr = "B1"
    elif difficulty_score <= 5:
        cefr = "B2"
    elif difficulty_score <= 7:
        cefr = "C1"
    else:
        cefr = "C2"

    prompt = f"""Generate a TOEFL listening conversation.

Scenario: {scenario}
Difficulty: {difficulty_score}/10 (CEFR {cefr})
Duration: 2.5-3 minutes (approximately 400-450 words)
Speakers: 2 (Student and Professor/Staff member)

Requirements:
1. Natural conversational style with realistic dialogue
2. Include specific details, examples, or problem-solving
3. American English accent
4. Speaking speed: 140-160 words per minute
5. Clear turn-taking between speakers

Generate 5 questions following TOEFL format:
- 1 Gist-Content (main purpose of conversation)
- 2 Detail questions (specific information mentioned)
- 1 Function question (why does speaker say X)
- 1 Inference question (what can be inferred)

Return ONLY a JSON object:
{{
  "title": "Conversation title",
  "scenario": "{scenario}",
  "duration_seconds": 180,
  "word_count": 420,
  "speakers": [
    {{"name": "Student", "gender": "female"}},
    {{"name": "Professor", "gender": "male"}}
  ],
  "script": [
    {{"speaker": "Student", "text": "Hi Professor, I wanted to ask about..."}},
    {{"speaker": "Professor", "text": "Of course, what's on your mind?"}}
  ],
  "questions": [
    {{
      "question": "What is the main purpose of the conversation?",
      "type": "gist_content",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "B",
      "explanation": "..."
    }}
  ]
}}"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=2500)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        data = json.loads(text[start:end])

        # Validate
        if not data.get("script") or not data.get("questions"):
            return None

        if len(data["questions"]) != 5:
            print(f"Warning: Expected 5 questions, got {len(data['questions'])}")

        # Add metadata
        data["difficulty_score"] = difficulty_score
        data["cefr"] = cefr
        data["exam"] = "toefl"
        data["content_type"] = "conversation"

        return data

    except Exception as e:
        print(f"Error generating conversation: {e}")
        return None


def generate_toefl_lecture(
    ai_client: AIClient,
    topic: str,
    difficulty_score: int,
    item_number: int
) -> dict:
    """Generate a TOEFL lecture with 6 questions."""

    # Map difficulty to CEFR
    if difficulty_score <= 3:
        cefr = "B1"
    elif difficulty_score <= 5:
        cefr = "B2"
    elif difficulty_score <= 7:
        cefr = "C1"
    else:
        cefr = "C2"

    prompt = f"""Generate a TOEFL listening lecture.

Topic: {topic}
Difficulty: {difficulty_score}/10 (CEFR {cefr})
Duration: 4.5-5.5 minutes (approximately 700-800 words)
Speaker: 1 (Professor)

Requirements:
1. Academic lecture style with clear structure
2. Include examples, explanations, and key concepts
3. American English accent
4. Speaking speed: 140-160 words per minute
5. Natural pauses and transitions

Generate 6 questions following TOEFL format:
- 1 Main Idea (what is the lecture mainly about)
- 2 Detail questions (specific information)
- 1 Function question (why does professor mention X)
- 1 Organization question (how is information organized)
- 1 Inference question (what can be inferred)

Return ONLY a JSON object:
{{
  "title": "Lecture title",
  "topic": "{topic}",
  "duration_seconds": 300,
  "word_count": 750,
  "speaker": {{"name": "Professor", "gender": "male"}},
  "script": [
    {{"speaker": "Professor", "text": "Today we're going to discuss..."}}
  ],
  "questions": [
    {{
      "question": "What is the lecture mainly about?",
      "type": "main_idea",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "C",
      "explanation": "..."
    }}
  ]
}}"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=3500)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        data = json.loads(text[start:end])

        # Validate
        if not data.get("script") or not data.get("questions"):
            return None

        if len(data["questions"]) != 6:
            print(f"Warning: Expected 6 questions, got {len(data['questions'])}")

        # Add metadata
        data["difficulty_score"] = difficulty_score
        data["cefr"] = cefr
        data["exam"] = "toefl"
        data["content_type"] = "lecture"

        return data

    except Exception as e:
        print(f"Error generating lecture: {e}")
        return None


def generate_ielts_section(
    ai_client: AIClient,
    section_type: str,
    difficulty_score: int,
    item_number: int
) -> dict:
    """Generate an IELTS listening section with 10 questions."""

    # Map difficulty to band
    if difficulty_score <= 3:
        band = "5.0-6.0"
        cefr = "B1-B2"
    elif difficulty_score <= 6:
        band = "6.5-7.0"
        cefr = "B2-C1"
    else:
        band = "7.5-9.0"
        cefr = "C1-C2"

    # Determine section characteristics
    section_num = int(section_type.split("_")[0].replace("section", ""))

    if section_num == 1:
        speakers = 2
        context = "social/everyday situation"
        accent = "British"
    elif section_num == 2:
        speakers = 1
        context = "monologue on everyday topic"
        accent = "Australian"
    elif section_num == 3:
        speakers = 3
        context = "academic discussion"
        accent = "British"
    else:
        speakers = 1
        context = "academic lecture"
        accent = "American"

    prompt = f"""Generate an IELTS listening Section {section_num}.

Context: {context}
Difficulty: {difficulty_score}/10 (Band {band}, CEFR {cefr})
Duration: 4-5 minutes (approximately 600-700 words)
Speakers: {speakers}
Accent: {accent} English

Requirements:
1. Natural conversational/lecture style
2. Include specific details, numbers, names, dates
3. {accent} English accent
4. Speaking speed: 140-180 words per minute

Generate 10 questions using IELTS format:
- Mix of: Multiple Choice, Form Completion, Matching, Note Completion
- Questions follow the order of information in recording
- Answers are words/numbers from the recording

Return ONLY a JSON object:
{{
  "title": "Section title",
  "section_number": {section_num},
  "context": "{context}",
  "duration_seconds": 270,
  "word_count": 650,
  "accent": "{accent}",
  "speakers": [{{"name": "Speaker A", "gender": "female"}}],
  "script": [
    {{"speaker": "Speaker A", "text": "..."}}
  ],
  "questions": [
    {{
      "question": "What is the speaker's name?",
      "type": "form_completion",
      "answer": "Sarah Johnson",
      "explanation": "..."
    }}
  ]
}}"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=3500)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        data = json.loads(text[start:end])

        # Validate
        if not data.get("script") or not data.get("questions"):
            return None

        if len(data["questions"]) != 10:
            print(f"Warning: Expected 10 questions, got {len(data['questions'])}")

        # Add metadata
        data["difficulty_score"] = difficulty_score
        data["band"] = band
        data["cefr"] = cefr.split("-")[0]
        data["exam"] = "ielts"
        data["content_type"] = f"section{section_num}"

        return data

    except Exception as e:
        print(f"Error generating IELTS section: {e}")
        return None


def save_listening_to_kb(kb: KnowledgeBase, listening_data: dict) -> bool:
    """Save generated listening content to knowledge base."""
    try:
        # Create text representation
        script_text = "\n".join([f"{line['speaker']}: {line['text']}" for line in listening_data["script"]])
        chunk_id = hashlib.sha256(script_text.encode()).hexdigest()[:16]

        chunk = Chunk(
            chunk_id=chunk_id,
            source_file=f"ai_generated_{listening_data['exam']}_{listening_data['content_type']}",
            content_type="listening",
            text=script_text,
            difficulty=listening_data.get("cefr", "B2"),
            topic=listening_data.get("topic", listening_data.get("scenario", "general")),
            exam=listening_data["exam"],
            language="en",
            metadata={
                "title": listening_data.get("title", ""),
                "duration_seconds": listening_data.get("duration_seconds", 0),
                "word_count": listening_data.get("word_count", 0),
                "script": listening_data.get("script", []),
                "questions": listening_data.get("questions", []),
                "speakers": listening_data.get("speakers", listening_data.get("speaker", [])),
                "accent": listening_data.get("accent", "American"),
                "difficulty_score": listening_data.get("difficulty_score", 5),
                "estimated_time": listening_data.get("duration_seconds", 0) // 60 + 5,
                "source_quality": "ai_generated",
            }
        )

        kb.add_chunks([chunk])
        return True

    except Exception as e:
        print(f"Error saving listening to KB: {e}")
        return False


def main():
    """Main generation workflow."""
    print("=" * 70)
    print("Professional Listening Content Generation for TOEFL/IELTS")
    print("=" * 70)

    # Initialize components
    ai_client = AIClient()
    data_dir = get_data_dir()
    kb = KnowledgeBase(data_dir)

    total_generated = 0

    # Generate TOEFL conversations (60 total)
    print("\n[1/3] Generating TOEFL conversations...")
    print("-" * 70)

    for scenario, count in TOEFL_CONVERSATION_SCENARIOS.items():
        print(f"\n{scenario.replace('_', ' ').title()}: {count} conversations")

        for i in range(count):
            difficulty_score = 3 + (i % 7)
            print(f"  Conversation {i+1}/{count} (difficulty {difficulty_score}/10)...", end=" ")

            data = generate_toefl_conversation(ai_client, scenario, difficulty_score, i+1)

            if data and save_listening_to_kb(kb, data):
                total_generated += 1
                print(f"✓ ({data.get('word_count', 0)} words, {len(data.get('questions', []))} questions)")
            else:
                print("✗")

    # Generate TOEFL lectures (100 total)
    print("\n[2/3] Generating TOEFL lectures...")
    print("-" * 70)

    for topic, count in TOEFL_LECTURE_TOPICS.items():
        print(f"\n{topic.replace('_', ' ').title()}: {count} lectures")

        for i in range(count):
            difficulty_score = 3 + (i % 7)
            print(f"  Lecture {i+1}/{count} (difficulty {difficulty_score}/10)...", end=" ")

            data = generate_toefl_lecture(ai_client, topic, difficulty_score, i+1)

            if data and save_listening_to_kb(kb, data):
                total_generated += 1
                print(f"✓ ({data.get('word_count', 0)} words, {len(data.get('questions', []))} questions)")
            else:
                print("✗")

    # Generate IELTS sections (80 sets = 320 sections)
    print("\n[3/3] Generating IELTS listening sections...")
    print("-" * 70)

    for section_type, count in IELTS_SECTIONS.items():
        print(f"\n{section_type.replace('_', ' ').title()}: {count} sections")

        for i in range(count):
            difficulty_score = 3 + (i % 7)
            print(f"  Section {i+1}/{count} (difficulty {difficulty_score}/10)...", end=" ")

            data = generate_ielts_section(ai_client, section_type, difficulty_score, i+1)

            if data and save_listening_to_kb(kb, data):
                total_generated += 1
                print(f"✓ ({data.get('word_count', 0)} words, {len(data.get('questions', []))} questions)")
            else:
                print("✗")

    # Summary
    print("\n" + "=" * 70)
    print(f"Generation complete!")
    print(f"Total listening items added: {total_generated}")
    print(f"Target: 240 items (60 TOEFL conversations + 100 TOEFL lectures + 80 IELTS sections)")
    print(f"Achievement: {total_generated/240*100:.1f}%")
    print("=" * 70)


if __name__ == "__main__":
    main()
