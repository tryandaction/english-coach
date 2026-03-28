"""Vocab flashcard API — session state machine wrapping SM2Engine."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.vocab.catalog import (
    derive_subject,
    normalize_difficulty,
    normalize_exam_type,
    normalize_word,
    parse_vocab_markdown,
    scan_content_library,
    sync_builtin_vocabulary,
)
from gui.deps import _CONFIG_PATH, get_components, get_content_dir, load_config

router = APIRouter(prefix="/api/vocab", tags=["vocab"])

_CONTENT_ROOT = get_content_dir()
_VOCAB_CONTENT_DIRS = [
    _CONTENT_ROOT / "vocab",
    _CONTENT_ROOT / "vocab_selected",
    _CONTENT_ROOT / "vocab_expanded",
]


@dataclass
class VocabSession:
    session_id: str
    user_id: str
    db_session_id: str
    cards: list
    index: int = 0
    correct: int = 0
    start_time: float = field(default_factory=time.time)


_sessions: dict[str, VocabSession] = {}


def _normalize_exam_type(value: str) -> str:
    return normalize_exam_type(value)


def _normalize_difficulty(value: str) -> str:
    return normalize_difficulty(value)


def _derive_subject(topic: str, source: str) -> str:
    return derive_subject(topic, source)


def _parse_vocab_markdown(md_file: Path) -> tuple[dict, list[dict]]:
    return parse_vocab_markdown(md_file=md_file)


def _lookup_existing_word(srs, word: str):
    return srs._db.execute(
        "SELECT * FROM vocabulary WHERE word=?",
        (normalize_word(word),),
    ).fetchone()


def _extract_word_updates(payload: BaseModel, *, include_word: bool = False, allow_blank: bool = False) -> dict[str, str]:
    editable_fields = (
        "word",
        "definition_en",
        "definition_zh",
        "example",
        "part_of_speech",
        "pronunciation",
        "synonyms",
        "antonyms",
        "derivatives",
        "collocations",
        "context_sentence",
    )
    raw = payload.model_dump()
    updates: dict[str, str] = {}
    for field in editable_fields:
        if field == "word" and not include_word:
            continue
        value = raw.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if field == "word":
            if text:
                updates[field] = normalize_word(text)
            continue
        if allow_blank or text:
            updates[field] = text
    return updates


def _card_to_dict(card) -> dict:
    return {
        "card_id": card.card_id,
        "word": card.word,
        "interval": card.interval,
        "repetitions": card.repetitions,
        "accuracy": round(card.accuracy * 100),
        "is_new": card.repetitions == 0,
    }


def _card_detail(card) -> dict:
    """Full card with enrichment fields."""
    d = _card_to_dict(card)
    d.update({
        "definition_en": card.definition_en,
        "definition_zh": card.definition_zh,
        "example": card.example,
        "synonyms": getattr(card, "synonyms", ""),
        "antonyms": getattr(card, "antonyms", ""),
        "derivatives": getattr(card, "derivatives", ""),
        "collocations": getattr(card, "collocations", ""),
        "context_sentence": getattr(card, "context_sentence", ""),
        "part_of_speech": getattr(card, "part_of_speech", ""),
        "pronunciation": getattr(card, "pronunciation", ""),
    })
    return d


def _scan_builtin_library() -> dict[str, Any]:
    return scan_content_library(_VOCAB_CONTENT_DIRS)


def _resolve_data_dir() -> str:
    cfg = load_config() or {}
    raw = cfg.get("data_dir", "data")
    path = Path(raw)
    resolved = path if path.is_absolute() else _CONFIG_PATH.parent / path
    return str(resolved.resolve())


def _content_exam_summary(catalog: dict[str, Any], exam: str) -> dict[str, Any]:
    normalized_exam = _normalize_exam_type(exam)
    books = [
        book for book in catalog.get("books", [])
        if normalized_exam == "both" or book.get("exam") == normalized_exam
    ]
    words: set[str] = set()
    subjects: dict[str, set[str]] = {}
    levels: dict[int, set[str]] = {level: set() for level in range(1, 5)}
    for book in books:
        for file_info in book.get("files", []):
            md_file = Path(file_info["path"])
            if not md_file.exists():
                continue
            fm, rows = _parse_vocab_markdown(md_file)
            difficulty = _normalize_difficulty(fm.get("difficulty", book.get("level", "B1")))
            level = 3 if difficulty.startswith("C") else 2 if difficulty.startswith("B") else 1
            subject = _derive_subject(fm.get("topic", book.get("topic", "general")), fm.get("source", md_file.stem))
            for row in rows:
                word = normalize_word(row.get("word", ""))
                if not word:
                    continue
                words.add(word)
                levels[level].add(word)
                subjects.setdefault(subject, set()).add(word)
    return {
        "exam": normalized_exam,
        "total_words": len(words),
        "by_level": [{"level": level, "word_count": len(levels[level])} for level in range(1, 5)],
        "by_subject": sorted(
            (
                {"subject_domain": subject, "word_count": len(subject_words)}
                for subject, subject_words in subjects.items()
            ),
            key=lambda item: item["word_count"],
            reverse=True,
        ),
    }


def _db_vocab_stats(srs) -> dict[str, Any]:
    rows = srs._db.execute(
        """SELECT
               COUNT(*) AS total_rows,
               COUNT(DISTINCT word) AS unique_words,
               SUM(CASE WHEN source='user' THEN 1 ELSE 0 END) AS user_words,
               SUM(CASE WHEN source!='user' THEN 1 ELSE 0 END) AS builtin_words
           FROM vocabulary"""
    ).fetchone()
    exam_rows = srs._db.execute(
        """SELECT exam_type AS exam, COUNT(DISTINCT word) AS word_count
           FROM vocabulary
           GROUP BY exam_type
           ORDER BY word_count DESC"""
    ).fetchall()
    group_rows = srs._db.execute(
        """SELECT book_group, COUNT(*) AS book_count, SUM(word_count) AS word_count
           FROM (
               SELECT b.book_group, COUNT(w.id) AS word_count
               FROM word_books b
               LEFT JOIN word_book_words w ON b.book_id = w.book_id
               GROUP BY b.book_id
           )
           GROUP BY book_group"""
    ).fetchall()
    return {
        "total_rows": rows["total_rows"] if rows else 0,
        "unique_words": rows["unique_words"] if rows else 0,
        "user_words": rows["user_words"] if rows else 0,
        "builtin_words": rows["builtin_words"] if rows else 0,
        "by_exam": [dict(r) for r in exam_rows],
        "by_book_group": [dict(r) for r in group_rows],
    }


@router.post("/start")
def start_session(max_cards: int = 20):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    exam = getattr(profile, "target_exam", "general")
    due = srs.get_due_cards(profile.user_id, limit=max_cards)
    if not due:
        # Try to enroll new words from exam-specific list
        new_words = srs.get_new_words(profile.user_id, exam=exam, limit=max_cards)
        if new_words:
            srs.enroll_words(profile.user_id, [w["word_id"] for w in new_words])
            due = srs.get_due_cards(profile.user_id, limit=max_cards)
        if not due:
            return {"empty": True, "message": "No cards due today!"}

    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "vocab")
    _sessions[sid] = VocabSession(
        session_id=sid,
        user_id=profile.user_id,
        db_session_id=db_sid,
        cards=due,
    )

    # Attach exam/source info to first card for UI badge
    first = _card_to_dict(due[0])
    first["source"] = _get_word_source(srs, due[0].word_id)
    first["exam"] = exam if hasattr(profile, "target_exam") else "general"
    return {
        "session_id": sid,
        "total": len(due),
        "remaining": len(due),
        "card": first,
        "exam": getattr(profile, "target_exam", "general"),
        "word_list_label": _source_label(first.get("source", "")),
    }


def _get_word_source(srs, word_id: str) -> str:
    row = srs._db.execute(
        "SELECT source FROM vocabulary WHERE word_id=?", (word_id,)
    ).fetchone()
    return row["source"] if row else "builtin"


def _source_label(source: str) -> str:
    labels = {
        "toefl_awl": "TOEFL Academic Word List",
        "gre_highfreq": "GRE High-Frequency",
        "ielts_academic": "IELTS Academic",
        "cet4_core": "CET-4 Core",
        "cet6_core": "CET-6 Core",
        "user": "My Words",
        "builtin": "General",
    }
    return labels.get(source, source.replace("_", " ").title())


@router.post("/reveal/{session_id}")
def reveal_card(session_id: str):
    sess = _sessions.get(session_id)
    if not sess or sess.index >= len(sess.cards):
        raise HTTPException(404, "Session not found or complete")
    kb, srs, user_model, ai, profile = get_components()
    card = sess.cards[sess.index]
    d = _card_detail(card)
    d["source"] = _get_word_source(srs, card.word_id)
    d["source_label"] = _source_label(d["source"])
    d["word_id"] = card.word_id
    return d


class RateRequest(BaseModel):
    quality: int  # 1-5


@router.post("/rate/{session_id}")
def rate_card(session_id: str, req: RateRequest):
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(404, "Session not found")

    kb, srs, user_model, ai, profile = get_components()
    card = sess.cards[sess.index]

    # SM-2 quality: map 1-5 → 0-5
    quality = max(0, min(5, req.quality - 1 + 1))  # keep 1-5 as-is, SM2 uses 0-5
    srs.review_card(card.card_id, quality)

    correct = req.quality >= 3
    if correct:
        sess.correct += 1
    user_model.record_answer(sess.user_id, "vocab_general", correct)

    sess.index += 1

    if sess.index >= len(sess.cards):
        # Session complete
        duration = int(time.time() - sess.start_time)
        accuracy = sess.correct / max(len(sess.cards), 1)
        user_model.end_session(sess.db_session_id, duration, len(sess.cards), accuracy)
        del _sessions[session_id]
        return {
            "complete": True,
            "stats": {
                "reviewed": len(sess.cards),
                "correct": sess.correct,
                "accuracy": round(accuracy * 100),
            },
        }

    next_card = sess.cards[sess.index]
    return {
        "complete": False,
        "remaining": len(sess.cards) - sess.index,
        "card": _card_to_dict(next_card),
    }


@router.get("/deck-stats")
def deck_stats():
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    return srs.deck_stats(profile.user_id)


class EnrichRequest(BaseModel):
    word: str


@router.post("/enrich")
def enrich_word(req: EnrichRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not ai:
        raise HTTPException(400, "No AI client configured")
    word = req.word.strip().lower()
    if not word:
        raise HTTPException(400, "Word is required")
    try:
        result = ai.enrich_word(word)
        return result
    except Exception as e:
        raise HTTPException(400, f"AI enrichment failed: {e}")


class AddWordRequest(BaseModel):
    word: str
    definition_en: str = ""
    definition_zh: str = ""
    example: str = ""
    part_of_speech: str = ""
    pronunciation: str = ""
    synonyms: str = ""
    antonyms: str = ""
    derivatives: str = ""
    collocations: str = ""
    context_sentence: str = ""


@router.post("/add")
def add_word(req: AddWordRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    word = req.word.strip().lower()
    if not word:
        raise HTTPException(400, "Word is required")
    existing_vocab = _lookup_existing_word(srs, word)
    requested_updates = _extract_word_updates(req, include_word=False, allow_blank=False)

    if existing_vocab:
        word_id = existing_vocab["word_id"]
        updated_existing = False
        if requested_updates:
            srs.update_word_fields(word_id, **requested_updates)
            updated_existing = True
        existing = srs._db.execute(
            """SELECT c.card_id FROM srs_cards c
               WHERE c.user_id=? AND c.word_id=?""",
            (profile.user_id, word_id),
        ).fetchone()
        if existing:
            return {
                "ok": True,
                "already_exists": True,
                "word": word,
                "word_id": word_id,
                "updated_existing": updated_existing,
            }
        srs.enroll_words(profile.user_id, [word_id])
        return {
            "ok": True,
            "already_exists": False,
            "word": word,
            "word_id": word_id,
            "reused_existing": True,
            "updated_existing": updated_existing,
        }

    word_id = srs.add_word(
        word=word,
        definition_en=req.definition_en,
        definition_zh=req.definition_zh,
        example=req.example,
        source="user",
        part_of_speech=req.part_of_speech,
        pronunciation=req.pronunciation,
        synonyms=req.synonyms,
        antonyms=req.antonyms,
        derivatives=req.derivatives,
        collocations=req.collocations,
        context_sentence=req.context_sentence,
    )
    srs.enroll_words(profile.user_id, [word_id])
    return {"ok": True, "already_exists": False, "word": word, "word_id": word_id}


@router.post("/ingest_builtin")
def ingest_builtin():
    """Import builtin vocabulary and keep user-created data intact."""
    kb, srs, user_model, ai, profile = get_components()
    content_dirs = [path for path in _VOCAB_CONTENT_DIRS if path.exists()]
    if not content_dirs:
        return {"ok": True, "imported": 0, "message": "No vocab content directories"}
    return sync_builtin_vocabulary(content_dirs, srs, profile)


# ── Tag endpoints ──────────────────────────────────────────────────

class TagRequest(BaseModel):
    word_id: str
    tag: str
    active: bool = True


@router.post("/tag")
def set_tag(req: TagRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    valid_tags = {"star", "error", "writing", "listening"}
    tag = req.tag.strip().lower()
    if not tag:
        raise HTTPException(400, "Tag is required")
    # Allow builtin tags + any custom tag (max 20 chars)
    if len(tag) > 20:
        raise HTTPException(400, "Tag too long")
    srs.set_tag(profile.user_id, req.word_id, tag, req.active)
    return {"ok": True, "word_id": req.word_id, "tag": tag, "active": req.active}


@router.get("/tags/{word_id}")
def get_word_tags(word_id: str):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    tags = srs.get_tags(profile.user_id, word_id)
    return {"word_id": word_id, "tags": tags}


@router.get("/tagged/{tag}")
def get_tagged_words(tag: str, limit: int = 200):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    words = srs.get_tagged_words(profile.user_id, tag.strip().lower(), limit=limit)
    return words


@router.get("/tags")
def list_all_tags():
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    return srs.get_all_tags(profile.user_id)


# ── Professional filtering endpoints ──────────────────────────────

@router.get("/by-level")
def get_words_by_level(level: int, exam: str = "general", limit: int = 50):
    """Get vocabulary words by level (1-4 grading system)."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    if level < 1 or level > 4:
        raise HTTPException(400, "Level must be between 1 and 4")

    words = srs.get_new_words(
        user_id=profile.user_id,
        level=level,
        exam=exam,
        limit=limit
    )
    return {"level": level, "exam": exam, "words": words, "count": len(words)}


