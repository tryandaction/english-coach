"""
Reading comprehension mode — retrieves passages from knowledge base,
generates questions via AI (cached), scores answers algorithmically.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ai.client import AIClient
from core.knowledge_base.store import KnowledgeBase
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header, confirm

console = Console()


def run_reading_session(
    kb: KnowledgeBase,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: Optional[str] = None,
    srs: Optional[SM2Engine] = None,
) -> dict:
    """
    Run a reading comprehension session:
    1. Retrieve a passage at i+1 difficulty
    2. Display passage
    3. Generate/retrieve comprehension questions (AI, cached)
    4. Score answers
    5. Update skill scores
    """
    exam = exam or profile.target_exam or "general"
    session_id = user_model.start_session(profile.user_id, "reading")
    start_time = time.time()

    print_header(
        "阅读理解  ·  Reading Comprehension",
        subtitle=f"Exam: {exam.upper()} · CEFR {profile.cefr_level}",
    )

    # Fetch unseen passage chunks
    seen = user_model.get_seen_ids(profile.user_id)
    rows = kb.get_by_type(
        content_type="reading",
        difficulty=profile.cefr_level,
        exam=exam,
        exclude_ids=seen,
        limit=6,
        random_order=True,
    )

    if not rows:
        # Fallback: ignore seen filter
        rows = kb.get_by_type(
            content_type="reading",
            difficulty=profile.cefr_level,
            limit=6,
            random_order=True,
        )

    if not rows:
        console.print(
            Panel(
                "[yellow]No reading passages found in your knowledge base.[/yellow]\n"
                "Run [bold]english-coach ingest[/bold] to load your content files.",
                border_style="yellow",
            )
        )
        return {}

    # Pick best passage (longest chunk = most complete paragraph)
    passage_row = max(rows, key=lambda r: len(r["text"]))
    passage_text = passage_row["text"]
    chunk_id = passage_row["chunk_id"]

    # Mark as seen
    user_model.mark_seen(profile.user_id, [chunk_id])

    # Display passage
    _display_passage(passage_text, passage_row)

    stats = {"questions": 0, "correct": 0}

    # Generate questions
    if ai:
        console.print("\n[dim]Generating comprehension questions...[/dim]")
        with console.status("[bold blue]Preparing questions...[/bold blue]"):
            questions = ai.generate_comprehension_questions(
                passage=passage_text,
                cefr_level=profile.cefr_level,
                num_questions=3,
                exam=exam,
            )

        if questions:
            console.print(f"\n[bold]Answer these {len(questions)} questions:[/bold]\n")
            for i, q in enumerate(questions, 1):
                correct = _ask_question(i, q, profile.cefr_level)
                stats["questions"] += 1
                if correct:
                    stats["correct"] += 1
    else:
        console.print(
            "\n[dim]No API key — skipping comprehension questions. "
            "Add api_key to config.yaml to enable.[/dim]"
        )
        # Still count as a reading session
        stats["questions"] = 1
        stats["correct"] = 1

    # Update skill scores
    if stats["questions"] > 0:
        accuracy = stats["correct"] / stats["questions"]
        user_model.record_answer(
            profile.user_id, "reading_comprehension", accuracy >= 0.67
        )

    # Wrap up
    duration = int(time.time() - start_time)
    session_accuracy = stats["correct"] / max(stats["questions"], 1)
    user_model.end_session(session_id, duration, stats["questions"], session_accuracy)
    user_model.update_profile(profile)

    console.print(
        f"\n[bold]Session complete![/bold]  "
        f"Score: [{'green' if session_accuracy >= 0.67 else 'yellow'}]"
        f"{stats['correct']}/{stats['questions']}[/]  "
        f"({int(session_accuracy * 100)}%)\n"
    )

    if ai:
        console.print(f"[dim]{ai.usage_summary()}[/dim]\n")

    # Offer to extract and save new words from the passage
    if ai and srs:
        _offer_word_extraction(passage_text, profile, srs=srs, ai=ai)

    return stats


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _display_passage(text: str, row) -> None:
    """Render the reading passage with metadata."""
    meta = row
    difficulty = meta["difficulty"] if "difficulty" in meta.keys() else "?"
    topic = meta["topic"] if "topic" in meta.keys() else ""

    subtitle = f"Difficulty: {difficulty}"
    if topic:
        subtitle += f"  ·  Topic: {topic}"

    console.print(Panel(
        text,
        title=f"[bold]Reading Passage[/bold]  [dim]{subtitle}[/dim]",
        border_style="blue",
        padding=(1, 2),
    ))

    word_count = len(text.split())
    console.print(f"[dim]  {word_count} words[/dim]\n")
    input("  [dim]Press Enter when you have finished reading...[/dim]")


def _ask_question(num: int, q: dict, cefr_level: str) -> bool:
    """
    Display one comprehension question and evaluate the answer.
    For open-ended questions, does a simple keyword overlap check.
    Returns True if answer is acceptable.
    """
    q_type = q.get("type", "factual")
    question = q.get("question", "")
    answer = q.get("answer", "")
    explanation = q.get("explanation", "")

    type_label = {"factual": "Factual", "inference": "Inference", "vocabulary": "Vocabulary"}.get(
        q_type, q_type.title()
    )

    console.print(f"[bold cyan]Q{num}[/bold cyan] [{type_label}]  {question}\n")
    user_answer = Prompt.ask("  Your answer").strip()

    if not user_answer:
        console.print(f"  [dim]Correct answer: {answer}[/dim]\n")
        return False

    # Simple keyword overlap scoring (no API cost)
    correct = _keyword_match(user_answer, answer)

    if correct:
        console.print(f"  [green]✓ Good![/green]  {explanation}\n")
    else:
        console.print(
            f"  [yellow]→ Model answer:[/yellow] {answer}\n"
            f"  [dim]{explanation}[/dim]\n"
        )

    return correct


def _offer_word_extraction(
    passage: str,
    profile: UserProfile,
    srs: SM2Engine,
    ai: AIClient,
) -> None:
    """Ask AI to pick hard words from the passage and offer to add them to SRS."""
    from rich.prompt import Confirm
    try:
        if not Confirm.ask("\n  Extract new vocabulary from this passage?", default=True):
            return
    except (EOFError, KeyboardInterrupt):
        return

    prompt = (
        f"Student CEFR level: {profile.cefr_level}. Exam: {profile.target_exam.upper()}.\n\n"
        f"PASSAGE:\n{passage[:2000]}\n\n"
        f"List up to 6 words from this passage that are challenging for a {profile.cefr_level} student "
        f"and worth learning. Exclude very common words.\n"
        f"Return ONLY a JSON array of strings: [\"word1\", \"word2\", ...]"
    )

    try:
        with console.status("[bold blue]Extracting vocabulary...[/bold blue]"):
            raw = ai.complete(prompt, max_tokens=150)
        import json, re
        m = re.search(r'\[.*?\]', raw, re.DOTALL)
        words = json.loads(m.group()) if m else []
    except Exception:
        return

    if not words:
        console.print("[dim]No new words found.[/dim]\n")
        return

    # Filter out words already in deck
    new_words = []
    for w in words:
        w = w.strip().lower()
        existing = srs._db.execute(
            """SELECT c.card_id FROM srs_cards c
               JOIN vocabulary v ON c.word_id = v.word_id
               WHERE c.user_id = ? AND v.word = ?""",
            (profile.user_id, w),
        ).fetchone()
        if not existing:
            new_words.append(w)

    if not new_words:
        console.print("[dim]All extracted words are already in your deck.[/dim]\n")
        return

    console.print(f"\n  Found [cyan]{len(new_words)}[/cyan] new words: "
                  + ", ".join(f"[bold]{w}[/bold]" for w in new_words) + "\n")

    try:
        if not Confirm.ask(f"  Add all {len(new_words)} words to your deck (AI will enrich each)?", default=True):
            return
    except (EOFError, KeyboardInterrupt):
        return

    added = 0
    for w in new_words:
        try:
            with console.status(f"[bold blue]Enriching '{w}'...[/bold blue]"):
                data = ai.enrich_word(w, profile.cefr_level, profile.target_exam)
            wid = srs.add_word(
                word=w,
                definition_en=data.get("definition_en", ""),
                definition_zh=data.get("definition_zh", ""),
                example=data.get("example", ""),
                synonyms=data.get("synonyms", ""),
                antonyms=data.get("antonyms", ""),
                derivatives=data.get("derivatives", ""),
                collocations=data.get("collocations", ""),
                context_sentence=data.get("context_sentence", ""),
                part_of_speech=data.get("part_of_speech", ""),
                pronunciation=data.get("pronunciation", ""),
                source="reading",
            )
            srs.update_word_fields(wid, enriched=1)
            srs.enroll_words(profile.user_id, [wid])
            console.print(f"  [green]+[/green] {w}")
            added += 1
        except Exception:
            console.print(f"  [yellow]skipped {w}[/yellow]")

    console.print(f"\n[green]Added {added} words to your deck.[/green]\n")


def _keyword_match(user_answer: str, model_answer: str, threshold: float = 0.35) -> bool:
    """
    Lightweight answer scoring: keyword overlap ratio.
    No API call needed for basic factual questions.
    """
    def tokens(text: str) -> set[str]:
        import re
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
        stops = {"the", "and", "for", "are", "was", "were", "that", "this",
                 "with", "from", "have", "has", "been", "they", "their",
                 "which", "when", "what", "how", "can", "will", "not"}
        return {w for w in words if w not in stops}

    user_tokens = tokens(user_answer)
    model_tokens = tokens(model_answer)

    if not model_tokens:
        return True  # Can't evaluate, give benefit of doubt

    overlap = len(user_tokens & model_tokens) / len(model_tokens)
    return overlap >= threshold
