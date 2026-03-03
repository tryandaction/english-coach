"""
Anki .apkg export — zero backend, zero cost.
Converts the user's SRS vocabulary deck into a standard Anki package
that can be imported on any device (desktop, AnkiDroid, AnkiMobile).

.apkg format:
  - A ZIP file containing:
    - collection.anki2  (SQLite, Anki's internal schema)
    - media             (JSON mapping, empty if no media)
"""

from __future__ import annotations

import json
import os
import sqlite3
import struct
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header

console = Console(highlight=False)

# Anki epoch starts at 2006-01-01 (seconds since then)
_ANKI_EPOCH = 1136073600


def _anki_time() -> int:
    return int(time.time())


def _anki_id() -> int:
    """Anki uses millisecond timestamps as IDs."""
    return int(time.time() * 1000)


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def export_anki(
    srs: SM2Engine,
    profile: UserProfile,
    output_path: Path,
    deck_name: str = "English Coach",
) -> int:
    """
    Export user's vocabulary deck to Anki .apkg format.
    Returns number of cards exported.
    """
    print_header("Anki Export  /  导出到Anki")

    # Fetch all cards for this user (including enrichment fields)
    rows = srs._db.execute(
        """SELECT v.word, v.definition_en, v.definition_zh, v.example,
                  v.topic, v.difficulty, v.synonyms, v.antonyms,
                  v.derivatives, v.collocations, v.context_sentence,
                  v.part_of_speech, v.pronunciation,
                  c.interval, c.repetitions, c.easiness, c.due_date,
                  c.total_reviews, c.correct_reviews
           FROM srs_cards c
           JOIN vocabulary v ON c.word_id = v.word_id
           WHERE c.user_id = ?
           ORDER BY v.word""",
        (profile.user_id,),
    ).fetchall()

    if not rows:
        console.print("[yellow]No vocabulary cards to export.[/yellow]\n")
        return 0

    with console.status(f"[bold blue]Building Anki deck ({len(rows)} cards)...[/bold blue]"):
        apkg_path = _build_apkg(rows, output_path, deck_name, profile)

    size_kb = apkg_path.stat().st_size // 1024
    console.print(
        f"\n[green]Exported {len(rows)} cards to:[/green] [bold]{apkg_path}[/bold]  "
        f"[dim]({size_kb} KB)[/dim]\n"
    )
    console.print(
        "  Import into Anki: [bold]File -> Import[/bold] -> select the .apkg file\n"
        "  Works with: Anki desktop, AnkiDroid (Android), AnkiMobile (iOS)\n"
    )
    return len(rows)


# ------------------------------------------------------------------
# .apkg builder
# ------------------------------------------------------------------

def _build_apkg(
    rows: list,
    output_path: Path,
    deck_name: str,
    profile: UserProfile,
) -> Path:
    """Build the .apkg ZIP file and return its path."""
    # Ensure .apkg extension
    if output_path.suffix.lower() != ".apkg":
        output_path = output_path.with_suffix(".apkg")

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "collection.anki2"
        _build_anki_db(db_path, rows, deck_name, profile)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, "collection.anki2")
            zf.writestr("media", "{}")  # no media files

    return output_path


