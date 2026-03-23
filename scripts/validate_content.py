"""
Content validation pipeline for quality assurance.

Validates generated content against professional standards:
- Word count validation
- Question count validation
- Metadata completeness
- Answer key accuracy
- Difficulty calibration
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.knowledge_base.store import KnowledgeBase
from core.srs.engine import SM2Engine
from core.vocab.catalog import parse_vocab_markdown
from gui.deps import get_content_dir, _sync_builtin_content
from utils.paths import get_data_dir


class ContentValidator:
    """Validates content quality and completeness."""

    def __init__(self, kb: KnowledgeBase, srs: SM2Engine):
        self.kb = kb
        self.srs = srs
        self.errors = []
        self.warnings = []

    def validate_all(self) -> dict:
        """Run all validation checks."""
        print("=" * 70)
        print("Content Validation Pipeline")
        print("=" * 70)

        self.errors = []
        self.warnings = []

        # Validate vocabulary
        print("\n[1/4] Validating vocabulary...")
        vocab_stats = self.validate_vocabulary()

        # Validate reading passages
        print("\n[2/4] Validating reading passages...")
        reading_stats = self.validate_reading_passages()

        # Validate listening content
        print("\n[3/4] Validating listening content...")
        listening_stats = self.validate_listening_content()

        # Validate metadata completeness
        print("\n[4/4] Validating metadata completeness...")
        metadata_stats = self.validate_metadata()

        # Summary
        print("\n" + "=" * 70)
        print("Validation Summary")
        print("=" * 70)
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")

        if self.errors:
            print("\nErrors:")
            for error in self.errors[:10]:  # Show first 10
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more")

        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings[:10]:  # Show first 10
                print(f"  - {warning}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more")

        return {
            "vocabulary": vocab_stats,
            "reading": reading_stats,
            "listening": listening_stats,
            "metadata": metadata_stats,
            "errors": self.errors,
            "warnings": self.warnings,
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
        }

    def validate_vocabulary(self) -> dict:
        """Validate vocabulary entries."""
        rows = self.srs._db.execute(
            "SELECT word_id, word, definition_en, definition_zh, level, difficulty_score, exam_type FROM vocabulary"
        ).fetchall()

        if not rows:
            return self._validate_vocabulary_sources()

        total = len(rows)
        missing_definition = 0
        missing_level = 0
        missing_exam_type = 0
        invalid_difficulty = 0

        for row in rows:
            word_id = row["word_id"]
            word = row["word"]

            # Check required fields
            if not row["definition_en"]:
                missing_definition += 1
                self.errors.append(f"Vocabulary '{word}' missing English definition")

            if not row["level"] or row["level"] < 1 or row["level"] > 4:
                missing_level += 1
                self.warnings.append(f"Vocabulary '{word}' has invalid level: {row['level']}")

            if not row["exam_type"]:
                missing_exam_type += 1
                self.warnings.append(f"Vocabulary '{word}' missing exam_type")

            if not row["difficulty_score"] or row["difficulty_score"] < 1 or row["difficulty_score"] > 10:
                invalid_difficulty += 1
                self.warnings.append(f"Vocabulary '{word}' has invalid difficulty_score: {row['difficulty_score']}")

        print(f"  Total vocabulary: {total}")
        print(f"  Missing definitions: {missing_definition}")
        print(f"  Invalid levels: {missing_level}")
        print(f"  Missing exam types: {missing_exam_type}")
        print(f"  Invalid difficulty scores: {invalid_difficulty}")

        return {
            "total": total,
            "missing_definition": missing_definition,
            "invalid_level": missing_level,
            "missing_exam_type": missing_exam_type,
            "invalid_difficulty": invalid_difficulty,
        }

    def _validate_vocabulary_sources(self) -> dict:
        """Validate builtin vocabulary source files when DB has not been ingested yet."""
        content_dir = get_content_dir()
        vocab_dirs = [
            content_dir / "vocab",
            content_dir / "vocab_selected",
            content_dir / "vocab_expanded",
        ]

        total = 0
        missing_definition = 0
        missing_exam_type = 0
        invalid_difficulty = 0

        for vocab_dir in vocab_dirs:
            if not vocab_dir.exists():
                continue
            for md_file in sorted(vocab_dir.glob("*.md")):
                fm, rows = parse_vocab_markdown(md_file)
                if not rows:
                    continue
                exam = str(fm.get("exam", "")).strip()
                difficulty = str(fm.get("difficulty", "")).strip().upper()
                if exam == "":
                    missing_exam_type += 1
                    self.warnings.append(f"Vocab file '{md_file.name}' missing exam frontmatter")
                if difficulty and not self._is_valid_difficulty_marker(difficulty):
                    invalid_difficulty += 1
                    self.warnings.append(f"Vocab file '{md_file.name}' has invalid difficulty: {difficulty}")
                for row in rows:
                    total += 1
                    word = row.get("word", "")
                    if not row.get("definition_en"):
                        missing_definition += 1
                        self.errors.append(f"Vocabulary '{word}' missing English definition in source library")

        if total == 0:
            self.errors.append("No vocabulary content found in source library")

        print(f"  Total vocabulary: {total} (source library)")
        print(f"  Missing definitions: {missing_definition}")
        print(f"  Missing exam types: {missing_exam_type}")
        print(f"  Invalid difficulty markers: {invalid_difficulty}")

        return {
            "total": total,
            "missing_definition": missing_definition,
            "invalid_level": 0,
            "missing_exam_type": missing_exam_type,
            "invalid_difficulty": invalid_difficulty,
            "source_mode": True,
        }

    @staticmethod
    def _is_valid_difficulty_marker(value: str) -> bool:
        parts = [part.strip() for part in value.split("-") if part.strip()]
        return bool(parts) and all(part in {"A1", "A2", "B1", "B2", "C1", "C2"} for part in parts)

    def validate_reading_passages(self) -> dict:
        """Validate reading passages."""
        rows = self.kb._sql.execute(
            """SELECT rowid, chunk_id, source_file, text, difficulty, exam, word_count,
                      estimated_time, subject_category, difficulty_score,
                      question_types_json, metadata_json
               FROM chunks
               WHERE content_type = 'reading'
               ORDER BY rowid ASC"""
        ).fetchall()

        def passage_key(row) -> str:
            source_file = str(row["source_file"] or "").strip()
            if source_file and source_file != "ai_warehouse":
                return f"source:{source_file}"
            return f"chunk:{row['chunk_id']}"

        grouped: dict[str, list] = {}
        for row in rows:
            grouped.setdefault(passage_key(row), []).append(row)

        total = len(grouped)
        toefl_count = 0
        ielts_count = 0
        word_count_errors = 0
        question_count_errors = 0
        missing_metadata = 0

        if total == 0:
            self.errors.append("No reading passages found in knowledge base")

        for group_rows in grouped.values():
            label = group_rows[0]["chunk_id"][:8]
            exam = group_rows[0]["exam"]
            paragraphs: list[str] = []
            questions: list[dict] = []
            seen_questions: set[str] = set()
            subject_values: list[str] = []

            for row in group_rows:
                text = str(row["text"] or "").strip()
                if text and (not paragraphs or paragraphs[-1] != text):
                    paragraphs.append(text)

                subject = str(row["subject_category"] or "").strip()
                if subject:
                    subject_values.append(subject)

                try:
                    metadata = json.loads(row["metadata_json"] or "{}")
                except json.JSONDecodeError:
                    missing_metadata += 1
                    self.errors.append(f"Passage {label} has invalid metadata JSON")
                    continue

                raw_questions = metadata.get("questions", [])
                if isinstance(raw_questions, str):
                    try:
                        raw_questions = json.loads(raw_questions)
                    except Exception:
                        raw_questions = []

                if isinstance(raw_questions, list):
                    for question in raw_questions:
                        if not isinstance(question, dict):
                            continue
                        key = str(
                            question.get("id")
                            or question.get("question")
                            or json.dumps(question, sort_keys=True, ensure_ascii=True)
                        )
                        if key in seen_questions:
                            continue
                        seen_questions.add(key)
                        questions.append(question)

            passage_text = "\n\n".join(paragraphs).strip()
            word_count = len(passage_text.split())

            # Count by exam
            if exam == "toefl":
                toefl_count += 1
                # TOEFL: 700±50 words
                if word_count < 650 or word_count > 750:
                    word_count_errors += 1
                    self.warnings.append(f"TOEFL passage {label} has {word_count} words (expected 650-750)")

            elif exam == "ielts":
                ielts_count += 1
                # IELTS: 800-900 words
                if word_count < 800 or word_count > 900:
                    word_count_errors += 1
                    self.warnings.append(f"IELTS passage {label} has {word_count} words (expected 800-900)")

            if questions and exam == "toefl" and len(questions) != 10:
                question_count_errors += 1
                self.warnings.append(f"TOEFL passage {label} has {len(questions)} questions (expected 10)")

            elif questions and exam == "ielts" and (len(questions) < 13 or len(questions) > 14):
                question_count_errors += 1
                self.warnings.append(f"IELTS passage {label} has {len(questions)} questions (expected 13-14)")

            # Check required metadata
            if not subject_values:
                missing_metadata += 1
                self.warnings.append(f"Passage {label} missing subject_category")

        print(f"  Total passages: {total}")
        print(f"  TOEFL passages: {toefl_count}")
        print(f"  IELTS passages: {ielts_count}")
        print(f"  Word count errors: {word_count_errors}")
        print(f"  Question count errors: {question_count_errors}")
        print(f"  Missing metadata: {missing_metadata}")

        return {
            "total": total,
            "toefl": toefl_count,
            "ielts": ielts_count,
            "word_count_errors": word_count_errors,
            "question_count_errors": question_count_errors,
            "missing_metadata": missing_metadata,
        }

    def validate_listening_content(self) -> dict:
        """Validate listening source files used by the runtime listening page."""
        listening_dir = get_content_dir() / "listening"
        files = sorted(listening_dir.glob("*.md")) if listening_dir.exists() else []

        total = len(files)
        toefl_count = 0
        ielts_count = 0
        missing_script = 0
        missing_questions = 0
        invalid_duration = 0

        if total == 0:
            self.errors.append("No listening items found in source library")

        for md_file in files:
            try:
                text = md_file.read_text(encoding="utf-8").replace("\r\n", "\n")
            except Exception as exc:
                self.errors.append(f"Listening file '{md_file.name}' unreadable: {exc}")
                continue

            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if not fm_match:
                self.errors.append(f"Listening file '{md_file.name}' missing frontmatter")
                continue

            meta = {}
            for line in fm_match.group(1).splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()

            exam = meta.get("exam", "general")
            body = text[fm_match.end():]
            marker = re.search(r"\nquestions:\s*\n", body)
            script_text = body[:marker.start()].strip() if marker else body.strip()
            questions_text = body[marker.end():].strip() if marker else ""

            script = []
            for line in script_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^([AB]):\s*(.+)$", line)
                if m:
                    script.append({"speaker": m.group(1), "text": m.group(2).strip()})

            if not script:
                missing_script += 1
                self.errors.append(f"Listening '{md_file.name}' missing script")

            questions = []
            if questions_text:
                try:
                    parsed_questions = json.loads(questions_text)
                    if isinstance(parsed_questions, list):
                        questions = parsed_questions
                except json.JSONDecodeError:
                    self.errors.append(f"Listening '{md_file.name}' has invalid questions JSON")

            if not questions:
                missing_questions += 1
                self.errors.append(f"Listening '{md_file.name}' missing questions")

            duration = max(60, len(" ".join(item["text"] for item in script).split()) * 2)
            if exam == "toefl":
                toefl_count += 1
                if duration < 150 or duration > 330:
                    invalid_duration += 1
                    self.warnings.append(f"TOEFL listening '{md_file.name}' estimated duration {duration}s (expected 150-330s)")
            elif exam == "ielts":
                ielts_count += 1
                if duration < 240 or duration > 300:
                    invalid_duration += 1
                    self.warnings.append(f"IELTS listening '{md_file.name}' estimated duration {duration}s (expected 240-300s)")

        print(f"  Total listening items: {total}")
        print(f"  TOEFL items: {toefl_count}")
        print(f"  IELTS items: {ielts_count}")
        print(f"  Missing scripts: {missing_script}")
        print(f"  Missing questions: {missing_questions}")
        print(f"  Invalid durations: {invalid_duration}")

        return {
            "total": total,
            "toefl": toefl_count,
            "ielts": ielts_count,
            "missing_script": missing_script,
            "missing_questions": missing_questions,
            "invalid_duration": invalid_duration,
        }

    def validate_metadata(self) -> dict:
        """Validate metadata completeness across all content."""
        rows = self.kb._sql.execute(
            """SELECT chunk_id, content_type, difficulty, exam,
                      word_count, estimated_time, subject_category,
                      difficulty_score, source_quality
               FROM chunks"""
        ).fetchall()

        total = len(rows)
        missing_difficulty = 0
        missing_exam = 0
        missing_subject = 0
        missing_difficulty_score = 0
        missing_source_quality = 0

        if total == 0:
            self.errors.append("No content items found in knowledge base")

        for row in rows:
            chunk_id = row["chunk_id"]

            if not row["difficulty"]:
                missing_difficulty += 1
                self.warnings.append(f"Content {chunk_id[:8]} missing difficulty (CEFR level)")

            if not row["exam"]:
                missing_exam += 1
                self.warnings.append(f"Content {chunk_id[:8]} missing exam type")

            if not row["subject_category"]:
                missing_subject += 1
                self.warnings.append(f"Content {chunk_id[:8]} missing subject_category")

            if not row["difficulty_score"]:
                missing_difficulty_score += 1
                self.warnings.append(f"Content {chunk_id[:8]} missing difficulty_score")

            if not row["source_quality"]:
                missing_source_quality += 1
                self.warnings.append(f"Content {chunk_id[:8]} missing source_quality")

        print(f"  Total content items: {total}")
        print(f"  Missing difficulty: {missing_difficulty}")
        print(f"  Missing exam type: {missing_exam}")
        print(f"  Missing subject: {missing_subject}")
        print(f"  Missing difficulty score: {missing_difficulty_score}")
        print(f"  Missing source quality: {missing_source_quality}")

        return {
            "total": total,
            "missing_difficulty": missing_difficulty,
            "missing_exam": missing_exam,
            "missing_subject": missing_subject,
            "missing_difficulty_score": missing_difficulty_score,
            "missing_source_quality": missing_source_quality,
        }


def main():
    """Run content validation."""
    data_dir = get_data_dir()
    kb = KnowledgeBase(data_dir)
    srs = SM2Engine(data_dir / "user.db")
    _sync_builtin_content(kb, data_dir)

    validator = ContentValidator(kb, srs)
    results = validator.validate_all()

    # Save results to file
    output_file = data_dir / "validation_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nValidation report saved to: {output_file}")

    # Exit with error code if there are errors
    if results["total_errors"] > 0:
        print("\n[FAIL] Validation failed with errors!")
        sys.exit(1)
    else:
        print("\n[OK] Validation passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
