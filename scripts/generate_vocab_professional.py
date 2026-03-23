"""
Professional vocabulary generation script for TOEFL/IELTS preparation.

Generates 15,000+ words with professional categorization:
- TOEFL: 8,000 words (TPO 1-78 high-frequency)
- IELTS: 7,000 words (Cambridge 4-18)
- Subject-specific: biology, geology, astronomy, art history, archaeology
- 4-level grading system (Level 1-4)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.client import AIClient
from core.srs.engine import SM2Engine
from utils.paths import get_data_dir


# Level mapping: CEFR to 1-4 scale
CEFR_TO_LEVEL = {
    "A1": 1, "A2": 1,
    "B1": 2, "B2": 2,
    "C1": 3, "C2": 4
}

# Subject domains for TOEFL
TOEFL_SUBJECTS = {
    "biology": 800,
    "geology": 600,
    "astronomy": 500,
    "art_history": 400,
    "archaeology": 300,
    "general_academic": 2200,
}

# Topics for IELTS
IELTS_TOPICS = {
    "environment": 1000,
    "technology": 1000,
    "education": 1000,
    "health": 1000,
    "society": 1000,
    "general_academic": 2000,
}


def generate_toefl_words_batch(
    ai_client: AIClient,
    subject: str,
    count: int,
    difficulty_range: tuple[int, int] = (1, 10)
) -> list[dict]:
    """Generate a batch of TOEFL words for a specific subject."""

    prompt = f"""Generate {count} high-frequency TOEFL academic vocabulary words for the subject: {subject}.

Requirements:
1. Words should be from TPO (TOEFL Practice Online) materials
2. Include academic words commonly used in {subject} contexts
3. Difficulty range: {difficulty_range[0]}-{difficulty_range[1]} (1=basic, 10=advanced)
4. Each word must include:
   - word (lowercase)
   - definition_en (clear, concise English definition)
   - definition_zh (Chinese translation)
   - example (sentence using the word in academic context)
   - part_of_speech (noun/verb/adjective/adverb/etc.)
   - synonyms (comma-separated, 2-3 words)
   - collocations (common word combinations, 2-3 examples)
   - difficulty_score (1-10)
   - frequency (estimated rank 1-10000, lower = more common)

Return ONLY a JSON array of word objects. No markdown, no explanation.

Example format:
[
  {{
    "word": "photosynthesis",
    "definition_en": "the process by which green plants use sunlight to synthesize nutrients",
    "definition_zh": "光合作用",
    "example": "Photosynthesis is essential for plant growth and oxygen production.",
    "part_of_speech": "noun",
    "synonyms": "carbon fixation, light reaction",
    "collocations": "photosynthesis process, photosynthesis rate, undergo photosynthesis",
    "difficulty_score": 7,
    "frequency": 3500
  }}
]"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=4000)
        # Extract JSON from response
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            print(f"Warning: No JSON array found in response for {subject}")
            return []

        json_text = text[start:end]
        words = json.loads(json_text)

        # Add metadata
        for word in words:
            word["exam_type"] = "toefl"
            word["subject_domain"] = subject
            word["category"] = "academic"
            word["source"] = f"toefl_{subject}"

            # Map difficulty_score to CEFR and level
            score = word.get("difficulty_score", 5)
            if score <= 3:
                word["difficulty"] = "B1"
                word["level"] = 2
            elif score <= 5:
                word["difficulty"] = "B2"
                word["level"] = 2
            elif score <= 7:
                word["difficulty"] = "C1"
                word["level"] = 3
            else:
                word["difficulty"] = "C2"
                word["level"] = 4

        return words

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON for {subject}: {e}")
        return []
    except Exception as e:
        print(f"Error generating words for {subject}: {e}")
        return []


