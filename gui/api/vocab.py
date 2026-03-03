"""Vocab flashcard API — session state machine wrapping SM2Engine."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gui.deps import get_components

router = APIRouter(prefix="/api/vocab", tags=["vocab"])

_VOCAB_CONTENT_DIR = Path(__file__).parent.parent.parent / "content" / "vocab"


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


@router.get("/stats")
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
    # Check if already in deck
    existing = srs._db.execute(
        """SELECT c.card_id FROM srs_cards c
           JOIN vocabulary v ON c.word_id = v.word_id
           WHERE c.user_id=? AND v.word=?""",
        (profile.user_id, word),
    ).fetchone()
    if existing:
        return {"ok": True, "already_exists": True, "word": word}

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
    """Scan content/vocab/*.md and import words into vocabulary table, then seed default books."""
    kb, srs, user_model, ai, profile = get_components()
    if not _VOCAB_CONTENT_DIR.exists():
        return {"ok": True, "imported": 0, "message": "No vocab content directory"}

    total_imported = 0
    files_processed = []

    # source → (book name, icon, color)
    _DEFAULT_BOOKS = {
        "toefl_awl":      ("TOEFL Academic Words", "🎓", "#4f8ef7"),
        "gre_highfreq":   ("GRE High-Frequency",   "🔬", "#7c5cfc"),
        "ielts_academic": ("IELTS Academic",        "📖", "#3ecf8e"),
        "cet4_core":      ("CET-4 Core",            "⭐", "#f5c842"),
        "cet6_core":      ("CET-6 Core",            "🔥", "#f26b6b"),
    }

    for md_file in sorted(_VOCAB_CONTENT_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        fm: dict = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        fm[k.strip()] = v.strip()
                body = parts[2].strip()

        source = fm.get("source", md_file.stem)
        difficulty = fm.get("difficulty", "B1")
        topic = fm.get("topic", "general")

        imported = 0
        word_ids = []
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("word|"):
                continue
            parts = line.split("|")
            if len(parts) < 3:
                continue
            word = parts[0].strip().lower()
            definition_en = parts[1].strip() if len(parts) > 1 else ""
            definition_zh = parts[2].strip() if len(parts) > 2 else ""
            example = parts[3].strip() if len(parts) > 3 else ""
            pos = parts[4].strip() if len(parts) > 4 else ""
            synonyms = parts[5].strip() if len(parts) > 5 else ""
            antonyms = parts[6].strip() if len(parts) > 6 else ""
            if not word or not definition_en:
                continue
            wid = srs.add_word(
                word=word,
                definition_en=definition_en,
                definition_zh=definition_zh,
                example=example,
                topic=topic,
                difficulty=difficulty,
                source=source,
                synonyms=synonyms,
                antonyms=antonyms,
                part_of_speech=pos,
            )
            word_ids.append(wid)
            imported += 1

        total_imported += imported
        files_processed.append({"file": md_file.name, "words": imported})

        # Seed default word book for this source (once per user)
        if profile and source in _DEFAULT_BOOKS and word_ids:
            bname, bicon, bcolor = _DEFAULT_BOOKS[source]
            existing = srs._db.execute(
                "SELECT book_id FROM word_books WHERE user_id=? AND name=?",
                (profile.user_id, bname),
            ).fetchone()
            if not existing:
                book = srs.create_word_book(
                    user_id=profile.user_id,
                    name=bname,
                    description=f"Built-in {bname} word list",
                    color=bcolor,
                    icon=bicon,
                )
                for wid in word_ids:
                    srs.add_word_to_book(book["book_id"], wid)

    return {"ok": True, "imported": total_imported, "files": files_processed}


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
