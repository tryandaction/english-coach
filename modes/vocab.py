"""
Vocabulary learning mode — SRS flashcards, zero API calls.
Handles both review of due cards and introduction of new words.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich import box

from core.srs.engine import SM2Engine, Card
from core.user_model.profile import UserModel, UserProfile
from cli.display import (
    print_header, print_word_card, print_result_row,
    print_session_summary, confirm,
)

console = Console()


def run_vocab_session(
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    max_cards: int = 30,
) -> dict:
    """
    Run a vocabulary session:
    1. Review due cards first (SRS)
    2. Introduce new words if time/quota remains
    Returns session stats dict.
    """
    session_id = user_model.start_session(profile.user_id, "vocab")
    start_time = time.time()

    due_cards = srs.get_due_cards(profile.user_id, limit=max_cards)
    stats = {"reviewed": 0, "correct": 0, "new_enrolled": 0}

    # --- Phase 1: Review due cards ---
    if due_cards:
        print_header(
            f"词汇复习  ·  Vocabulary Review",
            subtitle=f"{len(due_cards)} cards due · CEFR {profile.cefr_level}",
        )
        for card in due_cards:
            result = _review_one_card(card, srs)
            stats["reviewed"] += 1
            if result["correct"]:
                stats["correct"] += 1
            user_model.record_answer(
                profile.user_id,
                "vocab_academic" if card.word else "vocab_general",
                result["correct"],
            )
    else:
        console.print("\n[green]✓ No cards due today![/green] Great job keeping up.\n")

    # --- Phase 2: New words (if quota not exhausted) ---
    remaining = profile.daily_new_words - stats["reviewed"]
    if remaining > 0:
        new_words = srs.get_new_words(
            profile.user_id,
            difficulty=profile.cefr_level,
            limit=min(remaining, 10),
        )
        if new_words:
            if confirm(f"\n学习 {len(new_words)} 个新词？ Learn {len(new_words)} new words?"):
                word_ids = [w["word_id"] for w in new_words]
                srs.enroll_words(profile.user_id, word_ids)
                stats["new_enrolled"] = len(word_ids)
                _introduce_new_words(new_words)

    # --- Wrap up ---
    duration = int(time.time() - start_time)
    accuracy = stats["correct"] / max(stats["reviewed"], 1)
    user_model.end_session(session_id, duration, stats["reviewed"], accuracy)
    user_model.update_profile(profile)

    deck = srs.deck_stats(profile.user_id)
    print_session_summary(
        mode="Vocabulary",
        reviewed=stats["reviewed"],
        correct=stats["correct"],
        new_words=stats["new_enrolled"],
        duration_sec=duration,
        deck_total=deck["total"],
        deck_mature=deck["mature"],
    )
    return stats


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _review_one_card(card: Card, srs: SM2Engine) -> dict:
    """Show a flashcard, wait for user rating, apply SM-2."""
    console.print()
    print_word_card(card.word, show_answer=False)

    # Speak the word automatically (non-blocking feel — fires and user presses Enter)
    try:
        from ai.tts import speak
        import threading
        threading.Thread(target=speak, args=(card.word,), daemon=True).start()
    except Exception:
        pass

    input("  Press Enter to reveal...")

    # Fetch enriched fields if available
    row = srs._db.execute(
        "SELECT * FROM vocabulary WHERE word=?", (card.word,)
    ).fetchone()
    extra = dict(row) if row else {}

    print_word_card(
        card.word,
        definition_en=card.definition_en,
        definition_zh=card.definition_zh,
        example=card.example,
        show_answer=True,
        synonyms=extra.get("synonyms", ""),
        collocations=extra.get("collocations", ""),
        context_sentence=extra.get("context_sentence", ""),
        part_of_speech=extra.get("part_of_speech", ""),
        pronunciation=extra.get("pronunciation", ""),
    )

    quality = _get_quality_rating()
    result = srs.review_card(card.card_id, quality)

    color = "green" if result["correct"] else "red"
    console.print(
        f"  [{'green' if result['correct'] else 'red'}]"
        f"{'correct' if result['correct'] else 'wrong'}[/]  "
        f"[dim]{result['message']}[/dim]"
    )
    return result


def _get_quality_rating() -> int:
    """Prompt user for 1-5 quality rating with visual guide."""
    console.print(
        "\n  [bold]How well did you know it?[/bold]\n"
        "  [red]1[/red] 完全不会  "
        "[yellow]2[/yellow] 模糊  "
        "[yellow]3[/yellow] 费力想起  "
        "[green]4[/green] 犹豫  "
        "[green]5[/green] 秒答\n"
    )
    while True:
        raw = Prompt.ask("  Rating", choices=["1", "2", "3", "4", "5"], default="3")
        return int(raw)


def _introduce_new_words(words: list[dict]) -> None:
    """Show new words one by one for initial learning (no rating needed)."""
    console.print()
    console.print(Panel(
        f"[bold]New Words · 新词学习[/bold]\n"
        f"[dim]Read each word carefully. You'll review them with SRS tomorrow.[/dim]",
        border_style="blue",
    ))

    for i, w in enumerate(words, 1):
        console.print(f"\n  [dim]{i}/{len(words)}[/dim]")
        print_word_card(
            w["word"],
            definition_en=w["definition_en"],
            definition_zh=w.get("definition_zh", ""),
            example=w.get("example", ""),
            show_answer=True,
            is_new=True,
        )
        if i < len(words):
            input("  [dim]Press Enter for next word...[/dim]")

    console.print(
        f"\n[green]✓ {len(words)} new words added to your deck![/green] "
        f"First review: tomorrow.\n"
    )
