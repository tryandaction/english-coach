"""
Offline word lookup — zero API cost, zero network.
Searches the local knowledge base and SRS vocabulary for a word,
then optionally adds it to the SRS deck.
Falls back to AI definition only if API key is configured.
"""

from __future__ import annotations

import re
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Prompt, Confirm

from core.knowledge_base.store import KnowledgeBase
from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel, UserProfile
from ai.client import AIClient
from cli.display import print_header

console = Console()


def run_lookup(
    word: str | None,
    kb: KnowledgeBase,
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
) -> None:
    print_header("Word Lookup  /  单词查询")

    if not word:
        try:
            word = Prompt.ask("  Word to look up").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

    if not word:
        return

    console.print(f"\n  Looking up: [bold cyan]{word}[/bold cyan]\n")

    # 1. Check SRS deck first (fastest, most personalised)
    srs_result = _lookup_srs(word, srs, profile)

    # 2. Search knowledge base
    kb_results = _lookup_kb(word, kb)

    # 3. If nothing found locally and AI available, fetch definition
    if not srs_result and not kb_results and ai:
        ai_result = _lookup_ai(word, ai, profile)
    else:
        ai_result = None

    # Display results
    if srs_result:
        _display_srs_card(srs_result)
    elif kb_results:
        _display_kb_results(word, kb_results)
    elif ai_result:
        _display_ai_result(word, ai_result)
    else:
        console.print(
            f"  [yellow]'{word}' not found in your knowledge base or SRS deck.[/yellow]\n"
            "  Try ingesting more content or add it manually with "
            "[bold]english-coach words --action add[/bold]\n"
        )
        return

    # Offer to add to SRS deck if not already enrolled
    if not srs_result:
        _offer_enroll(word, kb_results, ai_result, srs, profile)


# ------------------------------------------------------------------
# Lookup sources
# ------------------------------------------------------------------

