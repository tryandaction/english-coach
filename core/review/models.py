from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReviewCandidate:
    word_id: str
    word: str
    status: str
    due_for_review: str = ""
    wrong_count: int = 0
    success_count: int = 0
    source: str = ""
    topic: str = "general"
    difficulty: str = "B1"
    tags: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    priority_reason: str = ""


@dataclass
class ReviewPoolSummary:
    due_total: int = 0
    forgetting_total: int = 0
    candidate_total: int = 0
    recommended_batch_size: int = 8
    known_words: int = 0
    unsure_words: int = 0
    unknown_words: int = 0
