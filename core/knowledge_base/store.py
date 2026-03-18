"""
Knowledge base: pure SQLite with FTS5 full-text search.
No ChromaDB, no embedding model, no network required.
FTS5 provides fast keyword + phrase search across all teaching content.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from core.ingestion.pipeline import Chunk, CEFR_LEVELS


class KnowledgeBase:
    """
    Single SQLite database with two tables:
    - chunks: structured metadata (content_type, difficulty, exam, topic)
    - chunks_fts: FTS5 virtual table for full-text keyword search

    Retrieval strategy:
    - get_by_type(): structured filter → RANDOM() → fast, no search needed
    - search(): FTS5 keyword search with optional structured filters
    Both methods support i+1 difficulty filtering and seen-content exclusion.
    """

    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        self._db_path = str(self._resolve_db_path(data_dir))
        self._sql = sqlite3.connect(self._db_path, check_same_thread=False)
        self._sql.row_factory = sqlite3.Row
        self._sql.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    @classmethod
    def _resolve_db_path(cls, data_dir: Path) -> Path:
        """Resolve the active teaching DB path with legacy `kb/` compatibility."""
        if not data_dir.exists():
            data_dir.mkdir(parents=True, exist_ok=True)

        direct_db = data_dir / "teaching.db"
        legacy_dir = data_dir / "kb"
        legacy_db = legacy_dir / "teaching.db"

        # If caller already passed the legacy kb directory, keep using it.
        if data_dir.name == "kb":
            return direct_db

        if direct_db.exists() and not legacy_db.exists():
            return direct_db

        if legacy_db.exists() and not direct_db.exists():
            legacy_dir.mkdir(parents=True, exist_ok=True)
            return legacy_db

        if legacy_db.exists() and direct_db.exists():
            direct_count = cls._get_chunk_count(direct_db)
            legacy_count = cls._get_chunk_count(legacy_db)
            if legacy_count > direct_count:
                return legacy_db

        return direct_db

    @staticmethod
    def _get_chunk_count(db_path: Path) -> int:
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
            conn.close()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._sql.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id      TEXT PRIMARY KEY,
                source_file   TEXT,
                content_type  TEXT,
                difficulty    TEXT,
                topic         TEXT,
                exam          TEXT,
                language      TEXT,
                text          TEXT,
                metadata_json TEXT,
                word_count    INTEGER DEFAULT 0,
                estimated_time INTEGER DEFAULT 0,
                subject_category TEXT DEFAULT 'general',
                difficulty_score INTEGER DEFAULT 5,
                question_types_json TEXT DEFAULT '[]',
                source_quality TEXT DEFAULT 'ai_generated'
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(content_type);
            CREATE INDEX IF NOT EXISTS idx_chunks_diff ON chunks(difficulty);
            CREATE INDEX IF NOT EXISTS idx_chunks_exam ON chunks(exam);

            -- FTS5 virtual table for full-text search
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(
                chunk_id UNINDEXED,
                content_type UNINDEXED,
                difficulty UNINDEXED,
                exam UNINDEXED,
                text,
                content='chunks',
                content_rowid='rowid',
                tokenize='unicode61'
            );

            -- Keep FTS in sync via triggers
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, chunk_id, content_type, difficulty, exam, text)
                VALUES (new.rowid, new.chunk_id, new.content_type, new.difficulty, new.exam, new.text);
            END;

            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, content_type, difficulty, exam, text)
                VALUES ('delete', old.rowid, old.chunk_id, old.content_type, old.difficulty, old.exam, old.text);
            END;
        """)

        # Migrate: add new columns to existing chunks tables
        existing = {r[1] for r in self._sql.execute("PRAGMA table_info(chunks)").fetchall()}
        for col, col_type, default in [
            ("word_count", "INTEGER", "0"),
            ("estimated_time", "INTEGER", "0"),
            ("subject_category", "TEXT", "'general'"),
            ("difficulty_score", "INTEGER", "5"),
            ("question_types_json", "TEXT", "'[]'"),
            ("source_quality", "TEXT", "'ai_generated'"),
        ]:
            if col not in existing:
                self._sql.execute(f"ALTER TABLE chunks ADD COLUMN {col} {col_type} DEFAULT {default}")

        self._sql.execute("CREATE INDEX IF NOT EXISTS idx_chunks_subject ON chunks(subject_category)")
        self._sql.execute("CREATE INDEX IF NOT EXISTS idx_chunks_difficulty_score ON chunks(difficulty_score)")
        self._repair_builtin_content_rows()

        self._sql.commit()

    def _repair_builtin_content_rows(self) -> None:
        self._sql.execute(
            """UPDATE chunks
               SET content_type = 'listening'
               WHERE content_type = 'general'
                 AND LOWER(REPLACE(source_file, '\\', '/')) LIKE '%/content/listening/%'"""
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[Chunk], batch_size: int = 200) -> int:
        """Store chunks in SQLite + FTS5. Returns count of new chunks added."""
        new_chunks = [c for c in chunks if not self._exists(c.chunk_id)]
        if not new_chunks:
            return 0

        for i in range(0, len(new_chunks), batch_size):
            batch = new_chunks[i : i + batch_size]
            self._sql.executemany(
                """INSERT OR IGNORE INTO chunks
                   (chunk_id, source_file, content_type, difficulty, topic,
                    exam, language, text, metadata_json, word_count,
                    estimated_time, subject_category, difficulty_score,
                    question_types_json, source_quality)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        c.chunk_id,
                        c.source_file,
                        c.content_type.value,
                        c.difficulty,
                        c.topic,
                        c.exam,
                        c.language,
                        c.text,
                        json.dumps(c.metadata),
                        len(c.text.split()),
                        self._estimated_time(c.content_type.value, c.text),
                        self._subject_category(c),
                        self._difficulty_score(c.difficulty),
                        json.dumps(self._question_types(c.metadata)),
                        self._source_quality(c),
                    )
                    for c in batch
                ],
            )
            self._sql.commit()

        return len(new_chunks)

    def _exists(self, chunk_id: str) -> bool:
        return self._sql.execute(
            "SELECT 1 FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone() is not None

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        content_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        exam: Optional[str] = None,
        exclude_ids: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[sqlite3.Row]:
        """
        FTS5 full-text search with structured filters.
        Falls back to get_by_type() if query is empty.
        """
        if not query.strip():
            return self.get_by_type(
                content_type=content_type or "reading",
                difficulty=difficulty,
                exam=exam,
                exclude_ids=exclude_ids,
                limit=limit,
            )

        # Build FTS query — escape special chars, support multi-word
        fts_query = " OR ".join(
            f'"{w}"' for w in query.split() if len(w) > 2
        ) or query

        conditions = ["f.chunk_id = c.chunk_id"]
        params: list = [fts_query]

        if content_type:
            conditions.append("c.content_type = ?")
            params.append(content_type)
        if difficulty:
            levels = self._i_plus_one(difficulty)
            conditions.append(f"c.difficulty IN ({','.join('?'*len(levels))})")
            params.extend(levels)
        if exam and exam != "general":
            conditions.append("c.exam IN (?, 'general')")
            params.append(exam)
        if exclude_ids:
            conditions.append(
                f"c.chunk_id NOT IN ({','.join('?'*len(exclude_ids))})"
            )
            params.extend(exclude_ids)

        params.append(limit)
        sql = (
            f"SELECT c.* FROM chunks_fts f "
            f"JOIN chunks c ON {' AND '.join(conditions)} "
            f"WHERE chunks_fts MATCH ? "
            f"ORDER BY rank LIMIT ?"
        )
        # Reorder: FTS MATCH must reference the virtual table directly
        sql = (
            f"SELECT c.* FROM chunks c "
            f"JOIN chunks_fts f ON f.chunk_id = c.chunk_id "
            f"WHERE chunks_fts MATCH ?"
        )
        if content_type:
            sql += " AND c.content_type = ?"
        if difficulty:
            levels = self._i_plus_one(difficulty)
            sql += f" AND c.difficulty IN ({','.join('?'*len(levels))})"
        if exam and exam != "general":
            sql += " AND c.exam IN (?, 'general')"
        if exclude_ids:
            sql += f" AND c.chunk_id NOT IN ({','.join('?'*len(exclude_ids))})"
        sql += " ORDER BY rank LIMIT ?"

        try:
            return self._sql.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS query syntax error — fall back to structured retrieval
            return self.get_by_type(
                content_type=content_type or "reading",
                difficulty=difficulty,
                exam=exam,
                exclude_ids=exclude_ids,
                limit=limit,
            )

    def get_by_type(
        self,
        content_type: str,
        difficulty: Optional[str] = None,
        exam: Optional[str] = None,
        exclude_ids: Optional[list[str]] = None,
        limit: int = 10,
        random_order: bool = True,
    ) -> list[sqlite3.Row]:
        """Structured SQL retrieval — fast, no search needed."""
        conditions = ["content_type = ?"]
        params: list = [content_type]

        if difficulty:
            levels = self._i_plus_one(difficulty)
            conditions.append(f"difficulty IN ({','.join('?'*len(levels))})")
            params.extend(levels)

        if exam and exam != "general":
            conditions.append("exam IN (?, 'general')")
            params.append(exam)

        if exclude_ids:
            conditions.append(
                f"chunk_id NOT IN ({','.join('?'*len(exclude_ids))})"
            )
            params.extend(exclude_ids)

        order = "RANDOM()" if random_order else "rowid ASC"
        sql = (
            f"SELECT * FROM chunks WHERE {' AND '.join(conditions)} "
            f"ORDER BY {order} LIMIT ?"
        )
        params.append(limit)
        return self._sql.execute(sql, params).fetchall()

    # Keep semantic_search as alias for search() — modes use this name
    def semantic_search(
        self,
        query: str,
        content_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        exam: Optional[str] = None,
        language: str = "en",
        exclude_ids: Optional[list[str]] = None,
        limit: int = 5,
    ) -> list[dict]:
        rows = self.search(
            query=query,
            content_type=content_type,
            difficulty=difficulty,
            exam=exam,
            exclude_ids=exclude_ids,
            limit=limit,
        )
        return [
            {
                "chunk_id": r["chunk_id"],
                "text": r["text"],
                "metadata": {
                    "content_type": r["content_type"],
                    "difficulty": r["difficulty"],
                    "topic": r["topic"],
                    "exam": r["exam"],
                },
                "distance": 0.0,
            }
            for r in rows
        ]

    def get_chunk(self, chunk_id: str) -> Optional[sqlite3.Row]:
        return self._sql.execute(
            "SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone()

    def count(self, content_type: Optional[str] = None) -> int:
        if content_type:
            return self._sql.execute(
                "SELECT COUNT(*) FROM chunks WHERE content_type=?", (content_type,)
            ).fetchone()[0]
        return self._sql.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _i_plus_one(cefr: str) -> list[str]:
        """Return current level + one above (Krashen i+1)."""
        try:
            idx = CEFR_LEVELS.index(cefr)
        except ValueError:
            idx = 2  # default B1
        return CEFR_LEVELS[idx : min(len(CEFR_LEVELS), idx + 2)]

    @staticmethod
    def _difficulty_score(cefr: str) -> int:
        return {
            "A1": 2,
            "A2": 3,
            "B1": 4,
            "B2": 5,
            "C1": 7,
            "C2": 9,
        }.get(str(cefr or "").upper(), 5)

    @staticmethod
    def _estimated_time(content_type: str, text: str) -> int:
        words = max(1, len(str(text or "").split()))
        if content_type == "reading":
            return max(3, round(words / 180))
        if content_type == "listening":
            return max(2, round(words / 160))
        return max(1, round(words / 200))

    @staticmethod
    def _subject_category(chunk: Chunk) -> str:
        meta = chunk.metadata or {}
        for key in ("subject_category", "subject", "domain"):
            value = str(meta.get(key, "")).strip()
            if value:
                return value
        return str(chunk.topic or "general")

    @staticmethod
    def _question_types(metadata: dict) -> list[str]:
        questions = metadata.get("questions") if isinstance(metadata, dict) else None
        if isinstance(questions, str):
            try:
                questions = json.loads(questions)
            except Exception:
                questions = []
        if not isinstance(questions, list):
            return []
        result = []
        for item in questions:
            if not isinstance(item, dict):
                continue
            qtype = str(item.get("type", "")).strip()
            if qtype and qtype not in result:
                result.append(qtype)
        return result

    @staticmethod
    def _source_quality(chunk: Chunk) -> str:
        meta = chunk.metadata or {}
        if meta.get("ai_generated"):
            return "ai_generated"
        return "builtin"
