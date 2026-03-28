"""Word Books API — Anki-style custom vocabulary collections."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.vocab.catalog import merge_word_payload, normalize_exam_type, parse_import_payload
from gui.deps import get_components
from gui.api.vocab import (
    _card_to_dict,
    _derive_subject,
    _extract_word_updates,
    _get_word_source,
    _lookup_existing_word,
    VocabSession,
    _sessions,
)

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


class UpdateWordRequest(BaseModel):
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


class StartSessionRequest(BaseModel):
    max_cards: int = 20


class ImportValidateRequest(BaseModel):
    payload: str
    format: str = "auto"


class ImportBookRequest(BaseModel):
    payload: str
    format: str = "auto"
    book_id: Optional[str] = None
    book_name: str = ""
    description: str = ""
    color: str = "#4f8ef7"
    icon: str = "📥"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


def _book_due_today(srs, user_id: str, book_id: str) -> int:
    from datetime import date

    today = date.today().isoformat()
    return srs._db.execute(
        """SELECT COUNT(*) FROM srs_cards c
           JOIN word_book_words w ON w.word_id = c.word_id AND w.book_id = ?
           WHERE c.user_id = ? AND c.due_date <= ?""",
        (book_id, user_id, today),
    ).fetchone()[0]

@router.get("")
def list_books():
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    books = srs.get_word_books(profile.user_id)
    for b in books:
        b["due_today"] = _book_due_today(srs, profile.user_id, b["book_id"])
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
        source="user",
        source_type="manual",
        book_group="用户自建",
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
    book["due_today"] = _book_due_today(srs, profile.user_id, book_id)
    return book


@router.put("/{book_id}")
def update_book(book_id: str, req: UpdateBookRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    if int(book.get("is_builtin") or 0):
        raise HTTPException(403, "Built-in word books cannot be edited")
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
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    if int(book.get("is_builtin") or 0):
        raise HTTPException(403, "Built-in word books cannot be deleted")
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
    book["due_today"] = _book_due_today(srs, profile.user_id, book_id)
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
    if int(book.get("is_builtin") or 0):
        raise HTTPException(403, "Built-in word books are read-only")
    requested_updates = _extract_word_updates(req, include_word=False, allow_blank=False)

    if req.word_id:
        # Add existing vocab word
        word_id = req.word_id
        # Verify it exists
        row = srs._db.execute("SELECT * FROM vocabulary WHERE word_id=?", (word_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Word not found in vocabulary")
        word = row["word"]
        if requested_updates:
            srs.update_word_fields(word_id, **requested_updates)

        # Check if word already exists in this book
        existing_id = srs.check_word_in_book(book_id, word)
        if existing_id:
            return {
                "ok": True,
                "word_id": existing_id,
                "word": word,
                "already_exists": True,
                "updated_existing": bool(requested_updates),
            }
    elif req.word:
        # Check if word already exists in this book
        word = req.word.strip().lower()
        if not word:
            raise HTTPException(400, "Word is required")

        existing_id = srs.check_word_in_book(book_id, word)
        if existing_id:
            if requested_updates:
                srs.update_word_fields(existing_id, **requested_updates)
            return {
                "ok": True,
                "word_id": existing_id,
                "word": word,
                "already_exists": True,
                "updated_existing": bool(requested_updates),
            }

        existing = _lookup_existing_word(srs, word)
        if existing:
            word_id = existing["word_id"]
            if requested_updates:
                srs.update_word_fields(word_id, **requested_updates)

        else:
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
    return {
        "ok": True,
        "word_id": word_id,
        "word": word,
        "already_exists": False,
        "updated_existing": bool(requested_updates),
    }


@router.delete("/{book_id}/words/{word_id}")
def remove_word(book_id: str, word_id: str):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    if int(book.get("is_builtin") or 0):
        raise HTTPException(403, "Built-in word books are read-only")
    srs.remove_word_from_book(book_id, word_id)
    return {"ok": True}


@router.put("/{book_id}/words/{word_id}")
def update_word(book_id: str, word_id: str, req: UpdateWordRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    book = srs.get_word_book(book_id, profile.user_id)
    if not book:
        raise HTTPException(404, "Word book not found")
    membership = srs._db.execute(
        "SELECT 1 FROM word_book_words WHERE book_id=? AND word_id=?",
        (book_id, word_id),
    ).fetchone()
    if not membership:
        raise HTTPException(404, "Word not found in word book")

    updates = _extract_word_updates(req, include_word=True, allow_blank=True)
    if not updates.get("word"):
        raise HTTPException(400, "Word is required")
    try:
        srs.update_word_fields(word_id, **updates)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    row = srs._db.execute("SELECT * FROM vocabulary WHERE word_id=?", (word_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Word not found")
    return dict(row)


@router.post("/import/validate")
def validate_import(req: ImportValidateRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    try:
        parsed = parse_import_payload(req.payload, req.format)
    except Exception as exc:
        raise HTTPException(400, f"Import parse failed: {exc}")

    existing_words = 0
    existing_user_words = 0
    preview = []
    for row in parsed["words"][:8]:
        existing = _lookup_existing_word(srs, row["word"])
        if existing:
            existing_words += 1
            if (existing["source"] or "").lower() == "user":
                existing_user_words += 1
        preview.append(
            {
                "word": row["word"],
                "definition_en": row["definition_en"],
                "exists": existing is not None,
                "source": existing["source"] if existing else "",
            }
        )

    return {
        "ok": True,
        "format": parsed["format"],
        "book": parsed["book"],
        "errors": parsed["errors"],
        "warnings": parsed["warnings"],
        "stats": {
            **parsed["stats"],
            "existing_words": existing_words,
            "existing_user_words": existing_user_words,
            "new_words": max(0, parsed["stats"]["unique_words"] - existing_words),
        },
        "merge_rules": [
            "按 word 的小写形式去重。",
            "用户自建词条不会被覆盖，只会复用并加入词书。",
            "已有内置词条会补充更完整字段，但不会因较差内容被降级。",
        ],
        "preview": preview,
    }


@router.post("/import")
def import_book(req: ImportBookRequest):
    kb, srs, user_model, ai, profile = get_components()
    if not profile:
        raise HTTPException(400, "No profile")
    try:
        parsed = parse_import_payload(req.payload, req.format)
    except Exception as exc:
        raise HTTPException(400, f"Import parse failed: {exc}")
    if parsed["errors"]:
        raise HTTPException(400, "Import has validation errors")

    if req.book_id:
        target_book = srs.get_word_book(req.book_id, profile.user_id)
        if not target_book:
            raise HTTPException(404, "Word book not found")
        if int(target_book.get("is_builtin") or 0):
            raise HTTPException(403, "Cannot import into built-in word books")
    else:
        target_book = srs.create_word_book(
            user_id=profile.user_id,
            name=req.book_name.strip() or parsed["book"].get("name") or "Imported Vocabulary",
            description=req.description.strip() or parsed["book"].get("description", ""),
            color=req.color,
            icon=req.icon,
            exam=normalize_exam_type(parsed["book"].get("exam", "general")),
            source="user_import",
            level=parsed["book"].get("level", ""),
            topic=parsed["book"].get("topic", "general"),
            source_label=f"User import ({parsed['format']})",
            source_type="import",
            import_format=parsed["format"],
            book_group="用户自建",
        )

    exam_type = normalize_exam_type(parsed["book"].get("exam", "general"))
    topic = parsed["book"].get("topic", "general")
    subject_domain = _derive_subject(topic, parsed["book"].get("source", "user_import"))
    difficulty = parsed["book"].get("level", "B1")
    difficulty_upper = str(difficulty).upper()
    level = 3 if difficulty_upper.startswith("C") else 2 if difficulty_upper.startswith("B") else 1
    difficulty_score = 7 if level >= 3 else 5 if level == 2 else 3

    created_words = 0
    reused_words = 0
    reused_user_words = 0
    added_to_book = 0

    for row in parsed["words"]:
        existing = _lookup_existing_word(srs, row["word"])
        if not existing:
            word_id = srs.add_word(
                word=row["word"],
                definition_en=row["definition_en"],
                definition_zh=row["definition_zh"],
                example=row["example"],
                topic=topic,
                difficulty=difficulty,
                source="user",
                synonyms=row["synonyms"],
                antonyms=row["antonyms"],
                derivatives=row["derivatives"],
                collocations=row["collocations"],
                context_sentence=row["context_sentence"],
                part_of_speech=row["part_of_speech"],
                pronunciation=row["pronunciation"],
                level=level,
                category=topic,
                difficulty_score=difficulty_score,
                exam_type=exam_type,
                subject_domain=subject_domain,
                usage_notes=row["usage_notes"],
            )
            created_words += 1
        else:
            word_id = existing["word_id"]
            reused_words += 1
            if (existing["source"] or "").lower() == "user":
                reused_user_words += 1
            updates = merge_word_payload(
                dict(existing),
                row,
                exam_type=exam_type,
                topic=topic,
                subject_domain=subject_domain,
                difficulty=difficulty,
                level=level,
                difficulty_score=difficulty_score,
            )
            if updates:
                srs.update_word_fields(word_id, **updates)
        srs.enroll_words(profile.user_id, [word_id])
        if srs.add_word_to_book(target_book["book_id"], word_id):
            added_to_book += 1

    return {
        "ok": True,
        "format": parsed["format"],
        "book": srs.get_word_book(target_book["book_id"], profile.user_id),
        "stats": {
            "imported_rows": parsed["stats"]["rows"],
            "valid_words": parsed["stats"]["valid_words"],
            "created_words": created_words,
            "reused_words": reused_words,
            "reused_user_words": reused_user_words,
            "added_to_book": added_to_book,
        },
    }


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