def generate_ielts_words_batch(
    ai_client: AIClient,
    topic: str,
    count: int,
    difficulty_range: tuple[int, int] = (1, 10)
) -> list[dict]:
    """Generate a batch of IELTS words for a specific topic."""

    prompt = f"""Generate {count} high-frequency IELTS academic vocabulary words for the topic: {topic}.

Requirements:
1. Words should be from Cambridge IELTS 4-18 materials
2. Include both British and American English variants where applicable
3. Focus on Academic module vocabulary
4. Difficulty range: {difficulty_range[0]}-{difficulty_range[1]} (1=basic, 10=advanced)
5. Each word must include:
   - word (lowercase, British spelling if different)
   - definition_en (clear, concise English definition)
   - definition_zh (Chinese translation)
   - example (sentence using the word in academic context)
   - part_of_speech (noun/verb/adjective/adverb/etc.)
   - synonyms (comma-separated, 2-3 words)
   - collocations (common word combinations, 2-3 examples)
   - difficulty_score (1-10)
   - frequency (estimated rank 1-10000, lower = more common)
   - usage_notes (British vs American spelling, register, etc. if applicable)

Return ONLY a JSON array of word objects. No markdown, no explanation.

Example format:
[
  {{
    "word": "globalisation",
    "definition_en": "the process by which businesses develop international influence",
    "definition_zh": "全球化",
    "example": "Globalisation has transformed international trade and communication.",
    "part_of_speech": "noun",
    "synonyms": "internationalization, worldwide integration",
    "collocations": "economic globalisation, globalisation process, effects of globalisation",
    "difficulty_score": 6,
    "frequency": 2500,
    "usage_notes": "British spelling; American: globalization"
  }}
]"""

    try:
        response = ai_client._call(prompt, model=ai_client._default_model, max_tokens=4000)
        # Extract JSON from response
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            print(f"Warning: No JSON array found in response for {topic}")
            return []

        json_text = text[start:end]
        words = json.loads(json_text)

        # Add metadata
        for word in words:
            word["exam_type"] = "ielts"
            word["subject_domain"] = topic
            word["category"] = "academic"
            word["source"] = f"ielts_{topic}"

            # Map difficulty_score to CEFR and level
            score = word.get("difficulty_score", 5)
            if score <= 3:
                word["difficulty"] = "B1"
                word["level"] = 2
            elif score <= 5:
                word["difficulty"] = "B2"
                word["level"] = 2
            elif score <= 7:
                word["difficulty"] = "C1"
                word["level"] = 3
            else:
                word["difficulty"] = "C2"
                word["level"] = 4

        return words

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON for {topic}: {e}")
        return []
    except Exception as e:
        print(f"Error generating words for {topic}: {e}")
        return []


def save_words_to_db(engine: SM2Engine, words: list[dict]) -> int:
    """Save generated words to vocabulary database."""
    added = 0
    for word_data in words:
        try:
            engine.add_word(
                word=word_data.get("word", ""),
                definition_en=word_data.get("definition_en", ""),
                definition_zh=word_data.get("definition_zh", ""),
                example=word_data.get("example", ""),
                part_of_speech=word_data.get("part_of_speech", ""),
                synonyms=word_data.get("synonyms", ""),
                collocations=word_data.get("collocations", ""),
                difficulty=word_data.get("difficulty", "B2"),
                source=word_data.get("source", "ai_generated"),
                level=word_data.get("level", 2),
                frequency=word_data.get("frequency", 5000),
                category=word_data.get("category", "academic"),
                difficulty_score=word_data.get("difficulty_score", 5),
                exam_type=word_data.get("exam_type", "general"),
                subject_domain=word_data.get("subject_domain", "general"),
                usage_notes=word_data.get("usage_notes", ""),
            )
            added += 1
        except Exception as e:
            print(f"Error adding word '{word_data.get('word', 'unknown')}': {e}")

    return added


def main():
    """Main generation workflow."""
    print("=" * 60)
    print("Professional Vocabulary Generation for TOEFL/IELTS")
    print("=" * 60)

    # Initialize components
    ai_client = AIClient()
    data_dir = get_data_dir()
    engine = SM2Engine(data_dir / "user.db")

    total_generated = 0

    # Generate TOEFL vocabulary (8,000 words target)
    print("\n[1/2] Generating TOEFL vocabulary...")
    print("-" * 60)

    for subject, count in TOEFL_SUBJECTS.items():
        print(f"\nGenerating {count} words for {subject}...")

        # Generate in batches of 50 to avoid token limits
        batch_size = 50
        subject_words = []

        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            print(f"  Batch {i//batch_size + 1}: {batch_count} words...", end=" ")

            batch_words = generate_toefl_words_batch(
                ai_client, subject, batch_count
            )
            subject_words.extend(batch_words)
            print(f"✓ ({len(batch_words)} generated)")

        # Save to database
        added = save_words_to_db(engine, subject_words)
        total_generated += added
        print(f"  → Added {added}/{len(subject_words)} words to database")

    # Generate IELTS vocabulary (7,000 words target)
    print("\n[2/2] Generating IELTS vocabulary...")
    print("-" * 60)

    for topic, count in IELTS_TOPICS.items():
        print(f"\nGenerating {count} words for {topic}...")

        # Generate in batches of 50
        batch_size = 50
        topic_words = []

        for i in range(0, count, batch_size):
            batch_count = min(batch_size, count - i)
            print(f"  Batch {i//batch_size + 1}: {batch_count} words...", end=" ")

            batch_words = generate_ielts_words_batch(
                ai_client, topic, batch_count
            )
            topic_words.extend(batch_words)
            print(f"✓ ({len(batch_words)} generated)")

        # Save to database
        added = save_words_to_db(engine, topic_words)
        total_generated += added
        print(f"  → Added {added}/{len(topic_words)} words to database")

    # Summary
    print("\n" + "=" * 60)
    print(f"Generation complete!")
    print(f"Total words added to database: {total_generated}")
    print(f"Target: 15,000 words")
    print(f"Achievement: {total_generated/15000*100:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
