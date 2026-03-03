"""
SM-2 spaced repetition engine — pure Python, zero API calls.
Manages vocabulary flashcard scheduling for long-term retention.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class Card:
    card_id: str
    user_id: str
    word_id: str
    word: str
    definition_en: str
    definition_zh: str
    example: str
    # SM-2 state
    interval: int = 1        # days until next review
    repetitions: int = 0     # consecutive correct answers
    easiness: float = 2.5    # ease factor (EF), floor 1.3
    due_date: str = ""        # YYYY-MM-DD
    total_reviews: int = 0
    correct_reviews: int = 0

    @property
    def accuracy(self) -> float:
        if self.total_reviews == 0:
            return 0.0
        return self.correct_reviews / self.total_reviews


class SM2Engine:
    """
    SM-2 algorithm implementation.

    Quality scale shown to user:
      1 = Complete blackout
      2 = Wrong, but recognized answer
      3 = Correct with major difficulty
      4 = Correct with hesitation
      5 = Perfect, instant recall
    """

    def __init__(self, db_path: str | Path):
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                word_id        TEXT PRIMARY KEY,
                word           TEXT UNIQUE,
                definition_en  TEXT,
                definition_zh  TEXT,
                example        TEXT,
                topic          TEXT DEFAULT 'general',
                difficulty     TEXT DEFAULT 'B1',
                source         TEXT DEFAULT 'builtin',
                synonyms       TEXT DEFAULT '',
                antonyms       TEXT DEFAULT '',
                derivatives    TEXT DEFAULT '',
                collocations   TEXT DEFAULT '',
                context_sentence TEXT DEFAULT '',
                part_of_speech TEXT DEFAULT '',
                pronunciation  TEXT DEFAULT '',
                enriched       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS srs_cards (
                card_id        TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                word_id        TEXT NOT NULL,
                interval       INTEGER DEFAULT 1,
                repetitions    INTEGER DEFAULT 0,
                easiness       REAL    DEFAULT 2.5,
                due_date       TEXT,
                last_reviewed  TEXT,
                total_reviews  INTEGER DEFAULT 0,
                correct_reviews INTEGER DEFAULT 0,
                UNIQUE(user_id, word_id)
            );

            CREATE TABLE IF NOT EXISTS srs_reviews (
                review_id      TEXT PRIMARY KEY,
                card_id        TEXT,
                user_id        TEXT,
                quality        INTEGER,
                response_ms    INTEGER DEFAULT 0,
                reviewed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS word_books (
                book_id        TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                name           TEXT NOT NULL,
                description    TEXT DEFAULT '',
                color          TEXT DEFAULT '#4f8ef7',
                icon           TEXT DEFAULT '📖',
                created_at     TEXT,
                updated_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS word_book_words (
                id             TEXT PRIMARY KEY,
                book_id        TEXT NOT NULL,
                word_id        TEXT NOT NULL,
                added_at       TEXT,
                UNIQUE(book_id, word_id),
                FOREIGN KEY(book_id) REFERENCES word_books(book_id) ON DELETE CASCADE,
                FOREIGN KEY(word_id) REFERENCES vocabulary(word_id)
            );

            CREATE INDEX IF NOT EXISTS idx_srs_due
                ON srs_cards(user_id, due_date);
            CREATE INDEX IF NOT EXISTS idx_word_books_user
                ON word_books(user_id);
            CREATE INDEX IF NOT EXISTS idx_word_book_words_book
                ON word_book_words(book_id);

            CREATE TABLE IF NOT EXISTS word_tags (
                id       TEXT PRIMARY KEY,
                user_id  TEXT NOT NULL,
                word_id  TEXT NOT NULL,
                tag      TEXT NOT NULL,
                created_at TEXT,
                UNIQUE(user_id, word_id, tag),
                FOREIGN KEY(word_id) REFERENCES vocabulary(word_id)
            );
            CREATE INDEX IF NOT EXISTS idx_word_tags_user
                ON word_tags(user_id, tag);
        """)
        # Migrate: add new columns to existing vocabulary tables
        existing = {r[1] for r in self._db.execute("PRAGMA table_info(vocabulary)").fetchall()}
        for col, default in [
            ("synonyms",         "''"),
            ("antonyms",         "''"),
            ("derivatives",      "''"),
            ("collocations",     "''"),
            ("context_sentence", "''"),
            ("part_of_speech",   "''"),
            ("pronunciation",    "''"),
            ("enriched",         "0"),
        ]:
            if col not in existing:
                self._db.execute(f"ALTER TABLE vocabulary ADD COLUMN {col} TEXT DEFAULT {default}")
        self._db.commit()

    # ------------------------------------------------------------------
    # Vocabulary management
    # ------------------------------------------------------------------

    def add_word(
        self,
        word: str,
        definition_en: str,
        definition_zh: str = "",
        example: str = "",
        topic: str = "general",
        difficulty: str = "B1",
        source: str = "builtin",
        synonyms: str = "",
        antonyms: str = "",
        derivatives: str = "",
        collocations: str = "",
        context_sentence: str = "",
        part_of_speech: str = "",
        pronunciation: str = "",
    ) -> str:
        """Insert word into vocabulary table. Returns word_id."""
        word_id = uuid.uuid4().hex[:12]
        self._db.execute(
            """INSERT OR IGNORE INTO vocabulary
               (word_id, word, definition_en, definition_zh, example, topic, difficulty, source,
                synonyms, antonyms, derivatives, collocations, context_sentence, part_of_speech, pronunciation)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (word_id, word.lower(), definition_en, definition_zh, example, topic, difficulty, source,
             synonyms, antonyms, derivatives, collocations, context_sentence, part_of_speech, pronunciation),
        )
        self._db.commit()
        row = self._db.execute(
            "SELECT word_id FROM vocabulary WHERE word=?", (word.lower(),)
        ).fetchone()
        return row["word_id"]

    def update_word_fields(self, word_id: str, **fields) -> None:
        """Update enrichment fields on an existing vocabulary entry."""
        allowed = {"definition_en", "definition_zh", "example", "synonyms", "antonyms",
                   "derivatives", "collocations", "context_sentence", "part_of_speech",
                   "pronunciation", "enriched"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        sets = ", ".join(f"{k}=?" for k in updates)
        self._db.execute(
            f"UPDATE vocabulary SET {sets} WHERE word_id=?",
            list(updates.values()) + [word_id],
        )
        self._db.commit()

    def enroll_words(self, user_id: str, word_ids: list[str]) -> int:
        """Add words to a user's SRS deck (skip already enrolled). Returns count added."""
        today = date.today().isoformat()
        added = 0
        for wid in word_ids:
            card_id = uuid.uuid4().hex[:16]
            try:
                self._db.execute(
                    """INSERT OR IGNORE INTO srs_cards
                       (card_id, user_id, word_id, due_date)
                       VALUES (?,?,?,?)""",
                    (card_id, user_id, wid, today),
                )
                added += self._db.execute("SELECT changes()").fetchone()[0]
            except sqlite3.IntegrityError:
                pass
        self._db.commit()
        return added

    # ------------------------------------------------------------------
    # Review flow
    # ------------------------------------------------------------------

    def get_due_cards(self, user_id: str, limit: int = 20) -> list[Card]:
        """Return cards due for review today, ordered by urgency."""
        today = date.today().isoformat()
        rows = self._db.execute(
            """SELECT c.card_id, c.user_id, c.word_id,
                      v.word, v.definition_en, v.definition_zh, v.example,
                      c.interval, c.repetitions, c.easiness, c.due_date,
                      c.total_reviews, c.correct_reviews
               FROM srs_cards c
               JOIN vocabulary v ON c.word_id = v.word_id
               WHERE c.user_id = ? AND c.due_date <= ?
               ORDER BY c.due_date ASC, c.easiness ASC
               LIMIT ?""",
            (user_id, today, limit),
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def get_new_words(
        self,
        user_id: str,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        exam: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Return vocabulary words not yet in user's deck."""
        conditions = [
            "v.word_id NOT IN (SELECT word_id FROM srs_cards WHERE user_id=?)"
        ]
        params: list = [user_id]

        if topic:
            conditions.append("v.topic = ?")
            params.append(topic)
        if difficulty:
            conditions.append("v.difficulty = ?")
            params.append(difficulty)
        if exam and exam != "general":
            source_prefix = {
                "toefl": "toefl_%",
                "gre": "gre_%",
                "ielts": "ielts_%",
                "cet": "cet%",
            }.get(exam)
            if source_prefix:
                conditions.append("v.source LIKE ?")
                params.append(source_prefix)

        params.append(limit)
        rows = self._db.execute(
            f"""SELECT v.word_id, v.word, v.definition_en, v.definition_zh,
                       v.example, v.topic, v.difficulty, v.source
                FROM vocabulary v
                WHERE {' AND '.join(conditions)}
                ORDER BY RANDOM() LIMIT ?""",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def review_card(self, card_id: str, quality: int, response_ms: int = 0) -> dict:
        """
        Apply SM-2 algorithm. quality must be 1–5.
        Returns dict with next_due, interval_days, message.
        """
        quality = max(1, min(5, quality))
        row = self._db.execute(
            "SELECT * FROM srs_cards WHERE card_id=?", (card_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Card {card_id} not found")

        interval = row["interval"]
        reps = row["repetitions"]
        ef = row["easiness"]
        correct = quality >= 3

        if correct:
            if reps == 0:
                new_interval = 1
            elif reps == 1:
                new_interval = 6
            else:
                new_interval = round(interval * ef)
            new_reps = reps + 1
            new_ef = max(1.3, ef + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        else:
            new_interval = 1
            new_reps = 0
            new_ef = ef  # EF unchanged on failure

        due = (date.today() + timedelta(days=new_interval)).isoformat()
        now = datetime.now().isoformat()

        self._db.execute(
            """UPDATE srs_cards
               SET interval=?, repetitions=?, easiness=?, due_date=?,
                   last_reviewed=?,
                   total_reviews = total_reviews + 1,
                   correct_reviews = correct_reviews + ?
               WHERE card_id=?""",
            (new_interval, new_reps, new_ef, due, now, 1 if correct else 0, card_id),
        )
        self._db.execute(
            """INSERT INTO srs_reviews (review_id, card_id, user_id, quality, response_ms, reviewed_at)
               VALUES (?,?,?,?,?,?)""",
            (uuid.uuid4().hex, card_id, row["user_id"], quality, response_ms, now),
        )
        self._db.commit()

        return {
            "correct": correct,
            "next_due": due,
            "interval_days": new_interval,
            "new_ef": round(new_ef, 2),
            "message": self._interval_label(new_interval),
        }

    # ------------------------------------------------------------------
    # Word Books
    # ------------------------------------------------------------------

    def create_word_book(self, user_id: str, name: str, description: str = "", color: str = "#4f8ef7", icon: str = "📖") -> dict:
        book_id = uuid.uuid4().hex[:16]
        now = datetime.now().isoformat()
        self._db.execute(
            """INSERT INTO word_books (book_id, user_id, name, description, color, icon, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (book_id, user_id, name, description, color, icon, now, now),
        )
        self._db.commit()
        return {"book_id": book_id, "user_id": user_id, "name": name,
                "description": description, "color": color, "icon": icon,
                "created_at": now, "updated_at": now, "word_count": 0}

    def get_word_books(self, user_id: str) -> list[dict]:
        rows = self._db.execute(
            """SELECT b.*, COUNT(w.id) as word_count
               FROM word_books b
               LEFT JOIN word_book_words w ON b.book_id = w.book_id
               WHERE b.user_id = ?
               GROUP BY b.book_id
               ORDER BY b.created_at DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_word_book(self, book_id: str, user_id: str) -> Optional[dict]:
        row = self._db.execute(
            """SELECT b.*, COUNT(w.id) as word_count
               FROM word_books b
               LEFT JOIN word_book_words w ON b.book_id = w.book_id
               WHERE b.book_id = ? AND b.user_id = ?
               GROUP BY b.book_id""",
            (book_id, user_id),
        ).fetchone()
        return dict(row) if row else None

    def update_word_book(self, book_id: str, user_id: str, **fields) -> bool:
        allowed = {"name", "description", "color", "icon"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k}=?" for k in updates)
        self._db.execute(
            f"UPDATE word_books SET {sets} WHERE book_id=? AND user_id=?",
            list(updates.values()) + [book_id, user_id],
        )
        self._db.commit()
        return self._db.execute("SELECT changes()").fetchone()[0] > 0

    def delete_word_book(self, book_id: str, user_id: str) -> bool:
        self._db.execute(
            "DELETE FROM word_book_words WHERE book_id=?", (book_id,)
        )
        self._db.execute(
            "DELETE FROM word_books WHERE book_id=? AND user_id=?", (book_id, user_id)
        )
        self._db.commit()
        return self._db.execute("SELECT changes()").fetchone()[0] > 0

    def check_word_in_book(self, book_id: str, word: str) -> Optional[str]:
        """Check if a word already exists in the book. Returns word_id if found, None otherwise."""
        row = self._db.execute(
            """SELECT v.word_id FROM word_book_words w
               JOIN vocabulary v ON w.word_id = v.word_id
               WHERE w.book_id = ? AND LOWER(v.word) = LOWER(?)""",
            (book_id, word.strip()),
        ).fetchone()
        return row["word_id"] if row else None

    def add_word_to_book(self, book_id: str, word_id: str) -> bool:
        try:
            self._db.execute(
                """INSERT OR IGNORE INTO word_book_words (id, book_id, word_id, added_at)
                   VALUES (?,?,?,?)""",
                (uuid.uuid4().hex[:16], book_id, word_id, datetime.now().isoformat()),
            )
            self._db.commit()
            return True
        except Exception:
            return False

    def remove_word_from_book(self, book_id: str, word_id: str) -> bool:
        self._db.execute(
            "DELETE FROM word_book_words WHERE book_id=? AND word_id=?", (book_id, word_id)
        )
        self._db.commit()
        return self._db.execute("SELECT changes()").fetchone()[0] > 0

    def get_book_words(self, book_id: str, user_id: str, limit: int = 200, offset: int = 0) -> list[dict]:
        rows = self._db.execute(
            """SELECT v.*, w.added_at,
                      c.card_id, c.interval, c.repetitions, c.due_date,
                      c.total_reviews, c.correct_reviews
               FROM word_book_words w
               JOIN vocabulary v ON w.word_id = v.word_id
               LEFT JOIN srs_cards c ON c.word_id = v.word_id AND c.user_id = ?
               WHERE w.book_id = ?
               ORDER BY w.added_at DESC
               LIMIT ? OFFSET ?""",
            (user_id, book_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_due_cards_for_book(self, user_id: str, book_id: str, limit: int = 20) -> list[Card]:
        today = date.today().isoformat()
        rows = self._db.execute(
            """SELECT c.card_id, c.user_id, c.word_id,
                      v.word, v.definition_en, v.definition_zh, v.example,
                      c.interval, c.repetitions, c.easiness, c.due_date,
                      c.total_reviews, c.correct_reviews
               FROM srs_cards c
               JOIN vocabulary v ON c.word_id = v.word_id
               JOIN word_book_words w ON w.word_id = c.word_id AND w.book_id = ?
               WHERE c.user_id = ? AND c.due_date <= ?
               ORDER BY c.due_date ASC, c.easiness ASC
               LIMIT ?""",
            (book_id, user_id, today, limit),
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def get_new_words_for_book(self, user_id: str, book_id: str, limit: int = 20) -> list[dict]:
        rows = self._db.execute(
            """SELECT v.word_id, v.word, v.definition_en, v.definition_zh,
                      v.example, v.topic, v.difficulty, v.source
               FROM word_book_words w
               JOIN vocabulary v ON w.word_id = v.word_id
               WHERE w.book_id = ?
                 AND v.word_id NOT IN (SELECT word_id FROM srs_cards WHERE user_id=?)
               LIMIT ?""",
            (book_id, user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_vocabulary(self, query: str, limit: int = 20) -> list[dict]:
        q = f"%{query.lower()}%"
        rows = self._db.execute(
            """SELECT word_id, word, definition_en, definition_zh, part_of_speech, source
               FROM vocabulary
               WHERE LOWER(word) LIKE ? OR LOWER(definition_en) LIKE ?
               ORDER BY CASE WHEN LOWER(word) = ? THEN 0
                             WHEN LOWER(word) LIKE ? THEN 1 ELSE 2 END
               LIMIT ?""",
            (q, q, query.lower(), f"{query.lower()}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Word Tags
    # ------------------------------------------------------------------

    BUILTIN_TAGS = {"star", "error", "writing", "listening"}

    def set_tag(self, user_id: str, word_id: str, tag: str, active: bool) -> None:
        """Add or remove a tag on a word for a user."""
        if active:
            self._db.execute(
                """INSERT OR IGNORE INTO word_tags (id, user_id, word_id, tag, created_at)
                   VALUES (?,?,?,?,?)""",
                (uuid.uuid4().hex[:16], user_id, word_id, tag, datetime.now().isoformat()),
            )
        else:
            self._db.execute(
                "DELETE FROM word_tags WHERE user_id=? AND word_id=? AND tag=?",
                (user_id, word_id, tag),
            )
        self._db.commit()

    def get_tags(self, user_id: str, word_id: str) -> list[str]:
        """Return all tags for a word."""
        rows = self._db.execute(
            "SELECT tag FROM word_tags WHERE user_id=? AND word_id=?",
            (user_id, word_id),
        ).fetchall()
        return [r["tag"] for r in rows]

    def get_tagged_words(self, user_id: str, tag: str, limit: int = 200) -> list[dict]:
        """Return vocabulary words with a given tag."""
        rows = self._db.execute(
            """SELECT v.*, t.created_at as tagged_at,
                      c.card_id, c.interval, c.repetitions, c.due_date
               FROM word_tags t
               JOIN vocabulary v ON t.word_id = v.word_id
               LEFT JOIN srs_cards c ON c.word_id = v.word_id AND c.user_id = t.user_id
               WHERE t.user_id = ? AND t.tag = ?
               ORDER BY t.created_at DESC
               LIMIT ?""",
            (user_id, tag, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_tags(self, user_id: str) -> list[dict]:
        """Return all distinct tags with counts."""
        rows = self._db.execute(
            """SELECT tag, COUNT(*) as count FROM word_tags
               WHERE user_id=? GROUP BY tag ORDER BY count DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def deck_stats(self, user_id: str) -> dict:
        today = date.today().isoformat()
        total = self._db.execute(
            "SELECT COUNT(*) FROM srs_cards WHERE user_id=?", (user_id,)
        ).fetchone()[0]
        due = self._db.execute(
            "SELECT COUNT(*) FROM srs_cards WHERE user_id=? AND due_date<=?",
            (user_id, today),
        ).fetchone()[0]
        mature = self._db.execute(
            "SELECT COUNT(*) FROM srs_cards WHERE user_id=? AND interval>=21",
            (user_id,),
        ).fetchone()[0]
        return {"total": total, "due_today": due, "mature": mature}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> Card:
        return Card(
            card_id=row["card_id"],
            user_id=row["user_id"],
            word_id=row["word_id"],
            word=row["word"],
            definition_en=row["definition_en"],
            definition_zh=row["definition_zh"] or "",
            example=row["example"] or "",
            interval=row["interval"],
            repetitions=row["repetitions"],
            easiness=row["easiness"],
            due_date=row["due_date"] or "",
            total_reviews=row["total_reviews"],
            correct_reviews=row["correct_reviews"],
        )

    @staticmethod
    def _interval_label(days: int) -> str:
        if days == 1:
            return "明天再见 · See you tomorrow"
        if days <= 7:
            return f"{days}天后复习 · Review in {days} days"
        if days <= 30:
            return f"{days//7}周后复习 · Review in {days//7} week(s)"
        return f"{days//30}个月后复习 · Review in {days//30} month(s)"
