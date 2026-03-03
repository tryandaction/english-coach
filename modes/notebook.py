"""
Notebook mode — daily writing journal with AI feedback.
Users write a short daily entry; AI gives brief inline corrections.
All entries stored locally in SQLite. Zero cost without API key.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
from rich.prompt import Prompt, Confirm

from core.user_model.profile import UserModel, UserProfile
from ai.client import AIClient
from cli.display import print_header

console = Console()

# Notebook DB lives alongside user.db
_NOTEBOOK_SCHEMA = """
    CREATE TABLE IF NOT EXISTS notebook_entries (
        entry_id    TEXT PRIMARY KEY,
        user_id     TEXT NOT NULL,
        entry_date  TEXT NOT NULL,
        prompt      TEXT,
        body        TEXT,
        word_count  INTEGER DEFAULT 0,
        ai_feedback TEXT,
        created_at  TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_notebook_user
        ON notebook_entries(user_id, entry_date);
"""

_DAILY_PROMPTS = [
    "Describe something you learned today.",
    "What is one scientific concept you find fascinating? Explain it simply.",
    "Write about a challenge you faced recently and how you handled it.",
    "Describe your ideal research project or career goal.",
    "What would you tell a younger student about studying for TOEFL/GRE?",
    "Explain a physics or engineering concept as if to a non-expert.",
    "Write about a book, paper, or article you read recently.",
    "Describe your hometown or university in detail.",
    "What are the pros and cons of studying abroad?",
    "Write about a person who has influenced your academic journey.",
    "Describe a typical day in your life as a student.",
    "What technology do you think will change science the most in 10 years?",
    "Write about an experiment or project you worked on.",
    "What does academic integrity mean to you?",
    "Describe the most interesting place you have ever visited.",
]


class NotebookDB:
    def __init__(self, db_path: Path):
        self._db = sqlite3.connect(str(db_path))
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_NOTEBOOK_SCHEMA)
        self._db.commit()

    def save_entry(
        self,
        user_id: str,
        body: str,
        prompt: str = "",
        ai_feedback: str = "",
    ) -> str:
        entry_id = uuid.uuid4().hex[:16]
        word_count = len(body.split())
        self._db.execute(
            """INSERT INTO notebook_entries
               (entry_id, user_id, entry_date, prompt, body, word_count, ai_feedback, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                entry_id, user_id, date.today().isoformat(),
                prompt, body, word_count, ai_feedback,
                datetime.now().isoformat(),
            ),
        )
        self._db.commit()
        return entry_id

    def get_entries(self, user_id: str, limit: int = 10) -> list[sqlite3.Row]:
        return self._db.execute(
            """SELECT entry_id, entry_date, prompt, body, word_count, ai_feedback
               FROM notebook_entries
               WHERE user_id=?
               ORDER BY entry_date DESC, created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()

    def already_wrote_today(self, user_id: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM notebook_entries WHERE user_id=? AND entry_date=?",
            (user_id, date.today().isoformat()),
        ).fetchone()
        return row is not None

    def streak(self, user_id: str) -> int:
        from datetime import timedelta
        rows = self._db.execute(
            "SELECT DISTINCT entry_date FROM notebook_entries "
            "WHERE user_id=? ORDER BY entry_date DESC",
            (user_id,),
        ).fetchall()
        days = {r["entry_date"] for r in rows}
        count = 0
        check = date.today()
        while check.isoformat() in days:
            count += 1
            check -= timedelta(days=1)
        return count

    def total_words(self, user_id: str) -> int:
        row = self._db.execute(
            "SELECT COALESCE(SUM(word_count),0) FROM notebook_entries WHERE user_id=?",
            (user_id,),
        ).fetchone()
        return row[0]


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def run_notebook_session(
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    data_dir: Path,
    action: str | None = None,
) -> None:
    nb = NotebookDB(data_dir / "notebook.db")

    print_header(
        "写作日记  ·  Writing Notebook",
        subtitle=f"CEFR {profile.cefr_level} · {profile.target_exam.upper()}",
    )

    if action is None:
        action = _pick_action(nb, profile)

    if action == "write":
        _write_entry(nb, user_model, profile, ai)
    elif action == "history":
        _show_history(nb, profile)
    elif action == "stats":
        _show_stats(nb, profile)


# ------------------------------------------------------------------
# Actions
# ------------------------------------------------------------------

def _pick_action(nb: NotebookDB, profile: UserProfile) -> str:
    wrote_today = nb.already_wrote_today(profile.user_id)
    streak = nb.streak(profile.user_id)
    total = nb.total_words(profile.user_id)

    console.print(
        f"  Streak: [yellow]{streak}d[/yellow]  ·  "
        f"Total words written: [cyan]{total}[/cyan]"
        + ("  ·  [green]✓ wrote today[/green]" if wrote_today else "")
    )
    console.print()
    console.print("  [cyan]write[/cyan]    — write today's entry")
    console.print("  [cyan]history[/cyan]  — view past entries")
    console.print("  [cyan]stats[/cyan]    — writing statistics")
    console.print()
    try:
        return Prompt.ask(
            "  Action",
            choices=["write", "history", "stats"],
            default="write",
        )
    except (EOFError, KeyboardInterrupt):
        return "write"


def _write_entry(
    nb: NotebookDB,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
) -> None:
    # Pick a daily prompt (deterministic by day-of-year so it's consistent)
    day_idx = date.today().timetuple().tm_yday % len(_DAILY_PROMPTS)
    daily_prompt = _DAILY_PROMPTS[day_idx]

    console.print(Panel(
        f"[bold cyan]Today's prompt:[/bold cyan]\n\n"
        f"[italic]{daily_prompt}[/italic]\n\n"
        f"[dim]Write at least 50 words. Type your entry below, then press Enter twice to finish.[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))

    # Collect multi-line input
    lines = []
    try:
        console.print()
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    body = "\n".join(lines).strip()
    if not body:
        console.print("[yellow]No text entered. Entry not saved.[/yellow]\n")
        return

    word_count = len(body.split())
    console.print(f"\n  [dim]{word_count} words[/dim]")

    if word_count < 20:
        console.print("[yellow]Entry is very short. Try to write more next time![/yellow]")

    # AI feedback
    ai_feedback = ""
    if ai:
        with console.status("[bold blue]Getting AI feedback...[/bold blue]"):
            ai_feedback = _get_ai_feedback(ai, body, profile)

        if ai_feedback:
            console.print()
            console.print(Panel(
                ai_feedback,
                title="[bold]AI Feedback[/bold]",
                border_style="green",
                padding=(1, 3),
            ))

    # Save
    nb.save_entry(
        user_id=profile.user_id,
        body=body,
        prompt=daily_prompt,
        ai_feedback=ai_feedback,
    )

    streak = nb.streak(profile.user_id)
    console.print(
        f"\n[green]✓ Entry saved![/green]  "
        f"[yellow]{streak}d streak[/yellow]  ·  "
        f"[cyan]{word_count} words[/cyan]\n"
    )


def _show_history(nb: NotebookDB, profile: UserProfile) -> None:
    entries = nb.get_entries(profile.user_id, limit=10)
    if not entries:
        console.print("[yellow]No entries yet. Start writing![/yellow]\n")
        return

    console.print()
    for entry in entries:
        has_feedback = bool(entry["ai_feedback"])
        console.print(Rule(
            f"[dim]{entry['entry_date']}[/dim]  "
            f"[cyan]{entry['word_count']} words[/cyan]"
            + ("  [green]✓ feedback[/green]" if has_feedback else ""),
            style="dim",
        ))
        if entry["prompt"]:
            console.print(f"  [dim italic]{entry['prompt']}[/dim italic]")
        console.print()
        # Show first 300 chars
        body = entry["body"]
        preview = body[:300] + ("…" if len(body) > 300 else "")
        console.print(f"  {preview}")
        console.print()

        if has_feedback:
            try:
                if Confirm.ask("  Show AI feedback for this entry?", default=False):
                    console.print(Panel(
                        entry["ai_feedback"],
                        title="[bold]AI Feedback[/bold]",
                        border_style="green",
                        padding=(1, 3),
                    ))
            except (EOFError, KeyboardInterrupt):
                break


def _show_stats(nb: NotebookDB, profile: UserProfile) -> None:
    entries = nb.get_entries(profile.user_id, limit=100)
    if not entries:
        console.print("[yellow]No entries yet.[/yellow]\n")
        return

    total_entries = len(entries)
    total_words = nb.total_words(profile.user_id)
    streak = nb.streak(profile.user_id)
    avg_words = total_words // max(total_entries, 1)
    with_feedback = sum(1 for e in entries if e["ai_feedback"])

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")

    table.add_row("Total entries", str(total_entries))
    table.add_row("Total words written", f"[cyan]{total_words}[/cyan]")
    table.add_row("Average words/entry", str(avg_words))
    table.add_row("Current streak", f"[yellow]{streak}d[/yellow]")
    table.add_row("Entries with AI feedback", str(with_feedback))

    console.print()
    console.print(Panel(table, title="[bold cyan]Notebook Statistics[/bold cyan]", border_style="cyan"))
    console.print()


# ------------------------------------------------------------------
# AI feedback
# ------------------------------------------------------------------

_FEEDBACK_PROMPT = """\
You are an English writing coach. The student is at CEFR {level}, targeting {exam}.

Read their journal entry and give brief, encouraging feedback (3–5 bullet points):
1. One grammar correction (if any)
2. One vocabulary suggestion (a more precise or academic word)
3. One structural comment (sentence variety, coherence)
4. One thing they did well

Keep each point to one sentence. Be warm and specific. Do NOT rewrite the whole entry.

Entry:
{body}"""


def _get_ai_feedback(ai: AIClient, body: str, profile: UserProfile) -> str:
    prompt = _FEEDBACK_PROMPT.format(
        level=profile.cefr_level,
        exam=profile.target_exam.upper(),
        body=body[:1500],
    )
    try:
        return ai.complete(prompt, cache_key=None, max_tokens=400)
    except Exception:
        return ""
