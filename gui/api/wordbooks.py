"""Word Books API — Anki-style custom vocabulary collections."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gui.deps import get_components
from gui.api.vocab import _card_to_dict, _card_detail, _get_word_source, _source_label, VocabSession, _sessions

import time
import uuid

router = APIRouter(prefix="/api/wordbooks", tags=["wordbooks"])


# ------------------------------------------------------------------
# Request models
# ------------------------------------------------------------------

class CreateBookRequest(BaseModel):
    name: str
    description: str = ""
    color: str = "#4f8ef7"
    icon: str = "📖"


class UpdateBookRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class AddWordRequest(BaseModel):
    word_id: Optional[str] = None   # existing vocab word_id
    # OR create new word inline
    word: Optional[str] = None
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


class StartSessionRequest(BaseModel):
    max_cards: int = 20


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("")
def list_books():
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    books = srs.get_word_books(profile.user_id)
    # Attach due_today count per book
    from datetime import date
    today = date.today().isoformat()
    for b in books:
        due = srs._db.execute(
            """SELECT COUNT(*) FROM srs_cards c
               JOIN word_book_words w ON w.word_id = c.word_id AND w.book_id = ?
               WHERE c.user_id = ? AND c.due_date <= ?""",
            (b["book_id"], profile.user_id, today),
        ).fetchone()[0]
        b["due_today"] = due
    return books


@router.post("")
def create_book(req: CreateBookRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    if not req.name.strip():
        raise HTTPException(400, "Name is required")
    book = srs.create_word_book(
        user_id=profile.user_id,
        name=req.name.strip(),
        description=req.description.strip(),
        color=req.color,
        icon=req.icon,
    )
    return book


@router.get("/{book_id}")
def get_book(book_id: str):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    return book


@router.put("/{book_id}")
def update_book(book_id: str, req: UpdateBookRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Nothing to update")
    ok = srs.update_word_book(book_id, profile.user_id, **fields)
    if not ok:
        raise HTTPException(404, "Word book not found")
    return srs.get_word_book(book_id, profile.user_id)


@router.delete("/{book_id}")
def delete_book(book_id: str):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    ok = srs.delete_word_book(book_id, profile.user_id)
    if not ok:
        raise HTTPException(404, "Word book not found")
    return {"ok": True}


@router.get("/{book_id}/words")
def list_words(book_id: str, limit: int = 200, offset: int = 0):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    words = srs.get_book_words(book_id, profile.user_id, limit=limit, offset=offset)
    return {"book": book, "words": words, "total": book["word_count"]}


@router.post("/{book_id}/words")
def add_word(book_id: str, req: AddWordRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")

    if req.word_id:
        # Add existing vocab word
        word_id = req.word_id
        # Verify it exists
        row = srs._db.execute("SELECT word FROM vocabulary WHERE word_id=?", (word_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Word not found in vocabulary")
        word = row["word"]

        # Check if word already exists in this book
        existing_id = srs.check_word_in_book(book_id, word)
        if existing_id:
            return {"ok": True, "word_id": existing_id, "word": word, "already_exists": True}
    elif req.word:
        # Check if word already exists in this book
        word = req.word.strip().lower()
        if not word:
            raise HTTPException(400, "Word is required")

        existing_id = srs.check_word_in_book(book_id, word)
        if existing_id:
            return {"ok": True, "word_id": existing_id, "word": word, "already_exists": True}

        # Create new word and add
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
    else:
        raise HTTPException(400, "Provide word_id or word")

    # Enroll in SRS if not already
    srs.enroll_words(profile.user_id, [word_id])
    srs.add_word_to_book(book_id, word_id)
    return {"ok": True, "word_id": word_id, "word": word, "already_exists": False}


@router.delete("/{book_id}/words/{word_id}")
def remove_word(book_id: str, word_id: str):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    srs.remove_word_from_book(book_id, word_id)
    return {"ok": True}


@router.get("/search/vocab")
def search_vocab(q: str = "", limit: int = 20):
    kb, srs, user_model, ai, profile = get_components()
    if not q.strip():
        return []
    return srs.search_vocabulary(q.strip(), limit=limit)


@router.post("/{book_id}/start")
def start_book_session(book_id: str, req: StartSessionRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")

    due = srs.get_due_cards_for_book(profile.user_id, book_id, limit=req.max_cards)
    if not due:
        new_words = srs.get_new_words_for_book(profile.user_id, book_id, limit=req.max_cards)
        if new_words:
            srs.enroll_words(profile.user_id, [w["word_id"] for w in new_words])
            due = srs.get_due_cards_for_book(profile.user_id, book_id, limit=req.max_cards)
        if not due:
            return {"empty": True, "message": "No cards due in this book!", "book": book}

    sid = uuid.uuid4().hex[:12]
    db_sid = user_model.start_session(profile.user_id, "vocab")
    _sessions[sid] = VocabSession(
        session_id=sid,
        user_id=profile.user_id,
        db_session_id=db_sid,
        cards=due,
    )

    first = _card_to_dict(due[0])
    first["source"] = _get_word_source(srs, due[0].word_id)
    return {
        "session_id": sid,
        "total": len(due),
        "remaining": len(due),
        "card": first,
        "book": book,
        "word_list_label": book["name"],
    }
