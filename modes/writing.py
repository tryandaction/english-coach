"""
Writing feedback mode — AI-powered essay scoring and improvement suggestions.
Highest-value AI task: users get structured rubric-based feedback.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from ai.client import AIClient
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header, print_score_table, print_improvement_item, confirm

console = Console()

# Writing prompts by exam type (local, no API cost)
_WRITING_PROMPTS = {
    "toefl": [
        ("Integrated", "The professor disagrees with the reading passage's claim that remote work increases productivity. Summarize the points made in the lecture and explain how they cast doubt on the reading."),
        ("Independent", "Do you agree or disagree: Universities should require all students to take courses outside their major field of study. Use specific reasons and examples to support your answer."),
        ("Independent", "Some people believe that the best way to learn about a new culture is to read books about it. Others think that living in the culture is the best way to learn. Which do you prefer and why?"),
    ],
    "ielts": [
        ("Task 2", "Some people think that the government should provide free university education for all citizens. Others believe that students should pay for their own university education. Discuss both views and give your own opinion."),
        ("Task 2", "In many countries, the gap between the rich and the poor is increasing. What are the causes of this problem, and what measures could be taken to reduce it?"),
        ("Task 1", "The graph below shows the percentage of households with internet access in four countries between 2000 and 2020. Summarize the information by selecting and reporting the main features."),
    ],
    "gre": [
        ("Issue", "Governments should place few, if any, restrictions on scientific research and development. Write a response in which you discuss the extent to which you agree or disagree with this recommendation."),
        ("Argument", "The following appeared in a memo from the director of a company: 'Our competitor recently introduced a new product that has been very successful. We should immediately develop a similar product to compete.' Examine the reasoning in this argument."),
    ],
    "general": [
        ("Essay", "Describe a challenge you have faced in learning English and how you overcame it."),
        ("Essay", "What is the most important skill for a scientist or engineer to have? Use specific examples to support your view."),
        ("Email", "Write a formal email to your professor requesting an extension on your assignment deadline. Explain your reasons clearly and professionally."),
    ],
}


def run_writing_session(
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: Optional[str] = None,
) -> dict:
    """
    Run a writing feedback session:
    1. Present a writing prompt
    2. User writes/pastes their essay
    3. AI scores and gives structured feedback
    """
    if not ai:
        console.print(
            Panel(
                "[yellow]No API key configured.[/yellow]\n"
                "Writing feedback requires Claude API access.\n"
                "Add your key to [bold]config.yaml[/bold] → api_key",
                title="AI Required",
                border_style="yellow",
            )
        )
        return {}

    exam = exam or profile.target_exam or "general"
    session_id = user_model.start_session(profile.user_id, "writing")
    start_time = time.time()

    print_header(
        "写作练习  ·  Writing Practice",
        subtitle=f"Exam: {exam.upper()} · CEFR {profile.cefr_level}",
    )

    # Select prompt
    prompts = _WRITING_PROMPTS.get(exam, _WRITING_PROMPTS["general"])
    task_type, prompt_text = _select_prompt(prompts)

    # Display prompt
    console.print(Panel(
        f"[bold]{task_type}[/bold]\n\n{prompt_text}",
        title="Writing Prompt",
        border_style="blue",
        padding=(1, 2),
    ))

    # Collect essay
    essay = _collect_essay()
    if not essay:
        console.print("[dim]Session cancelled.[/dim]")
        return {}

    word_count = len(essay.split())
    console.print(f"\n[dim]Word count: {word_count}[/dim]")

    # AI feedback
    console.print("\n[dim]Analyzing your writing...[/dim]")
    with console.status("[bold blue]Getting AI feedback...[/bold blue]"):
        feedback = ai.evaluate_writing(
            essay=essay,
            task_type=task_type,
            cefr_level=profile.cefr_level,
            exam=exam,
        )

    if "error" in feedback:
        console.print(f"[red]Error getting feedback: {feedback.get('error')}[/red]")
        return {}

    # Display results
    _display_feedback(feedback, task_type, exam)

    # Update skill scores
    scores = feedback.get("scores", {})
    if scores:
        avg = sum(scores.values()) / len(scores)
        normalized = avg / 5.0  # normalize to 0-1
        user_model.record_answer(profile.user_id, "writing_grammar", normalized > 0.6)
        user_model.record_answer(profile.user_id, "writing_coherence", normalized > 0.6)
        user_model.record_answer(profile.user_id, "writing_vocabulary", normalized > 0.6)

    duration = int(time.time() - start_time)
    user_model.end_session(session_id, duration, 1, feedback.get("overall", 0) / 5.0)
    user_model.update_profile(profile)

    console.print(f"\n[dim]{ai.usage_summary()}[/dim]\n")
    return feedback


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _select_prompt(prompts: list[tuple]) -> tuple[str, str]:
    """Let user pick a prompt or get a random one."""
    console.print("\n[bold]Choose a prompt:[/bold]")
    for i, (task_type, text) in enumerate(prompts, 1):
        preview = text[:80] + "..." if len(text) > 80 else text
        console.print(f"  [cyan]{i}[/cyan]. [{task_type}] {preview}")
    console.print(f"  [cyan]{len(prompts)+1}[/cyan]. Random")

    from rich.prompt import Prompt
    choices = [str(i) for i in range(1, len(prompts) + 2)]
    choice = int(Prompt.ask("\nSelect", choices=choices, default=str(len(prompts) + 1)))

    if choice > len(prompts):
        import random
        return random.choice(prompts)
    return prompts[choice - 1]


def _collect_essay() -> str:
    """
    Collect multi-line essay input from user.
    User types/pastes, then enters a line with just '---' to finish.
    """
    console.print(
        "\n[bold]Write your response below.[/bold]\n"
        "[dim]Paste or type your essay. When done, enter a line with just: ---[/dim]\n"
    )
    lines = []
    try:
        while True:
            line = input()
            if line.strip() == "---":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    return "\n".join(lines).strip()


def _display_feedback(feedback: dict, task_type: str, exam: str) -> None:
    """Render AI feedback in a structured, readable format."""
    console.print()

    # Score table
    scores = feedback.get("scores", {})
    overall = feedback.get("overall", 0)
    if scores:
        print_score_table(scores, overall, exam)

    # Strengths
    strengths = feedback.get("strengths", [])
    if strengths:
        console.print("\n[bold green]✓ Strengths[/bold green]")
        for s in strengths:
            console.print(f"  • {s}")

    # Improvements
    improvements = feedback.get("improvements", [])
    if improvements:
        console.print("\n[bold yellow]→ Areas to Improve[/bold yellow]")
        for item in improvements:
            print_improvement_item(item)

    # Revised intro
    revised = feedback.get("revised_intro", "")
    if revised:
        console.print(Panel(
            revised,
            title="[bold]Suggested Revision (intro)[/bold]",
            border_style="green",
            padding=(1, 2),
        ))
