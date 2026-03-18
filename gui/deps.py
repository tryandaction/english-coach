"""
Shared dependency injection for GUI — mirrors _get_components() in cli/app.py.
Components are loaded once at startup and cached as module-level singletons.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

import yaml


def _get_config_path() -> Path:
    """Return config.yaml path.

    Frozen (installed): %APPDATA%/EnglishCoach/config.yaml  (writable by user)
    Dev mode: CWD/config.yaml
    """
    if getattr(sys, "frozen", False):
        appdata = Path(os.environ.get("APPDATA", Path.home())) / "EnglishCoach"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata / "config.yaml"
    return Path("config.yaml")


def get_content_dir() -> Path:
    """Return content directory path: handles both frozen (PyInstaller) and dev mode."""
    from utils.paths import get_content_dir as _get_content_dir
    return _get_content_dir()


_CONFIG_PATH = _get_config_path()
_components = None  # cached tuple
_BUILTIN_CONTENT_DIRS = ("grammar", "listening", "reading")


def _load_env(data_dir: Path) -> None:
    # .env lives next to config.yaml (same dir as exe or CWD)
    env_file = _CONFIG_PATH.parent / ".env"
    if not env_file.exists():
        env_file = data_dir.parent / ".env"  # fallback for legacy layout
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _iter_builtin_content_files(content_dir: Path):
    supported = {".md", ".txt", ".pdf", ".docx"}
    for dirname in _BUILTIN_CONTENT_DIRS:
        source_dir = content_dir / dirname
        if not source_dir.exists():
            continue
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in supported:
                yield path


def _compute_builtin_content_signature(content_dir: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for path in _iter_builtin_content_files(content_dir):
        digest.update(path.relative_to(content_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
        count += 1
    return count, digest.hexdigest()


def _sync_builtin_content(kb, data_dir: Path) -> None:
    content_dir = get_content_dir()
    file_count, signature = _compute_builtin_content_signature(content_dir)
    if file_count == 0:
        return

    manifest_path = data_dir / ".builtin_content_sync.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("signature") == signature:
                return
        except Exception:
            pass

    from core.ingestion.pipeline import IngestionPipeline

    pipeline = IngestionPipeline()
    added_total = 0
    scanned = []
    for dirname in _BUILTIN_CONTENT_DIRS:
        source_dir = content_dir / dirname
        if not source_dir.exists():
            continue
        chunks = pipeline.ingest_directory(source_dir)
        added_total += kb.add_chunks(chunks)
        scanned.append({"dir": dirname, "chunk_count": len(chunks)})

    manifest = {
        "signature": signature,
        "file_count": file_count,
        "added_chunks": added_total,
        "scanned": scanned,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        # Create default config on first run
        default_config = {
            "backend": "",
            "api_key": "",
            "data_dir": "data",
            "history_retention_days": 30,
            "user": {
                "name": "",
                "target_exam": "",
            }
        }
        try:
            _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, allow_unicode=True)
            return default_config
        except Exception:
            return default_config
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_components():
    """Return cached (kb, srs, user_model, ai, profile). Thread-safe after first call."""
    global _components
    if _components is not None:
        kb, srs, user_model, ai, profile = _components
        # If ai was None (no key at startup), retry loading it
        if ai is None:
            cfg = load_config()
            _raw = cfg.get("data_dir", "data")
            data_dir = Path(_raw) if Path(_raw).is_absolute() else _CONFIG_PATH.parent / Path(_raw)
            _load_env(data_dir)
            from ai.client import load_client
            ai = load_client(cfg, data_dir)
            if ai is not None:
                _components = (kb, srs, user_model, ai, profile)
        return _components

    from core.knowledge_base.store import KnowledgeBase
    from core.srs.engine import SM2Engine
    from core.user_model.profile import UserModel

    cfg = load_config()
    _raw = cfg.get("data_dir", "data")
    data_dir = Path(_raw) if Path(_raw).is_absolute() else _CONFIG_PATH.parent / Path(_raw)
    # Auto-create data_dir if it doesn't exist (needed for license.key and databases)
    data_dir.mkdir(parents=True, exist_ok=True)

    # IMPORTANT: Load .env BEFORE loading AI client to ensure old-format licenses work
    _load_env(data_dir)

    db_path = data_dir / "user.db"
    kb = KnowledgeBase(data_dir)
    _sync_builtin_content(kb, data_dir)
    srs = SM2Engine(db_path)
    user_model = UserModel(db_path)

    # Lazy load AI client - don't block startup if license check is slow
    ai = None
    try:
        from ai.client import load_client
        ai = load_client(cfg, data_dir)
    except Exception:
        pass  # AI client will be None, can be loaded later

    active_uid = cfg.get("active_user_id")
    profile = user_model.get_profile(active_uid) if active_uid else user_model.get_first_profile()

    _components = (kb, srs, user_model, ai, profile)
    return _components


def reset_components():
    """Force reload on next call (e.g. after setup or user switch)."""
    global _components
    _components = None
