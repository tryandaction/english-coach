"""
Daily study plan mode — auto-picks the best sequence of activities
based on the user's weak areas, due SRS cards, and session time budget.
Zero API cost for planning; individual modes may use API as normal.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Confirm

from core.knowledge_base.store import KnowledgeBase
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel, UserProfile
from ai.client import AIClient
from cli.display import print_header

console = Console()


def run_daily_plan(
    kb: KnowledgeBase,
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    minutes: int = 30,
) -> None:
    """
    Build and execute a personalized daily study plan.
    Allocates time across modes based on:
    - Due SRS cards (always first)
    - Weakest skill areas
    - Exam focus
    - Available time budget
    """
    print_header(
        "每日学习计划  ·  Daily Study Plan",
        subtitle=f"Budget: {minutes} min · CEFR {profile.cefr_level} · {profile.target_exam.upper()}",
    )

    plan = _build_plan(srs, user_model, profile, minutes)
    _display_plan(plan)

    if not Confirm.ask("\n  Start this plan?", default=True):
        return

    start = time.time()
    for step in plan:
        elapsed = int((time.time() - start) / 60)
        if elapsed >= minutes:
            console.print("[dim]Time budget reached. Great work![/dim]")
            break

        console.print(f"\n[bold cyan]▶ {step['label']}[/bold cyan]\n")
        _run_step(step, kb, srs, user_model, profile, ai)

    total = int(time.time() - start)
    console.print(
        f"\n[bold green]Daily plan complete![/bold green]  "
        f"Total time: {total // 60}m {total % 60}s\n"
    )


# ------------------------------------------------------------------
# Plan builder
# ------------------------------------------------------------------

def _build_plan(
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    minutes: int,
) -> list[dict]:
    """
    Allocate study time across modes.
    Returns ordered list of steps with mode, params, label, est_minutes.
    """
    plan = []
    budget = minutes
    deck = srs.deck_stats(profile.user_id)
    weak = user_model.get_weak_areas(profile.user_id, threshold=0.60)
    scores = user_model.get_skill_scores(profile.user_id)

    # 1. SRS vocab — always first if cards are due
    due = deck.get("due_today", 0)
    if due > 0:
        cards = min(due, 20)
        est = max(3, cards // 5)
        plan.append({
            "mode": "vocab",
            "label": f"Vocabulary SRS — {cards} due cards",
            "params": {"max_cards": cards},
            "est_minutes": est,
        })
        budget -= est

    # 2. Grammar — if grammar skills are weak
    grammar_score = min(
        scores.get("grammar_articles", 0.5),
        scores.get("grammar_preposition", 0.5),
        scores.get("grammar_tense", 0.5),
    )
    if grammar_score < 0.65 and budget >= 5:
        # Pick weakest grammar category
        focus = None
        if scores.get("grammar_articles", 0.5) <= grammar_score:
            focus = "articles"
        elif scores.get("grammar_preposition", 0.5) <= grammar_score:
            focus = "prepositions"
        else:
            focus = "tense"
        plan.append({
            "mode": "grammar",
            "label": f"Grammar Drills — {focus} (weak area)",
            "params": {"focus": focus, "num_questions": 8},
            "est_minutes": 5,
        })
        budget -= 5

    # 3. Reading — if budget allows
    if budget >= 8:
        plan.append({
            "mode": "read",
            "label": "Reading Comprehension",
            "params": {},
            "est_minutes": 8,
        })
        budget -= 8

    # 4. Speaking or Writing — alternate based on exam and weak areas
    speaking_weak = (
        scores.get("speaking_structure", 0.5) < 0.65
        or scores.get("speaking_vocabulary", 0.5) < 0.65
    )
    writing_weak = (
        scores.get("writing_coherence", 0.5) < 0.65
        or scores.get("writing_grammar", 0.5) < 0.65
    )

    exam = profile.target_exam or "general"
    if budget >= 10:
        if exam in ("toefl", "ielts") and speaking_weak:
            plan.append({
                "mode": "speak",
                "label": "Speaking Practice — Task 1",
                "params": {"task": "task1"},
                "est_minutes": 10,
            })
            budget -= 10
        elif writing_weak or exam in ("gre",):
            plan.append({
                "mode": "write",
                "label": "Writing Practice",
                "params": {},
                "est_minutes": 15,
            })
            budget -= 15

    # 5. New vocab enrollment — if time remains and deck is small
    total_words = deck.get("total", 0)
    if budget >= 3 and total_words < 100:
        plan.append({
            "mode": "enroll_vocab",
            "label": "Add new vocabulary words from knowledge base",
            "params": {"count": 10},
            "est_minutes": 2,
        })
        budget -= 2

    return plan


def _display_plan(plan: list[dict]) -> None:
    """Render the plan as a table."""
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, padding=(0, 2))
    table.add_column("#", style="dim", width=3)
    table.add_column("Activity", style="bold")
    table.add_column("Est.", justify="right", style="dim")

    total_est = 0
    for i, step in enumerate(plan, 1):
        est = step.get("est_minutes", "?")
        total_est += est if isinstance(est, int) else 0
        table.add_row(str(i), step["label"], f"{est}m")

    table.add_section()
    table.add_row("", "[bold]Total[/bold]", f"[bold]{total_est}m[/bold]")

    console.print(Panel(
        table,
        title="[bold cyan]Your Study Plan[/bold cyan]",
        border_style="cyan",
    ))


def _run_step(
    step: dict,
    kb: KnowledgeBase,
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
) -> None:
    """Execute one plan step by delegating to the appropriate mode."""
    mode = step["mode"]
    params = step.get("params", {})

    if mode == "vocab":
        from modes.vocab import run_vocab_session
        run_vocab_session(srs, user_model, profile, max_cards=params.get("max_cards", 20))

    elif mode == "grammar":
        from modes.grammar import run_grammar_session
        run_grammar_session(
            user_model, profile, ai,
            focus=params.get("focus"),
            num_questions=params.get("num_questions", 8),
        )

    elif mode == "read":
        from modes.reading import run_reading_session
        run_reading_session(kb, user_model, profile, ai)

    elif mode == "speak":
        from modes.speaking import run_speaking_session
        run_speaking_session(kb, user_model, profile, ai, task=params.get("task"))

    elif mode == "write":
        from modes.writing import run_writing_session
        run_writing_session(user_model, profile, ai)

    elif mode == "enroll_vocab":
        _enroll_new_words(kb, srs, user_model, profile, count=params.get("count", 10))


def _enroll_new_words(
    kb: KnowledgeBase,
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    count: int = 10,
) -> None:
    """Pull vocab chunks from KB and enroll them into the SRS deck."""
    rows = kb.get_by_type(
        content_type="vocab",
        difficulty=profile.cefr_level,
        exam=profile.target_exam,
        limit=count * 3,
        random_order=True,
    )

    enrolled = 0
    for row in rows:
        if enrolled >= count:
            break
        text = row["text"].strip()
        # Parse simple "word — definition" or "**word**: definition" patterns
        word, defn_en = _parse_vocab_entry(text)
        if not word or len(word) > 40:
            continue
        wid = srs.add_word(
            word=word,
            definition_en=defn_en or text[:80],
            definition_zh="",
            example="",
            topic=row.get("topic", "general"),
            difficulty=row.get("difficulty", "B1"),
            source=row.get("source_file", "kb"),
        )
        enrolled += srs.enroll_words(profile.user_id, [wid])

    if enrolled:
        console.print(f"  [green]✓ Added {enrolled} new words to your SRS deck[/green]")
    else:
        console.print("  [dim]No new vocab entries found to enroll.[/dim]")


def _parse_vocab_entry(text: str) -> tuple[str, str]:
    """Extract (word, definition) from common vocab entry formats."""
    import re
    # **word**: definition
    m = re.match(r"\*\*(.+?)\*\*[:\s—-]+(.+)", text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).split("\n")[0].strip()
    # word — definition
    m = re.match(r"^([A-Za-z\-]+)\s*[—–-]+\s*(.+)", text)
    if m:
        return m.group(1).strip(), m.group(2).split("\n")[0].strip()
    # `word` definition
    m = re.match(r"`(.+?)`[:\s]+(.+)", text)
    if m:
        return m.group(1).strip(), m.group(2).split("\n")[0].strip()
    return "", ""
