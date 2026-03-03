"""
Words management command — add, list, search, view, enrich vocabulary.
Supports rich card view with all enrichment fields, AI auto-fill, and TTS.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich import box
from rich.prompt import Prompt, Confirm
from rich.text import Text

from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel, UserProfile
from ai.client import AIClient
from cli.display import print_header

console = Console()


def run_words_manager(
    srs: SM2Engine,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient] = None,
    action: Optional[str] = None,
    query: Optional[str] = None,
) -> None:
    print_header("词汇管理  /  Word Manager", subtitle=f"Deck for {profile.name}")

    if not action:
        action = Prompt.ask(
            "Action",
            choices=["list", "add", "search", "view", "enrich", "stats"],
            default="list",
        )

    if action == "list":
        _list_words(srs, profile)
    elif action == "add":
        _add_word_interactive(srs, profile, ai)
    elif action == "search":
        q = query or Prompt.ask("Search word")
        _search_words(srs, profile, q)
    elif action == "view":
        w = query or Prompt.ask("Word to view")
        _view_card(srs, profile, w.strip().lower())
    elif action == "enrich":
        _enrich_deck(srs, profile, ai)
    elif action == "stats":
        _show_stats(srs, profile)


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------

def _list_words(srs: SM2Engine, profile: UserProfile, limit: int = 40) -> None:
    from datetime import date
    today = date.today().isoformat()

    rows = srs._db.execute(
        """SELECT v.word, v.definition_en, v.part_of_speech, v.difficulty, v.topic,
                  v.enriched, c.interval, c.repetitions, c.due_date,
                  c.total_reviews, c.correct_reviews
           FROM srs_cards c
           JOIN vocabulary v ON c.word_id = v.word_id
           WHERE c.user_id = ?
           ORDER BY c.due_date ASC
           LIMIT ?""",
        (profile.user_id, limit),
    ).fetchall()

    if not rows:
        console.print("[yellow]No words in your deck yet.[/yellow]")
        console.print("Run [bold]english-coach vocab[/bold] or use [bold]add[/bold] to add words.")
        return

    table = Table(box=box.ROUNDED, border_style="dim", show_header=True, padding=(0, 1))
    table.add_column("Word", style="bold", min_width=14)
    table.add_column("POS", width=5, justify="center")
    table.add_column("Definition", max_width=34)
    table.add_column("Lvl", justify="center", width=4)
    table.add_column("Due", justify="center", width=10)
    table.add_column("Ivl", justify="right", width=5)
    table.add_column("Acc", justify="right", width=5)
    table.add_column("AI", justify="center", width=3)

    for r in rows:
        due = r["due_date"] or "-"
        overdue = due < today
        due_str = f"[red]{due}[/red]" if overdue else f"[green]{due}[/green]" if due == today else f"[dim]{due}[/dim]"
        acc = (r["correct_reviews"] or 0) / max(r["total_reviews"] or 1, 1)
        acc_color = "green" if acc >= 0.75 else "yellow" if acc >= 0.5 else "red"
        enriched = "[cyan]*[/cyan]" if r["enriched"] else "[dim]-[/dim]"
        pos = (r["part_of_speech"] or "")[:4]

        table.add_row(
            r["word"],
            f"[dim]{pos}[/dim]",
            (r["definition_en"] or "")[:34],
            r["difficulty"] or "?",
            due_str,
            f"{r['interval']}d",
            f"[{acc_color}]{int(acc*100)}%[/{acc_color}]",
            enriched,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(rows)} words. [cyan]*[/cyan] = AI-enriched. Sorted by due date.[/dim]\n")


# ------------------------------------------------------------------
# Rich card view
# ------------------------------------------------------------------

def _view_card(srs: SM2Engine, profile: UserProfile, word: str) -> None:
    row = srs._db.execute(
        """SELECT v.*, c.interval, c.repetitions, c.easiness,
                  c.due_date, c.total_reviews, c.correct_reviews
           FROM vocabulary v
           LEFT JOIN srs_cards c ON c.word_id = v.word_id AND c.user_id = ?
           WHERE v.word = ?""",
        (profile.user_id, word),
    ).fetchone()

    if not row:
        console.print(f"[yellow]'{word}' not found in vocabulary.[/yellow]\n")
        return

    r = dict(row)
    _print_rich_card(r)

    # Offer TTS
    try:
        from ai.tts import speak
        if Confirm.ask("  Hear pronunciation?", default=False):
            spoken = speak(word)
            if not spoken:
                console.print("[dim]TTS unavailable. Install edge-tts: pip install edge-tts[/dim]")
    except (EOFError, KeyboardInterrupt):
        pass


def _print_rich_card(r: dict) -> None:
    """Render a full vocabulary card with all enrichment fields."""
    word = r.get("word", "")
    pos = r.get("part_of_speech", "")
    pron = r.get("pronunciation", "")

    # Header line
    header = f"[bold white]{word}[/bold white]"
    if pos:
        header += f"  [dim italic]{pos}[/dim italic]"
    if pron:
        header += f"  [cyan]{pron}[/cyan]"

    body = header + "\n\n"

    if r.get("definition_en"):
        body += f"[bold]Definition:[/bold] {r['definition_en']}\n"
    if r.get("definition_zh"):
        body += f"[dim]{r['definition_zh']}[/dim]\n"

    if r.get("example"):
        body += f"\n[bold]Example:[/bold]\n[italic]\"{r['example']}\"[/italic]\n"

    if r.get("context_sentence"):
        body += f"\n[bold]In context:[/bold]\n[italic]\"{r['context_sentence']}\"[/italic]\n"

    if r.get("synonyms"):
        body += f"\n[bold]Synonyms:[/bold] [green]{r['synonyms']}[/green]"
    if r.get("antonyms"):
        body += f"\n[bold]Antonyms:[/bold] [red]{r['antonyms']}[/red]"
    if r.get("derivatives"):
        body += f"\n[bold]Derivatives:[/bold] [yellow]{r['derivatives']}[/yellow]"
    if r.get("collocations"):
        body += f"\n[bold]Collocations:[/bold] [cyan]{r['collocations']}[/cyan]"

    # SRS state
    if r.get("interval") is not None:
        acc = (r.get("correct_reviews") or 0) / max(r.get("total_reviews") or 1, 1)
        acc_color = "green" if acc >= 0.75 else "yellow" if acc >= 0.5 else "red"
        body += (
            f"\n\n[dim]SRS: interval {r['interval']}d  "
            f"reps {r.get('repetitions', 0)}  "
            f"accuracy [{acc_color}]{int(acc*100)}%[/{acc_color}]  "
            f"due {r.get('due_date', '?')}[/dim]"
        )

    enriched = r.get("enriched", 0)
    title = f"[bold cyan]{r.get('topic','general')}[/bold cyan]  [dim]{r.get('difficulty','?')}[/dim]"
    if enriched:
        title += "  [cyan][AI][/cyan]"

    console.print(Panel(body.strip(), title=title, border_style="cyan", padding=(1, 4)))
    console.print()


# ------------------------------------------------------------------
# Add word (with optional AI enrichment)
# ------------------------------------------------------------------

def _add_word_interactive(
    srs: SM2Engine,
    profile: UserProfile,
    ai: Optional[AIClient],
) -> None:
    console.print("\n[bold]Add a new word[/bold] (Ctrl+C to cancel)\n")

    try:
        word = Prompt.ask("  Word").strip().lower()
        if not word:
            return

        existing = srs._db.execute(
            "SELECT word_id FROM vocabulary WHERE word=?", (word,)
        ).fetchone()
        if existing:
            already = srs._db.execute(
                "SELECT card_id FROM srs_cards WHERE user_id=? AND word_id=?",
                (profile.user_id, existing["word_id"]),
            ).fetchone()
            if already:
                console.print(f"[yellow]'{word}' is already in your deck.[/yellow]")
                _view_card(srs, profile, word)
                return

        # Try AI enrichment first
        enriched_data = {}
        if ai:
            try:
                with console.status(f"[bold blue]AI enriching '{word}'...[/bold blue]"):
                    enriched_data = ai.enrich_word(word, profile.cefr_level, profile.target_exam)
            except Exception:
                pass

        if enriched_data and enriched_data.get("definition_en"):
            _print_rich_card({**enriched_data, "word": word, "enriched": 1,
                              "topic": "general", "difficulty": profile.cefr_level})
            if not Confirm.ask("  Use this AI-generated card?", default=True):
                enriched_data = {}

        if not enriched_data:
            defn_en = Prompt.ask("  Definition (English)").strip()
            defn_zh = Prompt.ask("  Definition (Chinese, optional)", default="").strip()
            example = Prompt.ask("  Example sentence (optional)", default="").strip()
            enriched_data = {"definition_en": defn_en, "definition_zh": defn_zh, "example": example}

        topic = Prompt.ask(
            "  Topic", choices=["general", "academic", "physics", "toefl", "gre"], default="general"
        )
        difficulty = Prompt.ask(
            "  Difficulty", choices=["A2", "B1", "B2", "C1", "C2"], default=profile.cefr_level
        )

        wid = srs.add_word(
            word=word,
            definition_en=enriched_data.get("definition_en", ""),
            definition_zh=enriched_data.get("definition_zh", ""),
            example=enriched_data.get("example", ""),
            topic=topic,
            difficulty=difficulty,
            source="manual",
            synonyms=enriched_data.get("synonyms", ""),
            antonyms=enriched_data.get("antonyms", ""),
            derivatives=enriched_data.get("derivatives", ""),
            collocations=enriched_data.get("collocations", ""),
            context_sentence=enriched_data.get("context_sentence", ""),
            part_of_speech=enriched_data.get("part_of_speech", ""),
            pronunciation=enriched_data.get("pronunciation", ""),
        )
        if enriched_data.get("definition_en"):
            srs.update_word_fields(wid, enriched=1)

        enrolled = srs.enroll_words(profile.user_id, [wid])
        if enrolled:
            console.print(f"\n[green]'{word}' added to your deck![/green]\n")
        else:
            console.print(f"\n[dim]'{word}' was already in your deck.[/dim]\n")

    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled.[/dim]\n")


# ------------------------------------------------------------------
# Enrich existing deck
# ------------------------------------------------------------------

def _enrich_deck(srs: SM2Engine, profile: UserProfile, ai: Optional[AIClient]) -> None:
    """AI-enrich all words in deck that haven't been enriched yet."""
    if not ai:
        console.print("[yellow]No AI configured. Run setup to add an API key.[/yellow]\n")
        return

    rows = srs._db.execute(
        """SELECT v.word_id, v.word FROM vocabulary v
           JOIN srs_cards c ON c.word_id = v.word_id
           WHERE c.user_id = ? AND (v.enriched = 0 OR v.enriched IS NULL)
           ORDER BY v.word""",
        (profile.user_id,),
    ).fetchall()

    if not rows:
        console.print("[green]All words in your deck are already enriched.[/green]\n")
        return

    console.print(f"  [cyan]{len(rows)}[/cyan] words need enrichment.\n")
    if not Confirm.ask(f"  Enrich all {len(rows)} words with AI?", default=True):
        return

    ok = 0
    for i, row in enumerate(rows, 1):
        word = row["word"]
        console.print(f"  [{i}/{len(rows)}] {word}...", end=" ")
        try:
            data = ai.enrich_word(word, profile.cefr_level, profile.target_exam)
            if data.get("definition_en"):
                srs.update_word_fields(
                    row["word_id"],
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
                    enriched=1,
                )
                console.print("[green]done[/green]")
                ok += 1
            else:
                console.print("[yellow]skipped[/yellow]")
        except Exception as e:
            console.print(f"[red]error[/red]")

    console.print(f"\n[green]Enriched {ok}/{len(rows)} words.[/green]\n")


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

