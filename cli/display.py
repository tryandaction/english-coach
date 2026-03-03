"""
CLI display helpers — Rich-based formatting for all output.
Centralizes all visual rendering so modes stay clean.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
from rich.prompt import Confirm

console = Console()


def print_header(title: str, subtitle: str = "") -> None:
    console.print()
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))
    if subtitle:
        console.print(f"  [dim]{subtitle}[/dim]")
    console.print()


def print_word_card(
    word: str,
    definition_en: str = "",
    definition_zh: str = "",
    example: str = "",
    show_answer: bool = False,
    is_new: bool = False,
    synonyms: str = "",
    collocations: str = "",
    context_sentence: str = "",
    part_of_speech: str = "",
    pronunciation: str = "",
) -> None:
    border = "green" if is_new else "blue"
    tag = "[bold green]NEW[/bold green]  " if is_new else ""

    header = f"{tag}[bold white]{word}[/bold white]"
    if part_of_speech:
        header += f"  [dim italic]{part_of_speech}[/dim italic]"
    if pronunciation:
        header += f"  [cyan]{pronunciation}[/cyan]"

    if not show_answer:
        console.print(Panel(header, border_style=border, padding=(1, 4)))
        return

    body = header + "\n\n"
    if definition_en:
        body += f"[cyan]{definition_en}[/cyan]\n"
    if definition_zh:
        body += f"[dim]{definition_zh}[/dim]\n"
    if example:
        body += f"\n[italic]\"{example}\"[/italic]\n"
    if context_sentence:
        body += f"\n[dim]Context:[/dim] [italic]{context_sentence}[/italic]\n"
    if synonyms:
        body += f"\n[dim]Synonyms:[/dim] [green]{synonyms}[/green]"
    if collocations:
        body += f"\n[dim]Collocations:[/dim] [yellow]{collocations}[/yellow]"

    console.print(Panel(body.strip(), border_style=border, padding=(1, 4)))


def print_result_row(word: str, correct: bool, interval_label: str) -> None:
    icon = "[green]✓[/green]" if correct else "[red]✗[/red]"
    console.print(f"  {icon}  [bold]{word}[/bold]  [dim]{interval_label}[/dim]")


def print_session_summary(
    mode: str,
    reviewed: int,
    correct: int,
    new_words: int = 0,
    duration_sec: int = 0,
    deck_total: int = 0,
    deck_mature: int = 0,
) -> None:
    accuracy = correct / max(reviewed, 1)
    acc_color = "green" if accuracy >= 0.8 else "yellow" if accuracy >= 0.6 else "red"
    minutes = duration_sec // 60
    seconds = duration_sec % 60

    table = Table(box=box.ROUNDED, border_style="dim", show_header=False, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")

    table.add_row("Mode", mode)
    table.add_row("Reviewed", str(reviewed))
    table.add_row("Correct", f"[{acc_color}]{correct}[/{acc_color}]")
    table.add_row("Accuracy", f"[{acc_color}]{int(accuracy*100)}%[/{acc_color}]")
    if new_words:
        table.add_row("New words added", str(new_words))
    table.add_row("Duration", f"{minutes}m {seconds}s")
    if deck_total:
        table.add_row("Deck total", str(deck_total))
        table.add_row("Mature cards", str(deck_mature))

    console.print()
    console.print(Panel(table, title="[bold]Session Summary[/bold]", border_style="cyan"))
    console.print()


def print_score_table(scores: dict, overall: float, exam: str) -> None:
    table = Table(
        title=f"Writing Scores — {exam.upper()}",
        box=box.ROUNDED,
        border_style="cyan",
        show_header=True,
    )
    table.add_column("Dimension", style="bold")
    table.add_column("Score", justify="center")
    table.add_column("", justify="left")

    max_score = 9 if exam == "ielts" else 6 if exam == "gre" else 5

    for dim, score in scores.items():
        label = dim.replace("_", " ").title()
        bar = _score_bar(score, max_score)
        color = "green" if score >= max_score * 0.7 else "yellow" if score >= max_score * 0.5 else "red"
        table.add_row(label, f"[{color}]{score}/{max_score}[/{color}]", bar)

    console.print(table)

    overall_color = "green" if overall >= max_score * 0.7 else "yellow" if overall >= max_score * 0.5 else "red"
    console.print(
        f"\n  Overall: [{overall_color}][bold]{overall}/{max_score}[/bold][/{overall_color}]\n"
    )


def print_improvement_item(item: dict) -> None:
    issue = item.get("issue", "")
    original = item.get("original", "")
    correction = item.get("correction", "")
    explanation = item.get("explanation", "")

    console.print(f"\n  [yellow]▸[/yellow] [bold]{issue}[/bold]")
    if original:
        console.print(f"    [red]✗[/red] [dim]{original}[/dim]")
    if correction:
        console.print(f"    [green]✓[/green] {correction}")
    if explanation:
        console.print(f"    [dim]{explanation}[/dim]")


def print_progress_dashboard(summary: dict) -> None:
    console.print()
    console.print(Rule("[bold]Progress Dashboard · 学习进度[/bold]", style="cyan"))
    console.print()

    # Profile info
    streak = summary.get("streak_days", 0)
    console.print(
        f"  [bold]{summary['name']}[/bold]  ·  "
        f"CEFR [cyan]{summary['cefr_level']}[/cyan]  ·  "
        f"Target: [bold]{summary['target_exam'].upper()}[/bold]"
        + (f"  ·  [bold yellow]🔥 {streak}d streak[/bold yellow]" if streak else "")
    )
    console.print(
        f"  Sessions: {summary['total_sessions']}  ·  "
        f"Items practiced: {summary['total_items']}  ·  "
        f"Avg accuracy: {summary['avg_accuracy']}%"
    )
    console.print()

    # Skill scores
    scores = summary.get("skill_scores", {})
    if scores:
        table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
        table.add_column("Skill", style="bold")
        table.add_column("Score", justify="center")
        table.add_column("Level", justify="center")
        table.add_column("", justify="left")

        for skill, score in sorted(scores.items(), key=lambda x: x[1]):
            color = "green" if score >= 0.75 else "yellow" if score >= 0.55 else "red"
            level = "Strong" if score >= 0.75 else "OK" if score >= 0.55 else "Weak"
            bar = _score_bar(score, 1.0, width=12)
            table.add_row(
                skill.replace("_", " "),
                f"[{color}]{int(score*100)}%[/{color}]",
                f"[{color}]{level}[/{color}]",
                bar,
            )
        console.print(table)

    # Weak areas
    weak = summary.get("weak_areas", [])
    if weak:
        console.print(
            f"  [yellow]Focus areas:[/yellow] "
            + ", ".join(w.replace("_", " ") for w in weak)
        )
    console.print()


def confirm(prompt: str) -> bool:
    return Confirm.ask(prompt, default=True)


def _score_bar(score: float, max_val: float, width: int = 10) -> str:
    ratio = min(score / max(max_val, 0.001), 1.0)
    filled = int(ratio * width)
    color = "green" if ratio >= 0.7 else "yellow" if ratio >= 0.5 else "red"
    return f"[{color}]{'█' * filled}{'░' * (width - filled)}[/{color}]"