def _build_anki_db(
    db_path: Path,
    rows: list,
    deck_name: str,
    profile: UserProfile,
) -> None:
    """Create a minimal Anki collection.anki2 SQLite database."""
    db = sqlite3.connect(str(db_path))

    # Anki schema (minimal subset needed for import)
    db.executescript("""
        CREATE TABLE col (
            id      INTEGER PRIMARY KEY,
            crt     INTEGER NOT NULL,
            mod     INTEGER NOT NULL,
            scm     INTEGER NOT NULL,
            ver     INTEGER NOT NULL,
            dty     INTEGER NOT NULL,
            usn     INTEGER NOT NULL,
            ls      INTEGER NOT NULL,
            conf    TEXT NOT NULL,
            models  TEXT NOT NULL,
            decks   TEXT NOT NULL,
            dconf   TEXT NOT NULL,
            tags    TEXT NOT NULL
        );

        CREATE TABLE notes (
            id      INTEGER PRIMARY KEY,
            guid    TEXT NOT NULL,
            mid     INTEGER NOT NULL,
            mod     INTEGER NOT NULL,
            usn     INTEGER NOT NULL,
            tags    TEXT NOT NULL,
            flds    TEXT NOT NULL,
            sfld    TEXT NOT NULL,
            csum    INTEGER NOT NULL,
            flags   INTEGER NOT NULL,
            data    TEXT NOT NULL
        );

        CREATE TABLE cards (
            id      INTEGER PRIMARY KEY,
            nid     INTEGER NOT NULL,
            did     INTEGER NOT NULL,
            ord     INTEGER NOT NULL,
            mod     INTEGER NOT NULL,
            usn     INTEGER NOT NULL,
            type    INTEGER NOT NULL,
            queue   INTEGER NOT NULL,
            due     INTEGER NOT NULL,
            ivl     INTEGER NOT NULL,
            factor  INTEGER NOT NULL,
            reps    INTEGER NOT NULL,
            lapses  INTEGER NOT NULL,
            left    INTEGER NOT NULL,
            odue    INTEGER NOT NULL,
            odid    INTEGER NOT NULL,
            flags   INTEGER NOT NULL,
            data    TEXT NOT NULL
        );

        CREATE TABLE revlog (
            id      INTEGER PRIMARY KEY,
            cid     INTEGER NOT NULL,
            usn     INTEGER NOT NULL,
            ease    INTEGER NOT NULL,
            ivl     INTEGER NOT NULL,
            lastIvl INTEGER NOT NULL,
            factor  INTEGER NOT NULL,
            time    INTEGER NOT NULL,
            type    INTEGER NOT NULL
        );

        CREATE TABLE graves (
            usn     INTEGER NOT NULL,
            oid     INTEGER NOT NULL,
            type    INTEGER NOT NULL
        );

        CREATE INDEX ix_notes_usn ON notes (usn);
        CREATE INDEX ix_cards_usn ON cards (usn);
        CREATE INDEX ix_revlog_usn ON revlog (usn);
        CREATE INDEX ix_cards_nid ON cards (nid);
        CREATE INDEX ix_cards_sched ON cards (did, queue, due);
        CREATE INDEX ix_revlog_cid ON revlog (cid);
        CREATE INDEX ix_notes_csum ON notes (csum);
    """)

    now = _anki_time()
    deck_id = _anki_id()
    model_id = deck_id + 1

    # Note model: Front = word + POS + pronunciation, Back = full enriched card
    model = {
        str(model_id): {
            "id": str(model_id),
            "name": "English Coach",
            "type": 0,
            "mod": now,
            "usn": -1,
            "sortf": 0,
            "did": deck_id,
            "tmpls": [
                {
                    "name": "Card 1",
                    "ord": 0,
                    "qfmt": (
                        "<div style='font-size:2em;font-weight:bold;text-align:center'>{{Word}}</div>"
                        "<div style='text-align:center;color:#888;font-style:italic'>{{POS}} &nbsp; {{Pronunciation}}</div>"
                    ),
                    "afmt": (
                        "{{FrontSide}}<hr>"
                        "<div style='font-size:1.15em;color:#222'>{{Definition}}</div>"
                        "<div style='color:#555;margin-top:6px'>{{Chinese}}</div>"
                        "<div style='font-style:italic;margin-top:10px;color:#444'>{{Example}}</div>"
                        "<div style='margin-top:10px;color:#555;font-style:italic'>{{ContextSentence}}</div>"
                        "<div style='margin-top:10px;font-size:0.9em'>"
                        "<span style='color:#2a7'>Synonyms:</span> {{Synonyms}}</div>"
                        "<div style='font-size:0.9em'>"
                        "<span style='color:#c44'>Antonyms:</span> {{Antonyms}}</div>"
                        "<div style='font-size:0.9em'>"
                        "<span style='color:#a70'>Derivatives:</span> {{Derivatives}}</div>"
                        "<div style='font-size:0.9em'>"
                        "<span style='color:#07a'>Collocations:</span> {{Collocations}}</div>"
                        "<div style='font-size:0.8em;color:#999;margin-top:8px'>{{Topic}} · {{Difficulty}}</div>"
                    ),
                    "bqfmt": "",
                    "bafmt": "",
                    "did": None,
                    "bfont": "",
                    "bsize": 0,
                }
            ],
            "flds": [
                {"name": "Word",            "ord": 0,  "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Definition",      "ord": 1,  "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Chinese",         "ord": 2,  "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Example",         "ord": 3,  "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Topic",           "ord": 4,  "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Difficulty",      "ord": 5,  "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Synonyms",        "ord": 6,  "sticky": False, "rtl": False, "font": "Arial", "size": 16},
                {"name": "Antonyms",        "ord": 7,  "sticky": False, "rtl": False, "font": "Arial", "size": 16},
                {"name": "Derivatives",     "ord": 8,  "sticky": False, "rtl": False, "font": "Arial", "size": 16},
                {"name": "Collocations",    "ord": 9,  "sticky": False, "rtl": False, "font": "Arial", "size": 16},
                {"name": "ContextSentence", "ord": 10, "sticky": False, "rtl": False, "font": "Arial", "size": 16},
                {"name": "POS",             "ord": 11, "sticky": False, "rtl": False, "font": "Arial", "size": 16},
                {"name": "Pronunciation",   "ord": 12, "sticky": False, "rtl": False, "font": "Arial", "size": 16},
            ],
            "css": "body { font-family: Arial; line-height: 1.5; }",
            "latexPre": "",
            "latexPost": "",
            "tags": [],
            "vers": [],
        }
    }

    deck = {
        str(deck_id): {
            "id": deck_id,
            "name": deck_name,
            "desc": f"Exported from English Coach — {profile.name} ({profile.target_exam.upper()})",
            "mod": now,
            "usn": -1,
            "collapsed": False,
            "newToday": [0, 0],
            "revToday": [0, 0],
            "lrnToday": [0, 0],
            "timeToday": [0, 0],
            "conf": 1,
            "extendNew": 10,
            "extendRev": 50,
            "dyn": 0,
        },
        "1": {
            "id": 1,
            "name": "Default",
            "conf": 1,
            "desc": "",
            "dyn": 0,
            "collapsed": False,
            "mod": now,
            "usn": -1,
            "newToday": [0, 0],
            "revToday": [0, 0],
            "lrnToday": [0, 0],
            "timeToday": [0, 0],
            "extendNew": 10,
            "extendRev": 50,
        },
    }

    dconf = {
        "1": {
            "id": 1,
            "name": "Default",
            "replayq": True,
            "lapse": {"delays": [10], "mult": 0, "minInt": 1, "leechFails": 8, "leechAction": 0},
            "rev": {"perDay": 200, "ease4": 1.3, "fuzz": 0.05, "minSpace": 1, "ivlFct": 1, "maxIvl": 36500, "bury": True},
            "new": {"perDay": 20, "delays": [1, 10], "separate": True, "ints": [1, 4, 7], "initialFactor": 2500, "bury": True, "order": 1},
            "maxTaken": 60,
            "timer": 0,
            "autoplay": True,
            "mod": 0,
            "usn": 0,
        }
    }

    db.execute(
        "INSERT INTO col VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            1, now, now, now * 1000, 11, 0, -1, 0,
            json.dumps({"nextPos": 1, "estTimes": True, "activeDecks": [deck_id],
                        "sortType": "noteFld", "timeLim": 0, "sortBackwards": False,
                        "addToCur": True, "curDeck": deck_id, "newBury": True,
                        "newSpread": 0, "dueCounts": True, "curModel": str(model_id),
                        "collapseTime": 1200}),
            json.dumps(model),
            json.dumps(deck),
            json.dumps(dconf),
            "{}",
        ),
    )

    # Insert notes and cards
    sep = "\x1f"  # Anki field separator
    for i, row in enumerate(rows):
        word        = row[0]  or ""
        defn_en     = row[1]  or ""
        defn_zh     = row[2]  or ""
        example     = row[3]  or ""
        topic       = row[4]  or "general"
        difficulty  = row[5]  or "B1"
        synonyms    = row[6]  or ""
        antonyms    = row[7]  or ""
        derivatives = row[8]  or ""
        collocations     = row[9]  or ""
        context_sentence = row[10] or ""
        part_of_speech   = row[11] or ""
        pronunciation    = row[12] or ""
        interval      = max(1, row[13] or 1)
        repetitions   = row[14] or 0
        easiness      = row[15] or 2.5
        total_reviews   = row[17] or 0
        correct_reviews = row[18] or 0

        note_id = deck_id + 100 + i
        card_id = deck_id + 200 + i
        flds = sep.join([
            word, defn_en, defn_zh, example, topic, difficulty,
            synonyms, antonyms, derivatives, collocations,
            context_sentence, part_of_speech, pronunciation,
        ])
        csum = _field_checksum(word)

        db.execute(
            "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (note_id, f"ec{note_id}", model_id, now, -1, "", flds, word, csum, 0, ""),
        )

        # Map SM-2 state to Anki card state
        # type: 0=new, 1=learning, 2=review
        card_type = 2 if repetitions > 0 else 0
        card_queue = 2 if repetitions > 0 else 0
        # Anki due for review cards = days since collection creation
        due = interval if repetitions > 0 else i
        factor = max(1300, int(easiness * 1000))

        db.execute(
            "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (card_id, note_id, deck_id, 0, now, -1,
             card_type, card_queue, due, interval,
             factor, total_reviews,
             max(0, total_reviews - correct_reviews),
             0, 0, 0, 0, ""),
        )

    db.commit()
    db.close()


def _field_checksum(text: str) -> int:
    """Anki uses a CRC32-like checksum of the first field."""
    import binascii
    return binascii.crc32(text.encode("utf-8")) & 0xFFFFFFFF