def _search_words(srs: SM2Engine, profile: UserProfile, query: str) -> None:
    rows = srs._db.execute(
        """SELECT v.word, v.definition_en, v.definition_zh, v.difficulty, v.topic,
                  v.part_of_speech, v.enriched, c.interval, c.due_date, c.total_reviews
           FROM vocabulary v
           LEFT JOIN srs_cards c ON v.word_id = c.word_id AND c.user_id = ?
           WHERE v.word LIKE ? OR v.definition_en LIKE ? OR v.synonyms LIKE ?
           ORDER BY v.word ASC
           LIMIT 20""",
        (profile.user_id, f"%{query}%", f"%{query}%", f"%{query}%"),
    ).fetchall()

    if not rows:
        console.print(f"[yellow]No results for '{query}'[/yellow]\n")
        return

    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("Word", style="bold", min_width=14)
    table.add_column("POS", width=6)
    table.add_column("Definition", max_width=38)
    table.add_column("Lvl", justify="center", width=4)
    table.add_column("Deck", justify="center", width=5)
    table.add_column("AI", justify="center", width=3)

    for r in rows:
        in_deck = "[green]yes[/green]" if r["interval"] is not None else "[dim]no[/dim]"
        enriched = "[cyan]*[/cyan]" if r["enriched"] else "[dim]-[/dim]"
        table.add_row(
            r["word"],
            (r["part_of_speech"] or "")[:6],
            (r["definition_en"] or "")[:38],
            r["difficulty"] or "?",
            in_deck,
            enriched,
        )

    console.print(table)
    console.print(f"\n[dim]{len(rows)} result(s) for '{query}'[/dim]\n")

    # Offer to view a card
    try:
        pick = Prompt.ask("  View card (enter word, or blank to skip)", default="")
        if pick.strip():
            _view_card(srs, profile, pick.strip().lower())
    except (EOFError, KeyboardInterrupt):
        pass

    # Offer to enroll unenrolled words
    not_enrolled = [r for r in rows if r["interval"] is None]
    if not_enrolled:
        try:
            if Confirm.ask(f"  Add {len(not_enrolled)} unenrolled word(s) to your deck?", default=False):
                for r in not_enrolled:
                    wid = srs._db.execute(
                        "SELECT word_id FROM vocabulary WHERE word=?", (r["word"],)
                    ).fetchone()["word_id"]
                    srs.enroll_words(profile.user_id, [wid])
                console.print(f"[green]Added {len(not_enrolled)} words.[/green]\n")
        except (EOFError, KeyboardInterrupt):
            pass


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

