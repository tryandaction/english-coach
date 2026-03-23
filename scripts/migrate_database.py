"""
Database migration script for existing users.

Upgrades existing databases to support new professional features:
- Vocabulary table: adds 8 new columns
- Chunks table: adds 6 new columns
- Creates new indexes for performance

Safe to run multiple times - only adds missing columns.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.srs.engine import SM2Engine
from core.knowledge_base.store import KnowledgeBase
from utils.paths import get_data_dir


def migrate_vocabulary_table(srs: SM2Engine) -> dict:
    """Migrate vocabulary table to add new professional columns."""
    print("\n[1/2] Migrating vocabulary table...")

    # Check existing columns
    existing = {r[1] for r in srs._db.execute("PRAGMA table_info(vocabulary)").fetchall()}

    migrations = [
        ("level", "INTEGER", "2"),
        ("frequency", "INTEGER", "5000"),
        ("category", "TEXT", "'general'"),
        ("difficulty_score", "INTEGER", "5"),
        ("exam_type", "TEXT", "'general'"),
        ("subject_domain", "TEXT", "'general'"),
        ("word_family", "TEXT", "''"),
        ("usage_notes", "TEXT", "''"),
    ]

    added = 0
    for col, col_type, default in migrations:
        if col not in existing:
            try:
                srs._db.execute(f"ALTER TABLE vocabulary ADD COLUMN {col} {col_type} DEFAULT {default}")
                added += 1
                print(f"  [OK] Added column: {col}")
            except Exception as e:
                print(f"  [FAIL] Failed to add {col}: {e}")

    srs._db.commit()

    if added == 0:
        print("  [INFO] All vocabulary columns already exist")

    return {"added": added, "total": len(migrations)}


def migrate_chunks_table(kb: KnowledgeBase) -> dict:
    """Migrate chunks table to add new metadata columns."""
    print("\n[2/2] Migrating chunks table...")

    # Check existing columns
    existing = {r[1] for r in kb._sql.execute("PRAGMA table_info(chunks)").fetchall()}

    migrations = [
        ("word_count", "INTEGER", "0"),
        ("estimated_time", "INTEGER", "0"),
        ("subject_category", "TEXT", "'general'"),
        ("difficulty_score", "INTEGER", "5"),
        ("question_types_json", "TEXT", "'[]'"),
        ("source_quality", "TEXT", "'ai_generated'"),
    ]

    added = 0
    for col, col_type, default in migrations:
        if col not in existing:
            try:
                kb._sql.execute(f"ALTER TABLE chunks ADD COLUMN {col} {col_type} DEFAULT {default}")
                added += 1
                print(f"  [OK] Added column: {col}")
            except Exception as e:
                print(f"  [FAIL] Failed to add {col}: {e}")

    # Create new indexes if they don't exist
    indexes = [
        ("idx_chunks_subject", "chunks", "subject_category"),
        ("idx_chunks_difficulty_score", "chunks", "difficulty_score"),
    ]

    for idx_name, table, column in indexes:
        try:
            kb._sql.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
            print(f"  [OK] Created index: {idx_name}")
        except Exception as e:
            print(f"  [INFO] Index {idx_name} already exists or failed: {e}")

    kb._sql.commit()

    if added == 0:
        print("  [INFO] All chunks columns already exist")

    return {"added": added, "total": len(migrations)}


def update_existing_vocabulary(srs: SM2Engine) -> dict:
    """Update existing vocabulary with inferred metadata."""
    print("\n[3/3] Updating existing vocabulary metadata...")

    # Map CEFR difficulty to level
    cefr_to_level = {
        "A1": 1, "A2": 1,
        "B1": 2, "B2": 2,
        "C1": 3, "C2": 4
    }

    # Map source to exam_type
    source_to_exam = {
        "toefl": "toefl",
        "ielts": "ielts",
        "gre": "gre",
        "cet": "cet",
    }

    rows = srs._db.execute(
        "SELECT word_id, difficulty, source FROM vocabulary WHERE level IS NULL OR level = 2"
    ).fetchall()

    updated = 0
    for row in rows:
        word_id = row["word_id"]
        difficulty = row["difficulty"] or "B2"
        source = row["source"] or "builtin"

        # Infer level from CEFR
        level = cefr_to_level.get(difficulty, 2)

        # Infer exam_type from source
        exam_type = "general"
        for key, value in source_to_exam.items():
            if key in source.lower():
                exam_type = value
                break

        # Infer difficulty_score from CEFR
        difficulty_score = {
            "A1": 2, "A2": 3,
            "B1": 4, "B2": 5,
            "C1": 7, "C2": 9
        }.get(difficulty, 5)

        try:
            srs._db.execute(
                """UPDATE vocabulary
                   SET level = ?, exam_type = ?, difficulty_score = ?
                   WHERE word_id = ?""",
                (level, exam_type, difficulty_score, word_id)
            )
            updated += 1
        except Exception as e:
            print(f"  [FAIL] Failed to update {word_id}: {e}")

    srs._db.commit()

    print(f"  [OK] Updated {updated} vocabulary entries with inferred metadata")

    return {"updated": updated}


def update_existing_chunks(kb: KnowledgeBase) -> dict:
    """Update existing chunks with inferred metadata."""
    print("\n[4/4] Updating existing chunks metadata...")

    rows = kb._sql.execute(
        "SELECT chunk_id, text, content_type, difficulty, exam FROM chunks WHERE word_count = 0"
    ).fetchall()

    updated = 0
    for row in rows:
        chunk_id = row["chunk_id"]
        text = row["text"]
        content_type = row["content_type"]
        difficulty = row["difficulty"] or "B2"
        exam = row["exam"] or "general"

        # Calculate word count
        word_count = len(text.split())

        # Estimate time based on content type
        if content_type == "reading":
            estimated_time = 20  # 20 minutes for reading
        elif content_type == "listening":
            estimated_time = 15  # 15 minutes for listening
        else:
            estimated_time = 10

        # Infer difficulty_score from CEFR
        difficulty_score = {
            "A1": 2, "A2": 3,
            "B1": 4, "B2": 5,
            "C1": 7, "C2": 9
        }.get(difficulty, 5)

        try:
            kb._sql.execute(
                """UPDATE chunks
                   SET word_count = ?, estimated_time = ?, difficulty_score = ?
                   WHERE chunk_id = ?""",
                (word_count, estimated_time, difficulty_score, chunk_id)
            )
            updated += 1
        except Exception as e:
            print(f"  [FAIL] Failed to update {chunk_id}: {e}")

    kb._sql.commit()

    print(f"  [OK] Updated {updated} chunks with inferred metadata")

    return {"updated": updated}


def main():
    """Run database migration."""
    print("=" * 70)
    print("English Coach Database Migration")
    print("=" * 70)
    print("\nThis script will upgrade your database to support new features.")
    print("It is safe to run multiple times - only missing columns will be added.")
    print("\nStarting migration...\n")

    data_dir = get_data_dir()

    # Initialize engines
    srs = SM2Engine(data_dir / "user.db")
    kb = KnowledgeBase(data_dir)

    # Run migrations
    vocab_result = migrate_vocabulary_table(srs)
    chunks_result = migrate_chunks_table(kb)

    # Update existing data
    vocab_update = update_existing_vocabulary(srs)
    chunks_update = update_existing_chunks(kb)

    # Summary
    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Vocabulary columns added: {vocab_result['added']}/{vocab_result['total']}")
    print(f"Chunks columns added: {chunks_result['added']}/{chunks_result['total']}")
    print(f"Vocabulary entries updated: {vocab_update['updated']}")
    print(f"Chunks updated: {chunks_update['updated']}")
    print("\n[SUCCESS] Migration completed successfully!")
    print("\nYour database is now ready for the new professional features.")
    print("=" * 70)


if __name__ == "__main__":
    main()
