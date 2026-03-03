"""
User model: profile, skill tracking, CEFR level inference.
Pure SQLite — zero API calls.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

SKILLS = [
    "vocab_academic",
    "vocab_general",
    "vocab_physics",
    "reading_speed",
    "reading_comprehension",
    "writing_coherence",
    "writing_grammar",
    "writing_vocabulary",
    "grammar_articles",
    "grammar_tense",
    "grammar_preposition",
    "speaking_structure",
    "speaking_vocabulary",
]

# Map skill groups to CEFR composite weights
_SKILL_WEIGHTS = {
    "vocab_academic": 0.10,
    "vocab_general": 0.10,
    "vocab_physics": 0.05,
    "reading_speed": 0.10,
    "reading_comprehension": 0.20,
    "writing_coherence": 0.10,
    "writing_grammar": 0.10,
    "writing_vocabulary": 0.10,
    "grammar_articles": 0.05,
    "grammar_tense": 0.05,
    "grammar_preposition": 0.05,
}


@dataclass
class UserProfile:
    user_id: str
    name: str
    cefr_level: str = "B1"
    target_exam: str = "toefl"       # toefl / gre / ielts / cet / general
    stem_domain: str = "physics"     # physics / engineering / cs / general
    daily_new_words: int = 20
    session_minutes: int = 30
    total_sessions: int = 0
    total_study_minutes: int = 0
    created_at: str = ""
    weak_areas: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "UserProfile":
        return cls(**json.loads(data))


class UserModel:
    """
    Tracks user profile, per-skill scores, session history.
    All operations are pure SQLite — no AI cost.
    """

    def __init__(self, db_path: str | Path):
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()
        # Migrate: add content_json and starred columns if not present
        for col_sql in [
            "ALTER TABLE sessions ADD COLUMN content_json TEXT DEFAULT NULL",
            "ALTER TABLE sessions ADD COLUMN starred INTEGER DEFAULT 0",
        ]:
            try:
                self._db.execute(col_sql)
            except Exception:
                pass
        self._db.commit()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      TEXT PRIMARY KEY,
                profile_json TEXT,
                updated_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS skill_scores (
                user_id      TEXT,
                skill        TEXT,
                score        REAL    DEFAULT 0.5,
                sample_count INTEGER DEFAULT 0,
                last_updated TEXT,
                PRIMARY KEY (user_id, skill)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                user_id      TEXT,
                mode         TEXT,
                duration_sec INTEGER DEFAULT 0,
                items_done   INTEGER DEFAULT 0,
                accuracy     REAL    DEFAULT 0.0,
                started_at   TEXT,
                ended_at     TEXT
            );

            CREATE TABLE IF NOT EXISTS seen_content (
                user_id   TEXT,
                chunk_id  TEXT,
                seen_at   TEXT,
                PRIMARY KEY (user_id, chunk_id)
            );
        """)
        self._db.commit()

    # ------------------------------------------------------------------
    # Profile CRUD
    # ------------------------------------------------------------------

    def create_profile(self, name: str, **kwargs) -> UserProfile:
        profile = UserProfile(
            user_id=uuid.uuid4().hex[:12],
            name=name,
            created_at=datetime.now().isoformat(),
            **kwargs,
        )
        self._save_profile(profile)
        # Initialise all skills at 0.5 (neutral)
        for skill in SKILLS:
            self._db.execute(
                "INSERT OR IGNORE INTO skill_scores (user_id, skill, score, sample_count, last_updated) "
                "VALUES (?,?,0.5,0,?)",
                (profile.user_id, skill, datetime.now().isoformat()),
            )
        self._db.commit()
        return profile

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        row = self._db.execute(
            "SELECT profile_json FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        if not row:
            return None
        return UserProfile.from_json(row["profile_json"])

    def get_first_profile(self) -> Optional[UserProfile]:
        """Convenience: return the first (and usually only) user."""
        row = self._db.execute(
            "SELECT profile_json FROM users ORDER BY rowid ASC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return UserProfile.from_json(row["profile_json"])

    def update_profile(self, profile: UserProfile) -> None:
        profile.weak_areas = self.get_weak_areas(profile.user_id)
        profile.cefr_level = self.infer_cefr(profile.user_id)
        self._save_profile(profile)

    def _save_profile(self, profile: UserProfile) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO users (user_id, profile_json, updated_at) VALUES (?,?,?)",
            (profile.user_id, profile.to_json(), datetime.now().isoformat()),
        )
        self._db.commit()

    # ------------------------------------------------------------------
    # Skill tracking
    # ------------------------------------------------------------------

    def record_answer(
        self,
        user_id: str,
        skill: str,
        correct: bool,
    ) -> None:
        """Update skill score using exponential moving average."""
        if skill not in SKILLS:
            return
        row = self._db.execute(
            "SELECT score, sample_count FROM skill_scores WHERE user_id=? AND skill=?",
            (user_id, skill),
        ).fetchone()

        new_val = 1.0 if correct else 0.0
        if row:
            old_score, count = row["score"], row["sample_count"]
            # Adaptive alpha: more weight to recent performance as data grows
            alpha = max(0.1, min(0.4, 2.0 / (count + 2)))
            updated = alpha * new_val + (1 - alpha) * old_score
            self._db.execute(
                "UPDATE skill_scores SET score=?, sample_count=?, last_updated=? "
                "WHERE user_id=? AND skill=?",
                (updated, count + 1, datetime.now().isoformat(), user_id, skill),
            )
        else:
            self._db.execute(
                "INSERT INTO skill_scores (user_id, skill, score, sample_count, last_updated) "
                "VALUES (?,?,?,1,?)",
                (user_id, skill, new_val, datetime.now().isoformat()),
            )
        self._db.commit()

    def get_skill_scores(self, user_id: str) -> dict[str, float]:
        rows = self._db.execute(
            "SELECT skill, score FROM skill_scores WHERE user_id=?", (user_id,)
        ).fetchall()
        return {r["skill"]: round(r["score"], 3) for r in rows}

    def get_weak_areas(self, user_id: str, threshold: float = 0.60) -> list[str]:
        """Return skills below threshold with >= 3 samples, sorted weakest first."""
        rows = self._db.execute(
            "SELECT skill FROM skill_scores "
            "WHERE user_id=? AND score < ? AND sample_count >= 3 "
            "ORDER BY score ASC LIMIT 5",
            (user_id, threshold),
        ).fetchall()
        return [r["skill"] for r in rows]

    def infer_cefr(self, user_id: str) -> str:
        """
        Weighted composite of skill scores → CEFR level.
        Pure statistics, no AI.
        """
        scores = self.get_skill_scores(user_id)
        total_weight = sum(_SKILL_WEIGHTS.values())
        composite = sum(
            scores.get(skill, 0.5) * w for skill, w in _SKILL_WEIGHTS.items()
        ) / total_weight

        thresholds = [
            (0.35, "A1"), (0.48, "A2"), (0.62, "B1"),
            (0.75, "B2"), (0.88, "C1"),
        ]
        for threshold, level in thresholds:
            if composite < threshold:
                return level
        return "C2"

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------

    def start_session(self, user_id: str, mode: str) -> str:
        session_id = uuid.uuid4().hex[:16]
        self._db.execute(
            "INSERT INTO sessions (session_id, user_id, mode, started_at) VALUES (?,?,?,?)",
            (session_id, user_id, mode, datetime.now().isoformat()),
        )
        self._db.commit()
        return session_id

    def end_session(
        self,
        session_id: str,
        duration_sec: int,
        items_done: int,
        accuracy: float,
        content_json: str | None = None,
    ) -> None:
        self._db.execute(
            "UPDATE sessions SET duration_sec=?, items_done=?, accuracy=?, ended_at=?, content_json=? "
            "WHERE session_id=?",
            (duration_sec, items_done, accuracy, datetime.now().isoformat(), content_json, session_id),
        )
        # Update total study time on profile
        row = self._db.execute(
            "SELECT user_id FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row:
            profile = self.get_profile(row["user_id"])
            if profile:
                profile.total_sessions += 1
                profile.total_study_minutes += duration_sec // 60
                self._save_profile(profile)
        self._db.commit()

    # ------------------------------------------------------------------
    # Seen content tracking (for deduplication)
    # ------------------------------------------------------------------

    def mark_seen(self, user_id: str, chunk_ids: list[str]) -> None:
        now = datetime.now().isoformat()
        self._db.executemany(
            "INSERT OR IGNORE INTO seen_content (user_id, chunk_id, seen_at) VALUES (?,?,?)",
            [(user_id, cid, now) for cid in chunk_ids],
        )
        self._db.commit()

    def get_seen_ids(self, user_id: str) -> list[str]:
        rows = self._db.execute(
            "SELECT chunk_id FROM seen_content WHERE user_id=?", (user_id,)
        ).fetchall()
        return [r["chunk_id"] for r in rows]

    # ------------------------------------------------------------------
    # Progress summary
    # ------------------------------------------------------------------

    def progress_summary(self, user_id: str) -> dict:
        profile = self.get_profile(user_id)
        scores = self.get_skill_scores(user_id)
        weak = self.get_weak_areas(user_id)
        sessions = self._db.execute(
            "SELECT COUNT(*), SUM(items_done), AVG(accuracy) FROM sessions WHERE user_id=?",
            (user_id,),
        ).fetchone()

        # Streak: count consecutive days with at least one completed session
        streak = self._calc_streak(user_id)

        return {
            "name": profile.name if profile else "Unknown",
            "cefr_level": profile.cefr_level if profile else "B1",
            "target_exam": profile.target_exam if profile else "general",
            "total_sessions": sessions[0] or 0,
            "total_items": sessions[1] or 0,
            "avg_accuracy": round((sessions[2] or 0) * 100, 1),
            "skill_scores": scores,
            "weak_areas": weak,
            "streak_days": streak,
        }

    def _calc_streak(self, user_id: str) -> int:
        """Count consecutive calendar days with at least one ended session."""
        from datetime import date, timedelta
        rows = self._db.execute(
            "SELECT DISTINCT date(ended_at) as day FROM sessions "
            "WHERE user_id=? AND ended_at IS NOT NULL "
            "ORDER BY day DESC",
            (user_id,),
        ).fetchall()
        if not rows:
            return 0
        days = {r["day"] for r in rows}
        streak = 0
        check = date.today()
        while check.isoformat() in days:
            streak += 1
            check -= timedelta(days=1)
        return streak
