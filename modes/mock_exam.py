"""
Mock exam mode — timed full-length practice tests for TOEFL/GRE/IELTS.
Zero backend. Uses KB passages for reading, built-in prompts for writing/speaking.
Generates a scored report saved locally as JSON.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box
from rich.prompt import Prompt, Confirm

from core.knowledge_base.store import KnowledgeBase
from core.user_model.profile import UserModel, UserProfile
from ai.client import AIClient
from cli.display import print_header

console = Console()

# Exam configurations: sections, time limits (minutes), item counts
_EXAM_CONFIGS = {
    "toefl": {
        "name": "TOEFL iBT",
        "sections": [
            {"name": "Reading",  "mode": "reading",  "minutes": 54, "items": 3},
            {"name": "Writing",  "mode": "writing",  "minutes": 50, "items": 2},
            {"name": "Speaking", "mode": "speaking", "minutes": 17, "items": 4},
        ],
    },
    "gre": {
        "name": "GRE General",
        "sections": [
            {"name": "Verbal Reasoning",     "mode": "reading",  "minutes": 30, "items": 2},
            {"name": "Analytical Writing",   "mode": "writing",  "minutes": 60, "items": 2},
        ],
    },
    "ielts": {
        "name": "IELTS Academic",
        "sections": [
            {"name": "Reading",  "mode": "reading",  "minutes": 60, "items": 3},
            {"name": "Writing",  "mode": "writing",  "minutes": 60, "items": 2},
            {"name": "Speaking", "mode": "speaking", "minutes": 15, "items": 3},
        ],
    },
    "cet": {
        "name": "CET-6",
        "sections": [
            {"name": "Reading Comprehension", "mode": "reading", "minutes": 40, "items": 2},
            {"name": "Writing",               "mode": "writing", "minutes": 30, "items": 1},
        ],
    },
}


# ------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------

def run_mock_exam(
    kb: KnowledgeBase,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    data_dir: Path,
    exam: Optional[str] = None,
    section: Optional[str] = None,
) -> None:
    exam = (exam or profile.target_exam or "toefl").lower()
    cfg = _EXAM_CONFIGS.get(exam, _EXAM_CONFIGS["toefl"])

    print_header(
        f"Mock Exam  /  {cfg['name']}",
        subtitle=f"CEFR {profile.cefr_level} · Full timed practice",
    )

    # Show exam overview
    _display_exam_overview(cfg)

    # Let user pick full exam or single section
    mode = _pick_mode(cfg, section)
    if mode is None:
        return

    sections_to_run = (
        cfg["sections"]
        if mode == "full"
        else [s for s in cfg["sections"] if s["name"].lower() == mode.lower()]
    )

    if not sections_to_run:
        console.print(f"[red]Section '{mode}' not found for {exam.upper()}.[/red]\n")
        return

    exam_id = uuid.uuid4().hex[:12]
    results = []
    total_start = time.time()

    for sec in sections_to_run:
        console.print(f"\n[bold cyan]Section: {sec['name']}[/bold cyan]  "
                      f"[dim]{sec['minutes']} min · {sec['items']} item(s)[/dim]\n")
        try:
            if not Confirm.ask("  Ready to start this section?", default=True):
                console.print("[dim]Section skipped.[/dim]")
                continue
        except (EOFError, KeyboardInterrupt):
            break

        sec_result = _run_section(sec, kb, user_model, profile, ai, exam)
        results.append(sec_result)

    total_elapsed = int(time.time() - total_start)

    # Generate and save report
    report = _build_report(exam_id, exam, cfg["name"], profile, results, total_elapsed)
    report_path = data_dir / f"mock_{exam}_{exam_id}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    _display_report(report, report_path)


# ------------------------------------------------------------------
# Section runners
# ------------------------------------------------------------------

def _run_section(
    sec: dict,
    kb: KnowledgeBase,
    user_model: UserModel,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: str,
) -> dict:
    mode = sec["mode"]
    minutes = sec["minutes"]
    items = sec["items"]
    deadline = time.time() + minutes * 60
    section_scores = []
    section_responses = []

    for i in range(items):
        remaining = int((deadline - time.time()) / 60)
        if remaining <= 0:
            console.print("[yellow]Time's up for this section.[/yellow]")
            break

        console.print(Rule(
            f"[dim]{sec['name']} — Item {i+1}/{items}  |  ~{remaining} min remaining[/dim]",
            style="dim",
        ))

        if mode == "reading":
            result = _reading_item(kb, profile, ai, exam)
        elif mode == "writing":
            result = _writing_item(profile, ai, exam, task_num=i+1)
        elif mode == "speaking":
            result = _speaking_item(kb, profile, ai, exam, task_num=i+1)
        else:
            result = {"score": 0, "response": ""}

        section_scores.append(result.get("score", 0))
        section_responses.append(result)

    avg_score = sum(section_scores) / max(len(section_scores), 1)
    return {
        "section": sec["name"],
        "mode": mode,
        "items_completed": len(section_scores),
        "avg_score": round(avg_score, 2),
        "responses": section_responses,
    }


def _reading_item(
    kb: KnowledgeBase,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: str,
) -> dict:
    chunks = kb.search(
        query="academic reading passage",
        limit=5,
        difficulty=profile.cefr_level,
        exam=exam,
    )
    if not chunks:
        console.print("[yellow]No reading passages found in knowledge base.[/yellow]")
        return {"score": 0}

    import random
    chunk = random.choice(chunks)
    passage = chunk.get("text", "")[:1200]

    console.print(Panel(passage, title="[bold]Reading Passage[/bold]", border_style="blue", padding=(1, 3)))

    if not ai:
        console.print("[dim]No API key — self-score this passage (1-5).[/dim]")
        try:
            score = int(Prompt.ask("  Self-score", choices=["1","2","3","4","5"], default="3"))
        except (EOFError, KeyboardInterrupt):
            score = 3
        return {"score": score, "passage": passage[:100]}

    with console.status("[bold blue]Generating questions...[/bold blue]"):
        questions = ai.generate_comprehension_questions(passage, profile.cefr_level, num_questions=2, exam=exam)

    correct = 0
    for q in questions:
        console.print(f"\n  [bold]{q.get('question', '')}[/bold]")
        try:
            answer = Prompt.ask("  Your answer")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        expected = q.get("answer", "")
        console.print(f"  [dim]Model answer: {expected}[/dim]")
        console.print(f"  [dim]{q.get('explanation', '')}[/dim]")
        # Simple scoring: user self-rates
        try:
            got_it = Confirm.ask("  Did you get it right?", default=True)
        except (EOFError, KeyboardInterrupt):
            got_it = True
        if got_it:
            correct += 1

    score = round((correct / max(len(questions), 1)) * 5, 1)
    return {"score": score, "correct": correct, "total_q": len(questions)}


def _writing_item(
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: str,
    task_num: int = 1,
) -> dict:
    prompts = _WRITING_PROMPTS.get(exam, _WRITING_PROMPTS["general"])
    prompt_text = prompts[(task_num - 1) % len(prompts)]

    console.print(Panel(
        f"[bold cyan]Writing Task {task_num}[/bold cyan]\n\n{prompt_text}\n\n"
        "[dim]Type your response. Press Enter twice when done.[/dim]",
        border_style="cyan", padding=(1, 3),
    ))

    lines = []
    try:
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    essay = "\n".join(lines).strip()
    word_count = len(essay.split())
    console.print(f"  [dim]{word_count} words[/dim]")

    if not essay:
        return {"score": 0, "word_count": 0}

    if not ai:
        try:
            score = float(Prompt.ask("  Self-score (0-5)", default="3"))
        except (EOFError, KeyboardInterrupt):
            score = 3.0
        return {"score": score, "word_count": word_count}

    with console.status("[bold blue]Scoring your writing...[/bold blue]"):
        feedback = ai.evaluate_writing(essay, f"task{task_num}", profile.cefr_level, exam)

    overall = feedback.get("overall", 0)
    scores = feedback.get("scores", {})
    console.print(f"\n  Overall score: [bold cyan]{overall}[/bold cyan]")
    for dim, s in scores.items():
        console.print(f"  {dim.replace('_',' ').title()}: [cyan]{s}[/cyan]")

    return {"score": overall, "word_count": word_count, "feedback": feedback}


def _speaking_item(
    kb: KnowledgeBase,
    profile: UserProfile,
    ai: Optional[AIClient],
    exam: str,
    task_num: int = 1,
) -> dict:
    task_key = f"task{task_num}"
    prompts = _SPEAKING_PROMPTS.get(exam, {}).get(task_key, [
        "Describe a place that is important to you and explain why."
    ])
    import random
    prompt_text = random.choice(prompts)

    console.print(Panel(
        f"[bold cyan]Speaking Task {task_num}[/bold cyan]\n\n{prompt_text}\n\n"
        "[dim]Prep: 15 sec · Response: 45 sec · Type your response below.[/dim]",
        border_style="cyan", padding=(1, 3),
    ))

    try:
        response = Prompt.ask("\n  Your response")
    except (EOFError, KeyboardInterrupt):
        response = ""

    if not response:
        return {"score": 0}

    if not ai:
        try:
            score = float(Prompt.ask("  Self-score (0-4)", default="2"))
        except (EOFError, KeyboardInterrupt):
            score = 2.0
        return {"score": score}

    with console.status("[bold blue]Scoring your speaking...[/bold blue]"):
        feedback = ai.evaluate_speaking(response, task_key, profile.cefr_level)

    overall = feedback.get("overall", 0)
    console.print(f"\n  Overall score: [bold cyan]{overall}/4[/bold cyan]")
    for imp in feedback.get("improvements", [])[:2]:
        console.print(f"  [yellow]>[/yellow] {imp}")

    return {"score": overall, "feedback": feedback}


# ------------------------------------------------------------------
# Report
# ------------------------------------------------------------------

def _build_report(
    exam_id: str,
    exam: str,
    exam_name: str,
    profile: UserProfile,
    results: list[dict],
    total_elapsed: int,
) -> dict:
    section_summaries = []
    overall_scores = []
    for r in results:
        section_summaries.append({
            "section": r["section"],
            "items_completed": r["items_completed"],
            "avg_score": r["avg_score"],
        })
        overall_scores.append(r["avg_score"])

    overall = round(sum(overall_scores) / max(len(overall_scores), 1), 2)

    return {
        "exam_id": exam_id,
        "exam": exam,
        "exam_name": exam_name,
        "date": datetime.now().isoformat(),
        "profile": {"name": profile.name, "cefr_level": profile.cefr_level},
        "total_elapsed_sec": total_elapsed,
        "overall_score": overall,
        "sections": section_summaries,
    }


def _display_report(report: dict, report_path: Path) -> None:
    console.print()
    console.print(Rule("[bold]Mock Exam Report[/bold]", style="cyan"))
    console.print()

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, padding=(0, 2))
    table.add_column("Section", style="bold")
    table.add_column("Items", justify="center")
    table.add_column("Avg Score", justify="center")

    for sec in report["sections"]:
        score = sec["avg_score"]
        color = "green" if score >= 3.5 else "yellow" if score >= 2.5 else "red"
        table.add_row(
            sec["section"],
            str(sec["items_completed"]),
            f"[{color}]{score}[/{color}]",
        )

    overall = report["overall_score"]
    overall_color = "green" if overall >= 3.5 else "yellow" if overall >= 2.5 else "red"
    table.add_section()
    table.add_row(
        "[bold]Overall[/bold]", "",
        f"[{overall_color}][bold]{overall}[/bold][/{overall_color}]",
    )

    elapsed = report["total_elapsed_sec"]
    console.print(Panel(
        table,
        title=f"[bold cyan]{report['exam_name']} — {report['date'][:10]}[/bold cyan]",
        border_style="cyan",
    ))
    console.print(
        f"  Time: {elapsed // 60}m {elapsed % 60}s  |  "
        f"Report saved: [dim]{report_path}[/dim]\n"
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _display_exam_overview(cfg: dict) -> None:
    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    table.add_column("Section", style="bold")
    table.add_column("Time", justify="right")
    table.add_column("Items", justify="right")

    total_min = 0
    for sec in cfg["sections"]:
        table.add_row(sec["name"], f"{sec['minutes']}m", str(sec["items"]))
        total_min += sec["minutes"]
    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total_min}m[/bold]", "")

    console.print(Panel(
        table,
        title=f"[bold cyan]{cfg['name']} — Exam Overview[/bold cyan]",
        border_style="cyan",
    ))


def _pick_mode(cfg: dict, section: Optional[str]) -> Optional[str]:
    if section:
        return section

    section_names = [s["name"] for s in cfg["sections"]]
    console.print("\n  [bold]Options:[/bold]")
    console.print("  [cyan]full[/cyan]  — run all sections")
    for name in section_names:
        console.print(f"  [cyan]{name}[/cyan]")
    console.print()

    choices = ["full"] + section_names
    try:
        choice = Prompt.ask("  Select", choices=choices, default="full")
        return choice
    except (EOFError, KeyboardInterrupt):
        return None


# ------------------------------------------------------------------
# Built-in prompts
# ------------------------------------------------------------------

_WRITING_PROMPTS = {
    "toefl": [
        "Do you agree or disagree with the following statement? "
        "Technology has made it easier for people to learn new skills. "
        "Use specific reasons and examples to support your answer.",
        "Some people believe that universities should focus on practical skills. "
        "Others think theoretical knowledge is more important. "
        "Discuss both views and give your opinion.",
    ],
    "gre": [
        "The following appeared in a report: 'Our city should invest in renewable energy "
        "because neighboring cities that did so saw a 20% drop in energy costs.' "
        "Write a response in which you examine the stated and/or unstated assumptions.",
        "Write an essay in response to the following issue: "
        "'In any field of endeavor, it is impossible to make a significant contribution "
        "without first being strongly influenced by past achievements within that field.'",
    ],
    "ielts": [
        "Some people think that the best way to reduce crime is to give longer prison sentences. "
        "Others, however, believe there are better alternative ways of reducing crime. "
        "Discuss both views and give your own opinion.",
        "The graph below shows the percentage of households with internet access in three countries "
        "between 2000 and 2020. Summarise the information by selecting and reporting the main features.",
    ],
    "general": [
        "Describe a significant challenge you have overcome and what you learned from it.",
        "What is the most important invention of the last 100 years? Explain your choice.",
    ],
}

_SPEAKING_PROMPTS = {
    "toefl": {
        "task1": [
            "Talk about a person in your life who has had a significant influence on you. "
            "Explain why this person has been important to you.",
            "Describe a place in your hometown that you enjoy visiting. "
            "Explain why you like going there.",
        ],
        "task2": [
            "Some students prefer to study alone. Others prefer to study in groups. "
            "Which do you prefer and why?",
        ],
        "task3": [
            "The university is considering eliminating the foreign language requirement. "
            "The man in the conversation supports this change. Summarize his reasons.",
        ],
        "task4": [
            "Using the concept of cognitive load theory from the lecture, "
            "explain how it applies to learning new vocabulary.",
        ],
    },
}