def _lookup_srs(word: str, srs: SM2Engine, profile: UserProfile) -> Optional[dict]:
    """Check if word is in the user's SRS deck."""
    row = srs._db.execute(
        """SELECT v.word, v.definition_en, v.definition_zh, v.example,
                  v.topic, v.difficulty,
                  c.interval, c.repetitions, c.easiness,
                  c.due_date, c.total_reviews, c.correct_reviews
           FROM vocabulary v
           LEFT JOIN srs_cards c ON c.word_id = v.word_id AND c.user_id = ?
           WHERE v.word = ?""",
        (profile.user_id, word),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def _lookup_kb(word: str, kb: KnowledgeBase) -> list[dict]:
    """Search knowledge base for chunks containing the word."""
    results = kb.search(query=word, limit=5)
    # Filter to chunks that actually contain the word
    filtered = []
    pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
    for r in results:
        row = dict(r) if not isinstance(r, dict) else r
        text = row.get("text", "")
        if pattern.search(text):
            filtered.append(row)
    return filtered[:3]


def _lookup_ai(word: str, ai: AIClient, profile: UserProfile) -> Optional[dict]:
    """Get AI definition — only called when local lookup fails."""
    prompt = (
        f"Define the English word '{word}' for a CEFR {profile.cefr_level} student "
        f"targeting {profile.target_exam.upper()}.\n"
        f"Return JSON only:\n"
        f'{{"definition_en":"...","definition_zh":"...","example":"...","part_of_speech":"...","synonyms":["..."]}}'
    )
    cache_key = f"lookup|{word}|{profile.cefr_level}"
    try:
        raw = ai.complete(prompt, cache_key=cache_key, max_tokens=200)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1:
            import json
            return json.loads(raw[start:end])
    except Exception:
        pass
    return None


# ------------------------------------------------------------------
# Display
# ------------------------------------------------------------------

def _display_srs_card(card: dict) -> None:
    enrolled = card.get("interval") is not None
    status = ""
    if enrolled:
        interval = card["interval"] or 1
        reps = card["repetitions"] or 0
        accuracy = (card["correct_reviews"] or 0) / max(card["total_reviews"] or 1, 1)
        acc_color = "green" if accuracy >= 0.8 else "yellow" if accuracy >= 0.6 else "red"
        status = (
            f"\n\n[dim]SRS: interval {interval}d · "
            f"reps {reps} · "
            f"accuracy [{acc_color}]{int(accuracy*100)}%[/{acc_color}][/dim]"
        )

    body = f"[bold white]{card['word']}[/bold white]\n\n"
    if card.get("definition_en"):
        body += f"[cyan]{card['definition_en']}[/cyan]\n"
    if card.get("definition_zh"):
        body += f"[dim]{card['definition_zh']}[/dim]\n"
    if card.get("example"):
        body += f'\n[italic]"{card["example"]}"[/italic]'
    if card.get("topic"):
        body += f"\n[dim]{card['topic']} · {card.get('difficulty','')}"
    body += status

    label = "[green]In your SRS deck[/green]" if enrolled else "[dim]In vocabulary (not enrolled)[/dim]"
    console.print(Panel(body.strip(), title=label, border_style="green" if enrolled else "blue", padding=(1, 4)))
    console.print()


def _display_kb_results(word: str, results: list[dict]) -> None:
    console.print(f"  Found [cyan]{len(results)}[/cyan] passage(s) containing '[bold]{word}[/bold]':\n")
    for i, r in enumerate(results, 1):
        text = r.get("text", "")
        # Highlight the word in context
        snippet = _extract_snippet(text, word, context_chars=150)
        source = r.get("source_file", "")
        difficulty = r.get("difficulty", "")
        console.print(
            f"  [dim]{i}. {source}  {difficulty}[/dim]\n"
            f"  ...{snippet}...\n"
        )


def _display_ai_result(word: str, result: dict) -> None:
    body = f"[bold white]{word}[/bold white]"
    if result.get("part_of_speech"):
        body += f"  [dim]{result['part_of_speech']}[/dim]"
    body += "\n\n"
    if result.get("definition_en"):
        body += f"[cyan]{result['definition_en']}[/cyan]\n"
    if result.get("definition_zh"):
        body += f"[dim]{result['definition_zh']}[/dim]\n"
    if result.get("example"):
        body += f'\n[italic]"{result["example"]}"[/italic]\n'
    if result.get("synonyms"):
        syns = ", ".join(result["synonyms"][:4])
        body += f"\n[dim]Synonyms: {syns}[/dim]"

    console.print(Panel(body.strip(), title="[dim]AI Definition[/dim]", border_style="blue", padding=(1, 4)))
    console.print()


# ------------------------------------------------------------------
# Enroll offer
# ------------------------------------------------------------------

def _offer_enroll(
    word: str,
    kb_results: list[dict],
    ai_result: Optional[dict],
    srs: SM2Engine,
    profile: UserProfile,
) -> None:
    # Check if already in vocabulary table (just not enrolled)
    existing = srs._db.execute(
        "SELECT word_id FROM vocabulary WHERE word=?", (word,)
    ).fetchone()

    if existing:
        enrolled = srs._db.execute(
            "SELECT 1 FROM srs_cards WHERE user_id=? AND word_id=?",
            (profile.user_id, existing["word_id"]),
        ).fetchone()
        if enrolled:
            return  # already in deck

    try:
        if not Confirm.ask(f"  Add '[bold]{word}[/bold]' to your SRS deck?", default=True):
            return
    except (EOFError, KeyboardInterrupt):
        return

    # Build definition from best available source
    defn_en, defn_zh, example, topic, difficulty = "", "", "", "general", "B1"

    if ai_result:
        defn_en = ai_result.get("definition_en", "")
        defn_zh = ai_result.get("definition_zh", "")
        example = ai_result.get("example", "")
    elif kb_results:
        # Extract from KB snippet
        text = kb_results[0].get("text", "")
        defn_en = _extract_snippet(text, word, context_chars=80)
        topic = kb_results[0].get("topic", "general")
        difficulty = kb_results[0].get("difficulty", "B1")

    if not defn_en:
        try:
            defn_en = Prompt.ask("  Definition (English)")
            defn_zh = Prompt.ask("  Definition (Chinese, optional)", default="")
        except (EOFError, KeyboardInterrupt):
            return

    word_id = srs.add_word(
        word=word,
        definition_en=defn_en,
        definition_zh=defn_zh,
        example=example,
        topic=topic,
        difficulty=difficulty,
        source="lookup",
    )
    added = srs.enroll_words(profile.user_id, [word_id])
    if added:
        console.print(f"  [green]Added '{word}' to your SRS deck.[/green]\n")
    else:
        console.print(f"  [dim]'{word}' was already in your deck.[/dim]\n")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_snippet(text: str, word: str, context_chars: int = 150) -> str:
    """Extract a snippet of text around the first occurrence of word."""
    pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return text[:context_chars]
    start = max(0, m.start() - context_chars // 2)
    end = min(len(text), m.end() + context_chars // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    # Bold the matched word
    snippet = pattern.sub(f"[bold]{word}[/bold]", snippet)
    return snippet