def _show_stats(srs: SM2Engine, profile: UserProfile) -> None:
    from datetime import date
    today = date.today().isoformat()

    stats = srs.deck_stats(profile.user_id)

    diff_rows = srs._db.execute(
        """SELECT v.difficulty, COUNT(*) as cnt
           FROM srs_cards c JOIN vocabulary v ON c.word_id = v.word_id
           WHERE c.user_id = ?
           GROUP BY v.difficulty ORDER BY v.difficulty""",
        (profile.user_id,),
    ).fetchall()

    topic_rows = srs._db.execute(
        """SELECT v.topic, COUNT(*) as cnt
           FROM srs_cards c JOIN vocabulary v ON c.word_id = v.word_id
           WHERE c.user_id = ?
           GROUP BY v.topic ORDER BY cnt DESC""",
        (profile.user_id,),
    ).fetchall()

    acc_row = srs._db.execute(
        """SELECT SUM(total_reviews) as total, SUM(correct_reviews) as correct
           FROM srs_cards WHERE user_id=?""",
        (profile.user_id,),
    ).fetchone()

    enriched_count = srs._db.execute(
        """SELECT COUNT(*) FROM vocabulary v JOIN srs_cards c ON c.word_id = v.word_id
           WHERE c.user_id = ? AND v.enriched = 1""",
        (profile.user_id,),
    ).fetchone()[0]

    total_reviews = acc_row["total"] or 0
    correct_reviews = acc_row["correct"] or 0
    accuracy = correct_reviews / max(total_reviews, 1)

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")

    table.add_row("Total words", str(stats["total"]))
    table.add_row("Due today", f"[yellow]{stats['due_today']}[/yellow]")
    table.add_row("Mature (>=21d)", f"[green]{stats['mature']}[/green]")
    table.add_row("AI-enriched", f"[cyan]{enriched_count}[/cyan]")
    table.add_row("Total reviews", str(total_reviews))
    table.add_row("Overall accuracy", f"[{'green' if accuracy >= 0.75 else 'yellow'}]{int(accuracy*100)}%[/]")

    if diff_rows:
        table.add_section()
        for r in diff_rows:
            table.add_row(f"  Level {r['difficulty']}", str(r["cnt"]))

    if topic_rows:
        table.add_section()
        for r in topic_rows:
            table.add_row(f"  Topic: {r['topic']}", str(r["cnt"]))

    console.print(Panel(table, title="[bold cyan]SRS Deck Statistics[/bold cyan]", border_style="cyan"))
    console.print()
