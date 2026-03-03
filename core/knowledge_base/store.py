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
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = str(data_dir / "teaching.db")
        self._sql = sqlite3.connect(self._db_path, check_same_thread=False)
        self._sql.row_factory = sqlite3.Row
        self._sql.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

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
                metadata_json TEXT
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
        self._sql.commit()

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
                    exam, language, text, metadata_json)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
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