@router.get("/by-subject")
def get_words_by_subject(subject: str, exam: str = "general", limit: int = 50):
    """Get vocabulary words by subject domain (biology, geology, astronomy, etc.)."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    words = srs.get_new_words(
        user_id=profile.user_id,
        subject_domain=subject,
        exam=exam,
        limit=limit
    )
    return {"subject": subject, "exam": exam, "words": words, "count": len(words)}


@router.get("/by-difficulty")
def get_words_by_difficulty(min_score: int = 1, max_score: int = 10, exam: str = "general", limit: int = 50):
    """Get vocabulary words by difficulty score (1-10 scale)."""
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")

    if min_score < 1 or max_score > 10 or min_score > max_score:
        raise HTTPException(400, "Invalid difficulty range (1-10)")

    words = srs.get_new_words(
        user_id=profile.user_id,
        difficulty_score_min=min_score,
        difficulty_score_max=max_score,
        exam=exam,
        limit=limit
    )
    return {
        "difficulty_range": {"min": min_score, "max": max_score},
        "exam": exam,
        "words": words,
        "count": len(words)
    }


@router.get("/subjects")
def list_subjects(exam: str = "general"):
    """List available subject domains for an exam."""
    rows = _content_exam_summary(_scan_builtin_library(), exam).get("by_subject", [])
    subjects = [{"subject": r["subject_domain"], "word_count": r["word_count"]} for r in rows]
    return {"exam": exam, "subjects": subjects}


@router.get("/stats")
def get_vocabulary_stats(exam: str = "general"):
    """Get vocabulary statistics by level, subject, and difficulty."""
    catalog = _content_exam_summary(_scan_builtin_library(), exam)

    return {
        "exam": exam,
        "total_words": catalog.get("total_words", 0),
        "by_level": catalog.get("by_level", [{"level": level, "word_count": 0} for level in range(1, 5)]),
        "by_subject": catalog.get("by_subject", [])[:10]
    }


@router.get("/library")
def get_vocabulary_library():
    kb, srs, user_model, ai, profile = get_components()
    content_catalog = _scan_builtin_library()
    books = srs.get_word_books(profile.user_id) if profile else []
    books_by_key = {book.get("book_key"): book for book in books if book.get("book_key")}
    recommended = []
    for item in content_catalog.get("recommended_path", []):
        actual = books_by_key.get(item["book_key"])
        recommended.append(
            {
                **item,
                "is_synced": actual is not None,
                "book_id": actual.get("book_id") if actual else None,
                "due_today": actual.get("due_today", 0) if actual else 0,
            }
        )
    return {
        "setup": {
            "configured": profile is not None,
            "has_api_key": ai is not None,
            "offline_ready": content_catalog.get("stats", {}).get("unique_words", 0) > 0,
            "data_dir": _resolve_data_dir(),
            "content_dirs": [str(path.resolve()) for path in _VOCAB_CONTENT_DIRS if path.exists()],
        },
        "recommended_path": recommended,
        "builtin_catalog": content_catalog,
        "database": _db_vocab_stats(srs),
        "user_books": [book for book in books if not int(book.get("is_builtin") or 0)],
        "builtin_books": [book for book in books if int(book.get("is_builtin") or 0)],
    }
