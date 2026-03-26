from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LearnerMemoryFact:
    fact_id: str
    user_id: str
    fact_type: str
    fact_key: str
    value: dict | list | str | int | float | bool | None
    source: str = "manual"
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class LearningEvent:
    event_id: str
    user_id: str
    event_type: str
    mode: str = ""
    session_id: str = ""
    word_id: str = ""
    payload: dict = field(default_factory=dict)
    event_at: str = ""


@dataclass
class VocabMemoryState:
    user_id: str
    word_id: str
    word: str = ""
    status: str = "unknown"
    source: str = ""
    topic: str = "general"
    difficulty: str = "B1"
    tags: list[str] = field(default_factory=list)
    wrong_count: int = 0
    success_count: int = 0
    last_seen_at: str = ""
    due_for_review: str = ""
    updated_at: str = ""


@dataclass
class DailyMemorySnapshot:
    user_id: str
    memory_date: str
    summary: dict = field(default_factory=dict)
    updated_at: str = ""
