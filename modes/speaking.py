"""
Speaking practice mode — TOEFL/GRE text-based speaking simulation.
User types their response (simulating spoken output), AI scores it.
Zero cost when no API key; uses sample responses from KB as reference.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ai.client import AIClient
from core.knowledge_base.store import KnowledgeBase
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header

console = Console()

# TOEFL speaking task definitions
_TOEFL_TASKS = {
    "task1": {
        "name": "Independent Speaking",
        "prompt_label": "Express and defend a personal opinion",
        "prep_seconds": 15,
        "speak_seconds": 45,
        "instructions": (
            "You will be given a question asking for your opinion or preference. "
            "Prepare for 15 seconds, then speak for 45 seconds.\n"
            "Structure: [Position] → [Reason 1 + example] → [Reason 2 + example] → [Conclusion]"
        ),
    },
    "task2": {
        "name": "Campus Situation",
        "prompt_label": "Summarize a campus announcement and a student's reaction",
        "prep_seconds": 30,
        "speak_seconds": 60,
        "instructions": (
            "You will read a short campus announcement and hear a student's opinion. "
            "Summarize the announcement and explain the student's view.\n"
            "Structure: [Announcement summary] → [Student's position] → [Reasons given]"
        ),
    },
    "task3": {
        "name": "Academic Concept",
        "prompt_label": "Define a concept and illustrate with a lecture example",
        "prep_seconds": 30,
        "speak_seconds": 60,
        "instructions": (
            "You will read a short definition and hear a lecture example. "
            "Explain the concept using the lecture example.\n"
            "Structure: [Define concept] → [Lecture example] → [How example illustrates concept]"
        ),
    },
    "task4": {
        "name": "Lecture Summary",
        "prompt_label": "Summarize key points from an academic lecture",
        "prep_seconds": 20,
        "speak_seconds": 60,
        "instructions": (
            "You will hear an academic lecture. Summarize the main points.\n"
            "Structure: [Main topic] → [Point 1 + detail] → [Point 2 + detail] → [Connection]"
        ),
    },
}

# Standalone prompts for Task 1 (no reading/listening material needed)
_TASK1_PROMPTS = [
    "Do you prefer studying alone or in a group? Use specific reasons and examples.",
    "Some people prefer living in a big city; others prefer a small town. Which do you prefer and why?",
    "Is it better to have a few close friends or many acquaintances? Explain your view.",
    "Do you agree that technology has made people less creative? Give reasons and examples.",
    "Would you rather have a job that pays well but is boring, or a lower-paying job you love?",
    "Some students prefer taking notes by hand; others prefer typing. Which do you prefer?",
    "Do you think it is important to learn a foreign language? Why or why not?",
    "Is it better to plan carefully before starting a project, or to start and adjust as you go?",
    "Do you prefer reading physical books or digital books? Explain with reasons.",
    "Should universities require all students to take physical education courses? Why or why not?",
]


def run_speaking_session(
    kb: KnowledgeBase,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: Optional[str] = None,
    task: Optional[str] = None,
) -> dict:
    """
    Run a speaking practice session.
    - Picks a task type (default: task1 for no-material practice)
    - Displays prompt + instructions
    - User types their response
    - AI scores it (or shows rubric-only feedback if no API key)
    """
    exam = exam or profile.target_exam or "toefl"
    session_id = user_model.start_session(profile.user_id, "speaking")
    start_time = time.time()

    print_header(
        "口语练习  ·  Speaking Practice",
        subtitle=f"Exam: {exam.upper()} · CEFR {profile.cefr_level}",
    )

    # Pick task type
    task_key = _pick_task(task, exam)
    task_info = _TOEFL_TASKS.get(task_key, _TOEFL_TASKS["task1"])

    console.print(Panel(
        f"[bold]{task_info['name']}[/bold]\n\n"
        f"[dim]{task_info['instructions']}[/dim]",
        title=f"[cyan]{task_key.upper()}[/cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    # Get prompt + optional reference material from KB
    prompt_text, sample_response = _get_prompt_and_sample(kb, task_key, profile, exam)

    console.print(f"\n[bold yellow]PROMPT:[/bold yellow]\n  {prompt_text}\n")

    # Prep timer (simulated — just show the time)
    prep = task_info["prep_seconds"]
    speak = task_info["speak_seconds"]
    console.print(
        f"[dim]Preparation time: {prep}s  ·  Speaking time: {speak}s[/dim]\n"
        f"[dim](Type your response below — aim for ~{speak//5}-{speak//4} words)[/dim]\n"
    )

    input("  Press Enter when ready to start typing your response...")
    console.print()

    # Collect response
    lines = []
    console.print("[bold]Your response[/bold] (type your answer, press Enter twice when done):\n")
    blank_count = 0
    while blank_count < 1:
        line = input()
        if line == "":
            blank_count += 1
        else:
            blank_count = 0
            lines.append(line)

    transcript = " ".join(lines).strip()

    if not transcript:
        console.print("[yellow]No response entered. Session cancelled.[/yellow]")
        user_model.end_session(session_id, 0, 0, 0.0)
        return {}

    # Guard: if no API key and no terminal (test runner), skip self-assessment prompt

    word_count = len(transcript.split())
    target_words = speak // 4  # ~1 word/4 seconds is a rough spoken pace
    console.print(f"\n[dim]Word count: {word_count}  (target: ~{target_words}+)[/dim]\n")

    # Score
    stats = {"score": 0, "max_score": 4}

    if ai:
        with console.status("[bold blue]Scoring your response...[/bold blue]"):
            feedback = ai.evaluate_speaking(
                transcript=transcript,
                task_type=f"{exam}_{task_key}",
                cefr_level=profile.cefr_level,
                sample_response=sample_response,
            )
        _display_speaking_feedback(feedback, transcript, sample_response)
        overall = feedback.get("overall", 0)
        stats["score"] = overall
    else:
        _display_no_api_feedback(transcript, task_info, sample_response)
        # Self-assessment — skip gracefully if stdin is not a tty (e.g. test runner)
        try:
            rating = Prompt.ask(
                "\n  Self-assessment — how did you do?",
                choices=["1", "2", "3", "4"],
                default="2",
            )
            stats["score"] = int(rating)
        except (EOFError, KeyboardInterrupt):
            stats["score"] = 2

    # Update skill scores
    score_ratio = stats["score"] / 4.0
    user_model.record_answer(profile.user_id, "speaking_structure", score_ratio >= 0.6)
    user_model.record_answer(profile.user_id, "speaking_vocabulary", score_ratio >= 0.6)

    duration = int(time.time() - start_time)
    user_model.end_session(session_id, duration, 1, score_ratio)
    user_model.update_profile(profile)

    console.print(
        f"\n[bold]Session complete![/bold]  "
        f"Score: [{'green' if score_ratio >= 0.6 else 'yellow'}]{stats['score']}/4[/]  "
        f"({int(score_ratio * 100)}%)\n"
    )

    if ai:
        console.print(f"[dim]{ai.usage_summary()}[/dim]\n")

    return stats


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _pick_task(task: Optional[str], exam: str) -> str:
    """Pick task type based on user preference or exam."""
    if task and task in _TOEFL_TASKS:
        return task
    # Default to task1 (independent — no reading material needed)
    return "task1"


def _get_prompt_and_sample(
    kb: KnowledgeBase,
    task_key: str,
    profile: UserProfile,
    exam: str,
) -> tuple[str, Optional[str]]:
    """
    Get a speaking prompt and optional sample response from KB.
    Falls back to built-in Task 1 prompts if KB has nothing.
    """
    sample_response = None

    # Try to find a speaking chunk with a prompt
    rows = kb.search(
        f"{task_key} speaking prompt",
        content_type="speaking",
        exam=exam if exam != "general" else None,
        limit=5,
    )

    # Also try get_by_type for variety
    if not rows:
        rows = kb.get_by_type(
            content_type="speaking",
            difficulty=profile.cefr_level,
            exam=exam if exam != "general" else None,
            limit=5,
            random_order=True,
        )

    # Extract a sample response if available
    if rows:
        for row in rows:
            text = row["text"]
            if len(text) > 100:
                sample_response = text[:800]
                break

    # For task1, use built-in prompts (more reliable than KB extraction)
    if task_key == "task1":
        import random
        prompt_text = random.choice(_TASK1_PROMPTS)
    else:
        # Try to extract a prompt from KB content
        prompt_text = _extract_prompt_from_kb(rows, task_key)

    return prompt_text, sample_response


def _extract_prompt_from_kb(rows: list, task_key: str) -> str:
    """Extract a usable prompt from KB rows, or return a generic one."""
    for row in rows:
        text = row["text"]
        # Look for lines that look like questions
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 30 and ("?" in line or line.startswith("Describe") or line.startswith("Explain")):
                return line
    # Generic fallback
    fallbacks = {
        "task2": "A university is considering changing its library hours. Summarize the announcement and explain the student's reaction.",
        "task3": "The professor discusses the concept of cognitive dissonance. Explain the concept and the example given.",
        "task4": "The professor explains two types of animal mimicry. Summarize the key points from the lecture.",
    }
    return fallbacks.get(task_key, "Describe an important skill you have learned and explain why it is valuable.")


def _display_speaking_feedback(feedback: dict, transcript: str, sample: Optional[str]) -> None:
    """Render AI speaking feedback with Rich."""
    if "error" in feedback:
        console.print(f"[yellow]Feedback error: {feedback.get('raw', '')}[/yellow]")
        return

    scores = feedback.get("scores", {})
    overall = feedback.get("overall", 0)
    strengths = feedback.get("strengths", [])
    improvements = feedback.get("improvements", [])
    key_phrases = feedback.get("key_phrases_to_add", [])

    # Score table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Dimension", style="dim")
    table.add_column("Score", justify="right")
    table.add_column("Bar")

    dim_labels = {
        "delivery": "Delivery",
        "language_use": "Language Use",
        "topic_development": "Topic Development",
    }
    for key, label in dim_labels.items():
        val = scores.get(key, 0)
        bar = "█" * int(val * 3) + "░" * (12 - int(val * 3))
        color = "green" if val >= 3 else "yellow" if val >= 2 else "red"
        table.add_row(label, f"[{color}]{val}/4[/{color}]", f"[{color}]{bar}[/{color}]")

    overall_color = "green" if overall >= 3 else "yellow" if overall >= 2 else "red"
    console.print(Panel(
        table,
        title=f"[bold]Speaking Score: [{overall_color}]{overall}/4[/{overall_color}][/bold]",
        border_style=overall_color,
        padding=(1, 2),
    ))

    if strengths:
        console.print("\n[bold green]Strengths:[/bold green]")
        for s in strengths:
            console.print(f"  [green]✓[/green] {s}")

    if improvements:
        console.print("\n[bold yellow]Improvements:[/bold yellow]")
        for imp in improvements:
            console.print(f"  [yellow]→[/yellow] {imp}")

    if key_phrases:
        console.print("\n[bold cyan]Phrases to add to your toolkit:[/bold cyan]")
        for phrase in key_phrases:
            console.print(f"  [cyan]»[/cyan] {phrase}")

    if sample:
        console.print(Panel(
            sample,
            title="[dim]Reference Sample Response[/dim]",
            border_style="dim",
            padding=(1, 2),
        ))


def _display_no_api_feedback(transcript: str, task_info: dict, sample: Optional[str]) -> None:
    """Show self-assessment rubric when no API key is available."""
    word_count = len(transcript.split())
    target = task_info["speak_seconds"] // 4

    console.print(Panel(
        "[bold]Self-Assessment Checklist[/bold]\n\n"
        f"  Word count: [cyan]{word_count}[/cyan]  (target: {target}+)\n\n"
        "  Structure:\n"
        "  [ ] Clear opening statement / position\n"
        "  [ ] At least 2 supporting points\n"
        "  [ ] Specific examples for each point\n"
        "  [ ] Conclusion or wrap-up\n\n"
        "  Language:\n"
        "  [ ] Varied vocabulary (no word repeated >3 times)\n"
        "  [ ] Transition phrases (furthermore, however, for example)\n"
        "  [ ] No major grammar errors\n\n"
        "  Delivery (if spoken aloud):\n"
        "  [ ] Stayed within time limit\n"
        "  [ ] Clear pronunciation\n"
        "  [ ] Natural pace (not too fast/slow)",
        title="[cyan]No API Key — Self-Assessment[/cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    if sample:
        console.print(Panel(
            sample,
            title="[dim]Reference Sample Response[/dim]",
            border_style="dim",
            padding=(1, 2),
        ))
