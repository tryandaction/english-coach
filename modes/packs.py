"""
Content pack discovery and management.
Scans local folders for content packs and provides a simple install/list interface.
No network required — works entirely with local paths.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box

from cli.display import print_header
from utils.paths import get_content_dir

console = Console()

# A content pack is any folder containing at least one supported file
_SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".docx"}

# Built-in pack registry — lightweight JSON index bundled with the app
_REGISTRY_FILE = get_content_dir() / "pack_registry.json"


def run_packs_manager(
    config: dict,
    config_path: Path,
    action: str | None = None,
) -> None:
    """
    Manage content packs.
    Actions: list, scan, add, remove
    """
    print_header("内容包管理  ·  Content Packs")

    if action is None:
        action = _pick_action()

    if action == "list":
        _list_installed(config)
    elif action == "scan":
        _scan_for_packs(config, config_path)
    elif action == "add":
        _add_pack(config, config_path)
    elif action == "remove":
        _remove_pack(config, config_path)
    elif action == "registry":
        _show_registry()


# ------------------------------------------------------------------
# Actions
# ------------------------------------------------------------------

def _pick_action() -> str:
    console.print("  [bold]Actions:[/bold]")
    console.print("  [cyan]list[/cyan]      — show installed content paths")
    console.print("  [cyan]scan[/cyan]      — auto-detect packs in a folder")
    console.print("  [cyan]add[/cyan]       — manually add a content path")
    console.print("  [cyan]remove[/cyan]    — remove a content path")
    console.print("  [cyan]registry[/cyan]  — show known pack types")
    console.print()
    try:
        return Prompt.ask(
            "  Action",
            choices=["list", "scan", "add", "remove", "registry"],
            default="list",
        )
    except (EOFError, KeyboardInterrupt):
        return "list"


def _list_installed(config: dict) -> None:
    paths = config.get("content_paths", [])
    if not paths:
        console.print("[yellow]No content paths configured.[/yellow]")
        console.print("Use [bold]english-coach packs --action add[/bold] to add one.\n")
        return

    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, padding=(0, 2))
    table.add_column("#", style="dim", width=3)
    table.add_column("Path", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Status", justify="center")

    for i, p in enumerate(paths, 1):
        path = Path(p)
        if path.exists():
            count = sum(1 for f in path.rglob("*") if f.suffix.lower() in _SUPPORTED_EXTS)
            status = "[green]✓ found[/green]"
        else:
            count = 0
            status = "[red]✗ missing[/red]"
        table.add_row(str(i), str(p), str(count) if count else "—", status)

    console.print()
    console.print(Panel(table, title="[bold cyan]Installed Content Paths[/bold cyan]", border_style="cyan"))
    console.print(
        "  Run [bold]english-coach ingest <path>[/bold] to load a path into the knowledge base.\n"
    )


def _scan_for_packs(config: dict, config_path: Path) -> None:
    """Auto-detect content pack folders inside a parent directory."""
    try:
        parent = Prompt.ask("  Scan folder (parent directory to search in)")
    except (EOFError, KeyboardInterrupt):
        return

    parent_path = Path(parent)
    if not parent_path.exists():
        console.print(f"[red]Path not found: {parent}[/red]")
        return

    # Find immediate subdirectories that contain supported files
    found: list[Path] = []
    for sub in sorted(parent_path.iterdir()):
        if sub.is_dir():
            count = sum(1 for f in sub.rglob("*") if f.suffix.lower() in _SUPPORTED_EXTS)
            if count > 0:
                found.append(sub)
    # Also check the parent itself
    direct = sum(1 for f in parent_path.glob("*") if f.suffix.lower() in _SUPPORTED_EXTS)
    if direct > 0:
        found.insert(0, parent_path)

    if not found:
        console.print("[yellow]No content packs found in that folder.[/yellow]\n")
        return

    console.print(f"\n  Found [cyan]{len(found)}[/cyan] content pack(s):\n")
    for i, p in enumerate(found, 1):
        count = sum(1 for f in p.rglob("*") if f.suffix.lower() in _SUPPORTED_EXTS)
        pack_type = _detect_pack_type(p.name)
        console.print(
            f"  [cyan]{i}[/cyan]. [bold]{p.name}[/bold]  "
            f"[dim]{count} files · {pack_type}[/dim]"
        )

    console.print()
    existing = set(config.get("content_paths", []))
    new_paths = [str(p) for p in found if str(p) not in existing]

    if not new_paths:
        console.print("[dim]All found packs are already in your config.[/dim]\n")
        return

    try:
        if Confirm.ask(f"  Add all {len(new_paths)} new pack(s) to config?", default=True):
            _save_paths(config, config_path, new_paths)
            console.print(
                f"[green]✓ Added {len(new_paths)} path(s) to config.[/green]\n"
                "Run [bold]english-coach ingest <path>[/bold] for each to load them.\n"
            )
    except (EOFError, KeyboardInterrupt):
        pass


def _add_pack(config: dict, config_path: Path) -> None:
    try:
        path_str = Prompt.ask("  Content path to add")
    except (EOFError, KeyboardInterrupt):
        return

    path = Path(path_str)
    if not path.exists():
        console.print(f"[yellow]Warning: path does not exist yet: {path_str}[/yellow]")
        try:
            if not Confirm.ask("  Add anyway?", default=False):
                return
        except (EOFError, KeyboardInterrupt):
            return

    existing = config.get("content_paths", [])
    if path_str in existing:
        console.print("[dim]Path already in config.[/dim]\n")
        return

    _save_paths(config, config_path, [path_str])
    console.print(f"[green]✓ Added: {path_str}[/green]\n")


def _remove_pack(config: dict, config_path: Path) -> None:
    paths = config.get("content_paths", [])
    if not paths:
        console.print("[yellow]No content paths to remove.[/yellow]\n")
        return

    console.print("\n  [bold]Installed paths:[/bold]")
    for i, p in enumerate(paths, 1):
        console.print(f"  [cyan]{i}[/cyan]. {p}")

    try:
        choice = Prompt.ask(
            "\n  Remove path number",
            choices=[str(i) for i in range(1, len(paths) + 1)],
        )
    except (EOFError, KeyboardInterrupt):
        return

    removed = paths[int(choice) - 1]
    config["content_paths"] = [p for p in paths if p != removed]
    with open(config_path, "w", encoding="utf-8") as f:
        import yaml
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    console.print(f"[green]✓ Removed: {removed}[/green]\n")
    console.print("[dim]Note: already-ingested chunks remain in the knowledge base.[/dim]\n")


def _show_registry() -> None:
    """Show the built-in pack type registry."""
    registry = _load_registry()
    if not registry:
        console.print("[dim]No registry file found.[/dim]\n")
        return

    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 2))
    table.add_column("Pack Type", style="bold")
    table.add_column("Exam Focus")
    table.add_column("Description")

    for entry in registry:
        table.add_row(
            entry.get("name", ""),
            entry.get("exam", "general").upper(),
            entry.get("description", ""),
        )

    console.print()
    console.print(Panel(table, title="[bold cyan]Known Content Pack Types[/bold cyan]", border_style="cyan"))
    console.print()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _save_paths(config: dict, config_path: Path, new_paths: list[str]) -> None:
    existing = config.get("content_paths", [])
    for p in new_paths:
        if p not in existing:
            existing.append(p)
    config["content_paths"] = existing
    with open(config_path, "w", encoding="utf-8") as f:
        import yaml
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def _detect_pack_type(folder_name: str) -> str:
    """Guess content type from folder name."""
    name = folder_name.lower()
    if "toefl" in name and "speak" in name:
        return "TOEFL Speaking"
    if "toefl" in name and "read" in name:
        return "TOEFL Reading"
    if "toefl" in name:
        return "TOEFL"
    if "gre" in name and "physics" in name:
        return "GRE Physics"
    if "gre" in name:
        return "GRE"
    if "ielts" in name:
        return "IELTS"
    if "cet" in name:
        return "CET-4/6"
    if "vocab" in name or "word" in name:
        return "Vocabulary"
    if "grammar" in name:
        return "Grammar"
    return "General"


def _load_registry() -> list[dict]:
    if _REGISTRY_FILE.exists():
        try:
            with open(_REGISTRY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []
