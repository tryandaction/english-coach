"""
Main CLI entry point — Typer-based command interface.
Commands: ingest, setup, vocab, read, write, speak, grammar, chat, progress, status, users
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force UTF-8 on Windows (default is GBK which can't encode ✓/✗ etc.)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

app = typer.Typer(
    name="english-coach",
    help="AI English tutor for STEM students — TOEFL / GRE / IELTS / CET",
    add_completion=False,
)
console = Console()

# Default paths
_DEFAULT_CONFIG = Path("config.yaml")
_DEFAULT_DATA = Path("data")


# ------------------------------------------------------------------
# Config + dependency loading
# ------------------------------------------------------------------

def _load_config(config_path: Path = _DEFAULT_CONFIG) -> dict:
    if not config_path.exists():
        console.print(f"[red]Config not found: {config_path}[/red]")
        console.print("Run [bold]english-coach setup[/bold] first.")
        raise typer.Exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_components(config: dict):
    """Lazy-load all components. Returns (kb, srs, user_model, ai, profile)."""
    from core.knowledge_base.store import KnowledgeBase
    from core.srs.engine import SM2Engine
    from core.user_model.profile import UserModel
    from ai.client import load_client

    data_dir = Path(config.get("data_dir", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "user.db"
    kb = KnowledgeBase(data_dir / "kb")
    srs = SM2Engine(db_path)
    user_model = UserModel(db_path)
    ai = load_client(config, data_dir)

    # Support active_user_id in config for multi-user switching
    active_uid = config.get("active_user_id")
    if active_uid:
        profile = user_model.get_profile(active_uid)
    else:
        profile = user_model.get_first_profile()

    if not profile:
        console.print("[yellow]No user profile found.[/yellow] Run [bold]english-coach setup[/bold] first.")
        raise typer.Exit(1)

    return kb, srs, user_model, ai, profile


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

@app.command()
def setup(
    config: Path = typer.Option(_DEFAULT_CONFIG, help="Path to config.yaml"),
):
    """First-time setup: create user profile and configure API key."""
    console.print(Panel(
        "[bold cyan]English Coach — Setup[/bold cyan]\n"
        "[dim]Let's get you started in 2 minutes.[/dim]",
        border_style="cyan",
    ))

    cfg = {}
    if config.exists():
        with open(config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    # User name
    name = Prompt.ask("\nYour name (用你的名字)")
    cfg["user"] = cfg.get("user", {})
    cfg["user"]["name"] = name

    # Backend + API key
    _ENV_KEYS = {
        "deepseek":  "DEEPSEEK_API_KEY",
        "qwen":      "DASHSCOPE_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai":    "OPENAI_API_KEY",
    }
    existing_backend = cfg.get("backend", "")
    existing_key = cfg.get("api_key", "")
    # Also check env vars
    if not existing_key and existing_backend:
        existing_key = os.environ.get(_ENV_KEYS.get(existing_backend, ""), "")

    if existing_key:
        console.print(f"[dim]API key already set for backend '{existing_backend}' ({existing_key[:8]}...)[/dim]")
    else:
        console.print(
            "\n[bold]AI Backend[/bold] (optional — needed for writing/reading AI features)\n"
            "[dim]deepseek: api.deepseek.com  |  qwen: dashscope.aliyuncs.com  |  Leave blank to skip[/dim]"
        )
        backend = Prompt.ask(
            "Backend",
            choices=["deepseek", "qwen", "anthropic", "openai", ""],
            default="deepseek",
        )
        if backend:
            cfg["backend"] = backend
            api_key = Prompt.ask(f"{backend} API key", default="", password=True)
            if api_key:
                # Save to .env file (never to config.yaml)
                env_file = Path(".env")
                env_var = _ENV_KEYS[backend]
                lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
                lines = [l for l in lines if not l.startswith(env_var + "=")]
                lines.append(f"{env_var}={api_key}")
                env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
                console.print(f"[green]✓ API key saved to .env[/green]")

    # Target exam
    exam = Prompt.ask(
        "\nTarget exam (目标考试)",
        choices=["toefl", "gre", "ielts", "cet", "general"],
        default="toefl",
    )
    cfg["user"]["target_exam"] = exam

    # Content paths
    console.print(
        "\n[bold]Content folder[/bold] (optional)\n"
        "[dim]Path to your study materials folder (MD files). Leave blank to use built-in content.[/dim]"
    )
    content_path = Prompt.ask("Content path", default="")
    if content_path:
        cfg.setdefault("content_paths", ["./content"])
        if content_path not in cfg["content_paths"]:
            cfg["content_paths"].append(content_path)

    # Save config
    with open(config, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    # Create user profile
    data_dir = Path(cfg.get("data_dir", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    from core.user_model.profile import UserModel
    user_model = UserModel(data_dir / "user.db")
    existing = user_model.get_first_profile()
    if not existing:
        profile = user_model.create_profile(
            name=name,
            target_exam=exam,
        )
        console.print(f"\n[green]✓ Profile created for {name}[/green]")
    else:
        console.print(f"\n[dim]Profile already exists for {existing.name}[/dim]")

    console.print(
        "\n[bold green]Setup complete![/bold green]\n"
        "Next steps:\n"
        "  1. [cyan]english-coach ingest ./your-content-folder[/cyan]  — load your study materials\n"
        "  2. [cyan]english-coach vocab[/cyan]  — start vocabulary practice\n"
        "  3. [cyan]english-coach write[/cyan]  — get writing feedback\n"
    )


@app.command()
def ingest(
    source: Path = typer.Argument(..., help="Folder containing MD/TXT files to ingest"),
    config: Path = typer.Option(_DEFAULT_CONFIG),
):
    """Load study materials from a folder into the knowledge base."""
    cfg = _load_config(config)
    data_dir = Path(cfg.get("data_dir", "data"))

    if not source.exists():
        console.print(f"[red]Path not found: {source}[/red]")
        raise typer.Exit(1)

    from core.ingestion.pipeline import IngestionPipeline
    from core.knowledge_base.store import KnowledgeBase

    console.print(f"\n[bold]Ingesting:[/bold] {source}")
    kb = KnowledgeBase(data_dir / "kb")
    pipeline = IngestionPipeline()

    with console.status("[bold blue]Parsing files...[/bold blue]"):
        chunks = pipeline.ingest_directory(source)

    if not chunks:
        console.print("[yellow]No supported files found (MD, TXT).[/yellow]")
        raise typer.Exit(0)

    console.print(f"  Found [cyan]{len(chunks)}[/cyan] chunks from {source}")

    with console.status("[bold blue]Embedding and storing...[/bold blue]"):
        added = kb.add_chunks(chunks)

    console.print(
        f"  [green]✓ Added {added} new chunks[/green]  "
        f"(skipped {len(chunks)-added} duplicates)\n"
        f"  Total in knowledge base: [cyan]{kb.count()}[/cyan]\n"
    )


@app.command()
def vocab(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    cards: int = typer.Option(30, help="Max cards per session"),
):
    """Vocabulary practice with spaced repetition (SRS)."""
    cfg = _load_config(config)
    kb, srs, user_model, ai, profile = _get_components(cfg)

    from modes.vocab import run_vocab_session
    run_vocab_session(srs, user_model, profile, max_cards=cards)


@app.command()
def read(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    exam: Optional[str] = typer.Option(None, help="toefl/gre/ielts/cet/general"),
):
    """Reading comprehension practice with AI-generated questions."""
    cfg = _load_config(config)
    kb, srs, user_model, ai, profile = _get_components(cfg)

    from modes.reading import run_reading_session
    run_reading_session(kb, user_model, profile, ai, exam=exam, srs=srs)


@app.command()
def write(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    exam: Optional[str] = typer.Option(None, help="toefl/gre/ielts/general"),
):
    """Writing practice with AI scoring and feedback."""
    cfg = _load_config(config)
    kb, srs, user_model, ai, profile = _get_components(cfg)

    from modes.writing import run_writing_session
    run_writing_session(user_model, profile, ai, exam=exam)


@app.command()
def words(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    action: Optional[str] = typer.Option(None, help="list/add/search/view/enrich/stats"),
    query: Optional[str] = typer.Option(None, help="Search query (for search action)"),
):
    """Manage your vocabulary deck — list, add, search, view, enrich, stats."""
    cfg = _load_config(config)
    _, srs, user_model, ai, profile = _get_components(cfg)

    from modes.words import run_words_manager
    run_words_manager(srs, user_model, profile, ai=ai, action=action, query=query)


@app.command()
def plan(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    minutes: int = typer.Option(30, help="Study session time budget in minutes"),
    exam: Optional[str] = typer.Option(None, help="toefl/gre/ielts/cet/general"),
):
    """Auto-generate and run a personalized daily study plan."""
    cfg = _load_config(config)
    kb, srs, user_model, ai, profile = _get_components(cfg)

    if exam:
        profile.target_exam = exam

    from modes.plan import run_daily_plan
    run_daily_plan(kb, srs, user_model, profile, ai, minutes=minutes)


@app.command()
def speak(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    exam: Optional[str] = typer.Option(None, help="toefl/gre/ielts/general"),
    task: Optional[str] = typer.Option(None, help="task1/task2/task3/task4"),
):
    """Speaking practice — type your response, get AI scoring."""
    cfg = _load_config(config)
    kb, srs, user_model, ai, profile = _get_components(cfg)

    from modes.speaking import run_speaking_session
    run_speaking_session(kb, user_model, profile, ai, exam=exam, task=task)


@app.command()
def grammar(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    focus: Optional[str] = typer.Option(None, help="articles/prepositions/tense/subject_verb/passive"),
    questions: int = typer.Option(10, help="Number of drill questions"),
):
    """Grammar drills — fill-in-the-blank exercises targeting weak areas."""
    cfg = _load_config(config)
    _, _, user_model, ai, profile = _get_components(cfg)

    from modes.grammar import run_grammar_session
    run_grammar_session(user_model, profile, ai, focus=focus, num_questions=questions)


@app.command()
def chat(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    exam: Optional[str] = typer.Option(None, help="toefl/gre/ielts/general"),
    topic: Optional[str] = typer.Option(None, help="Opening topic (optional)"),
):
    """Free conversation practice with your AI English coach."""
    cfg = _load_config(config)
    _, _, user_model, ai, profile = _get_components(cfg)

    from modes.chat import run_chat_session
    run_chat_session(user_model, profile, ai, exam=exam, topic=topic)


@app.command()
def progress(
    config: Path = typer.Option(_DEFAULT_CONFIG),
):
    """Show your learning progress dashboard."""
    cfg = _load_config(config)
    _, srs, user_model, _, profile = _get_components(cfg)

    from cli.display import print_progress_dashboard
    summary = user_model.progress_summary(profile.user_id)

    # Add SRS deck stats
    deck = srs.deck_stats(profile.user_id)
    summary["srs_total"] = deck["total"]
    summary["srs_due"] = deck["due_today"]
    summary["srs_mature"] = deck["mature"]

    print_progress_dashboard(summary)

    console.print(
        f"  SRS deck: [cyan]{deck['total']}[/cyan] words  ·  "
        f"Due today: [yellow]{deck['due_today']}[/yellow]  ·  "
        f"Mature: [green]{deck['mature']}[/green]\n"
    )


@app.command()
def status(
    config: Path = typer.Option(_DEFAULT_CONFIG),
):
    """Quick status check — due cards, knowledge base size, API key."""
    cfg = _load_config(config)
    data_dir = Path(cfg.get("data_dir", "data"))

    from core.knowledge_base.store import KnowledgeBase
    from core.srs.engine import SM2Engine
    from core.user_model.profile import UserModel

    kb = KnowledgeBase(data_dir / "kb")
    db_path = data_dir / "user.db"
    srs = SM2Engine(db_path)
    user_model = UserModel(db_path)
    profile = user_model.get_first_profile()

    api_key = cfg.get("api_key", "")
    backend = cfg.get("backend", "")
    # Load .env if present
    env_file = data_dir / ".." / ".env"
    if not api_key and Path(env_file).exists():
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    if not api_key:
        _env_map = {"deepseek": "DEEPSEEK_API_KEY", "qwen": "DASHSCOPE_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
        api_key = os.environ.get(_env_map.get(backend, "DEEPSEEK_API_KEY"), "")
    api_status = (
        f"[green]configured ({backend} · {api_key[:8]}...)[/green]"
        if api_key else "[yellow]not set -- run setup[/yellow]"
    )

    console.print()
    console.print(Panel(
        f"[bold]User:[/bold] {profile.name if profile else 'Not set up'}  ·  "
        f"CEFR [cyan]{profile.cefr_level if profile else '?'}[/cyan]\n"
        f"[bold]Knowledge base:[/bold] [cyan]{kb.count()}[/cyan] chunks\n"
        f"[bold]API key:[/bold] {api_status}\n"
        + (
            f"[bold]SRS deck:[/bold] {srs.deck_stats(profile.user_id)['total']} words  ·  "
            f"Due today: [yellow]{srs.deck_stats(profile.user_id)['due_today']}[/yellow]"
            if profile else ""
        ),
        title="[bold cyan]English Coach Status[/bold cyan]",
        border_style="cyan",
    ))
    console.print()


@app.command()
def export(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    output: Path = typer.Option(Path("export.json"), help="Output file path (.json, .csv, or .apkg)"),
):
    """Export your study history and vocabulary deck to JSON, CSV, or Anki .apkg."""
    cfg = _load_config(config)
    data_dir = Path(cfg.get("data_dir", "data"))

    from core.srs.engine import SM2Engine
    from core.user_model.profile import UserModel
    import json, csv

    db_path = data_dir / "user.db"
    srs = SM2Engine(db_path)
    user_model = UserModel(db_path)
    profile = user_model.get_first_profile()
    if not profile:
        console.print("[yellow]No profile found. Run setup first.[/yellow]")
        raise typer.Exit(1)

    suffix = output.suffix.lower()

    # Anki export
    if suffix == ".apkg":
        from modes.anki_export import export_anki
        export_anki(srs, profile, output)
        return

    # Gather data for JSON/CSV
    summary = user_model.progress_summary(profile.user_id)
    deck_rows = srs._db.execute(
        """SELECT v.word, v.definition_en, v.definition_zh, v.example,
                  v.topic, v.difficulty, c.interval, c.repetitions,
                  c.easiness, c.due_date, c.total_reviews, c.correct_reviews
           FROM srs_cards c JOIN vocabulary v ON c.word_id = v.word_id
           WHERE c.user_id = ? ORDER BY v.word""",
        (profile.user_id,),
    ).fetchall()

    session_rows = srs._db.execute(
        "SELECT mode, duration_sec, items_done, accuracy, started_at FROM sessions "
        "WHERE user_id=? ORDER BY started_at",
        (profile.user_id,),
    ).fetchall()

    if suffix == ".csv":
        with open(output, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["word", "definition_en", "definition_zh", "example",
                        "topic", "difficulty", "interval", "repetitions",
                        "easiness", "due_date", "total_reviews", "correct_reviews"])
            for r in deck_rows:
                w.writerow(list(r))
        console.print(f"[green]✓ Exported {len(deck_rows)} words to {output}[/green]")
    else:
        data = {
            "profile": {
                "name": profile.name,
                "cefr_level": profile.cefr_level,
                "target_exam": profile.target_exam,
                "streak_days": summary.get("streak_days", 0),
            },
            "skill_scores": summary["skill_scores"],
            "vocabulary": [dict(r) for r in deck_rows],
            "sessions": [dict(r) for r in session_rows],
        }
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(
            f"[green]✓ Exported to {output}[/green]  "
            f"({len(deck_rows)} words, {len(session_rows)} sessions)"
        )


@app.command()
def reset(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    keep_kb: bool = typer.Option(True, help="Keep knowledge base (default: yes)"),
):
    """Reset user data — clears profile, SRS deck, and session history."""
    from rich.prompt import Confirm
    cfg = _load_config(config)
    data_dir = Path(cfg.get("data_dir", "data"))

    console.print(Panel(
        "[bold yellow]This will delete:[/bold yellow]\n"
        "  • Your user profile and CEFR level\n"
        "  • Your entire SRS vocabulary deck\n"
        "  • All session history and skill scores\n"
        + ("  • Knowledge base chunks\n" if not keep_kb else
           "  [dim](Knowledge base will be kept)[/dim]"),
        title="[bold red]Reset Warning[/bold red]",
        border_style="red",
    ))

    if not Confirm.ask("\n  Are you sure?", default=False):
        console.print("[dim]Cancelled.[/dim]")
        return

    import sqlite3
    db_path = data_dir / "user.db"
    if db_path.exists():
        db = sqlite3.connect(str(db_path))
        db.execute("DELETE FROM users")
        db.execute("DELETE FROM srs_cards")
        db.execute("DELETE FROM vocabulary")
        db.execute("DELETE FROM skill_scores")
        db.execute("DELETE FROM seen_content")
        db.execute("DELETE FROM sessions")
        db.execute("DELETE FROM srs_reviews")
        db.commit()
        db.close()

    if not keep_kb:
        kb_path = data_dir / "kb" / "teaching.db"
        if kb_path.exists():
            kb_path.unlink()
        console.print("[green]✓ Knowledge base cleared.[/green]")

    # Clear AI cache too
    cache_path = data_dir / "ai_cache.db"
    if cache_path.exists():
        cache_path.unlink()

    console.print("[green]✓ User data reset complete.[/green]")
    console.print("Run [bold]english-coach setup[/bold] to start fresh.\n")


@app.command()
def users(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    action: Optional[str] = typer.Option(None, help="list/switch/new/delete/rename"),
):
    """Manage user profiles — list, switch, create, delete, rename."""
    cfg = _load_config(config)
    _, srs, user_model, _, profile = _get_components(cfg)

    from modes.users import run_users_manager
    new_uid = run_users_manager(user_model, srs, profile, action=action)

    if new_uid:
        # Persist the active user selection into config.yaml
        cfg["active_user_id"] = new_uid
        with open(config, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
        console.print(
            f"[dim]Active user saved to {config}. "
            "All subsequent commands will use this profile.[/dim]\n"
        )


@app.command()
def packs(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    action: Optional[str] = typer.Option(None, help="list/scan/add/remove/registry"),
):
    """Manage content packs — list, scan, add, remove."""
    cfg = _load_config(config)

    from modes.packs import run_packs_manager
    run_packs_manager(cfg, config, action=action)


@app.command()
def notebook(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    action: Optional[str] = typer.Option(None, help="write/history/stats"),
):
    """Daily writing journal with AI feedback — build a writing streak."""
    cfg = _load_config(config)
    data_dir = Path(cfg.get("data_dir", "data"))
    _, _, user_model, ai, profile = _get_components(cfg)

    from modes.notebook import run_notebook_session
    run_notebook_session(user_model, profile, ai, data_dir, action=action)


@app.command()
def mock(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    exam: Optional[str] = typer.Option(None, help="toefl/gre/ielts/cet"),
    section: Optional[str] = typer.Option(None, help="Run a single section by name"),
):
    """Timed mock exam — full TOEFL/GRE/IELTS practice with scored report."""
    cfg = _load_config(config)
    data_dir = Path(cfg.get("data_dir", "data"))
    kb, _, user_model, ai, profile = _get_components(cfg)

    from modes.mock_exam import run_mock_exam
    run_mock_exam(kb, user_model, profile, ai, data_dir, exam=exam, section=section)


@app.command()
def lookup(
    config: Path = typer.Option(_DEFAULT_CONFIG),
    word: Optional[str] = typer.Argument(None, help="Word to look up"),
):
    """Offline word lookup — search KB and SRS deck, optionally add to deck."""
    cfg = _load_config(config)
    kb, srs, user_model, ai, profile = _get_components(cfg)

    from modes.lookup import run_lookup
    run_lookup(word, kb, srs, user_model, profile, ai)


if __name__ == "__main__":
    app()
