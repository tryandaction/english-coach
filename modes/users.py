"""
Multi-user management mode — list, switch, create, delete user profiles.
All operations are pure SQLite — zero API cost.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box

from core.srs.engine import SM2Engine
from core.user_model.profile import UserModel, UserProfile
from cli.display import print_header

console = Console()


def run_users_manager(
    user_model: UserModel,
    srs: SM2Engine,
    current_profile: UserProfile,
    action: str | None = None,
) -> str | None:
    """
    Manage user profiles.
    Returns new active user_id if the user switched profiles, else None.
    """
    print_header("用户管理  ·  User Profiles")

    if action is None:
        action = _pick_action()

    if action == "list":
        _list_users(user_model, srs, current_profile)
    elif action == "switch":
        return _switch_user(user_model, srs, current_profile)
    elif action == "new":
        _create_user(user_model)
    elif action == "delete":
        _delete_user(user_model, srs, current_profile)
    elif action == "rename":
        _rename_user(user_model, current_profile)

    return None


# ------------------------------------------------------------------
# Actions
# ------------------------------------------------------------------

def _pick_action() -> str:
    console.print("  [bold]Actions:[/bold]")
    console.print("  [cyan]list[/cyan]    — show all profiles")
    console.print("  [cyan]switch[/cyan]  — switch active user")
    console.print("  [cyan]new[/cyan]     — create a new profile")
    console.print("  [cyan]delete[/cyan]  — delete a profile")
    console.print("  [cyan]rename[/cyan]  — rename current user")
    console.print()
    try:
        return Prompt.ask(
            "  Action",
            choices=["list", "switch", "new", "delete", "rename"],
            default="list",
        )
    except (EOFError, KeyboardInterrupt):
        return "list"


def _list_users(
    user_model: UserModel,
    srs: SM2Engine,
    current_profile: UserProfile,
) -> None:
    profiles = _get_all_profiles(user_model)
    if not profiles:
        console.print("[yellow]No profiles found.[/yellow]")
        return

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, padding=(0, 2))
    table.add_column("", width=2)
    table.add_column("Name", style="bold")
    table.add_column("CEFR", justify="center")
    table.add_column("Exam", justify="center")
    table.add_column("Words", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Streak", justify="right")

    for p in profiles:
        active = "[green]▶[/green]" if p.user_id == current_profile.user_id else ""
        deck = srs.deck_stats(p.user_id)
        summary = user_model.progress_summary(p.user_id)
        streak = summary.get("streak_days", 0)
        streak_str = f"[yellow]{streak}d[/yellow]" if streak else "—"
        table.add_row(
            active,
            p.name,
            f"[cyan]{p.cefr_level}[/cyan]",
            p.target_exam.upper(),
            str(deck["total"]),
            str(summary["total_sessions"]),
            streak_str,
        )

    console.print()
    console.print(Panel(table, title="[bold cyan]All Profiles[/bold cyan]", border_style="cyan"))
    console.print()


def _switch_user(
    user_model: UserModel,
    srs: SM2Engine,
    current_profile: UserProfile,
) -> str | None:
    profiles = _get_all_profiles(user_model)
    others = [p for p in profiles if p.user_id != current_profile.user_id]

    if not others:
        console.print("[yellow]No other profiles to switch to. Use 'new' to create one.[/yellow]")
        return None

    console.print("\n  [bold]Available profiles:[/bold]")
    for i, p in enumerate(others, 1):
        deck = srs.deck_stats(p.user_id)
        console.print(
            f"  [cyan]{i}[/cyan]. {p.name}  "
            f"[dim]CEFR {p.cefr_level} · {p.target_exam.upper()} · {deck['total']} words[/dim]"
        )

    try:
        choice = Prompt.ask(
            "\n  Select profile number",
            choices=[str(i) for i in range(1, len(others) + 1)],
        )
    except (EOFError, KeyboardInterrupt):
        return None

    selected = others[int(choice) - 1]
    console.print(f"\n[green]✓ Switched to profile: [bold]{selected.name}[/bold][/green]")
    console.print("[dim]Restart the command to use the new profile.[/dim]\n")

    # Persist the selection as the "first" profile by re-saving with a lower rowid trick:
    # We update the config file's active_user_id field instead.
    return selected.user_id


def _create_user(user_model: UserModel) -> UserProfile | None:
    console.print("\n  [bold]Create new profile[/bold]")
    try:
        name = Prompt.ask("  Name")
        exam = Prompt.ask(
            "  Target exam",
            choices=["toefl", "gre", "ielts", "cet", "general"],
            default="toefl",
        )
    except (EOFError, KeyboardInterrupt):
        return None

    profile = user_model.create_profile(name=name, target_exam=exam)
    console.print(f"\n[green]✓ Profile created for [bold]{name}[/bold][/green]")
    console.print("[dim]Use 'switch' to activate this profile.[/dim]\n")
    return profile


def _delete_user(
    user_model: UserModel,
    srs: SM2Engine,
    current_profile: UserProfile,
) -> None:
    profiles = _get_all_profiles(user_model)
    others = [p for p in profiles if p.user_id != current_profile.user_id]

    if not others:
        console.print("[yellow]Cannot delete the only profile.[/yellow]")
        return

    console.print("\n  [bold]Delete a profile:[/bold]")
    for i, p in enumerate(others, 1):
        console.print(f"  [cyan]{i}[/cyan]. {p.name}  [dim]{p.target_exam.upper()}[/dim]")

    try:
        choice = Prompt.ask(
            "\n  Select profile to delete",
            choices=[str(i) for i in range(1, len(others) + 1)],
        )
        target = others[int(choice) - 1]
        if not Confirm.ask(
            f"\n  [red]Delete profile '{target.name}' and all their data?[/red]",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            return
    except (EOFError, KeyboardInterrupt):
        return

    uid = target.user_id
    db = user_model._db
    db.execute("DELETE FROM users WHERE user_id=?", (uid,))
    db.execute("DELETE FROM skill_scores WHERE user_id=?", (uid,))
    db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    db.execute("DELETE FROM seen_content WHERE user_id=?", (uid,))
    db.commit()

    srs_db = srs._db
    srs_db.execute("DELETE FROM srs_cards WHERE user_id=?", (uid,))
    srs_db.execute("DELETE FROM srs_reviews WHERE user_id=?", (uid,))
    srs_db.commit()

    console.print(f"\n[green]✓ Profile '{target.name}' deleted.[/green]\n")


def _rename_user(user_model: UserModel, profile: UserProfile) -> None:
    try:
        new_name = Prompt.ask(f"  New name for [bold]{profile.name}[/bold]")
    except (EOFError, KeyboardInterrupt):
        return
    if not new_name.strip():
        return
    profile.name = new_name.strip()
    user_model._save_profile(profile)
    console.print(f"\n[green]✓ Renamed to [bold]{profile.name}[/bold][/green]\n")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_all_profiles(user_model: UserModel) -> list[UserProfile]:
    rows = user_model._db.execute(
        "SELECT profile_json FROM users ORDER BY rowid ASC"
    ).fetchall()
    profiles = []
    for row in rows:
        try:
            profiles.append(UserProfile.from_json(row["profile_json"]))
        except Exception:
            pass
    return profiles
