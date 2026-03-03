"""
Shared dependency injection for GUI — mirrors _get_components() in cli/app.py.
Components are loaded once at startup and cached as module-level singletons.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import yaml


def _get_config_path() -> Path:
    """Return config.yaml path: next to exe when frozen, else CWD."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "config.yaml"
    return Path("config.yaml")


_CONFIG_PATH = _get_config_path()
_components = None  # cached tuple


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


def load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
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
    from ai.client import load_client

    cfg = load_config()
    _raw = cfg.get("data_dir", "data")
    data_dir = Path(_raw) if Path(_raw).is_absolute() else _CONFIG_PATH.parent / Path(_raw)
    data_dir.mkdir(parents=True, exist_ok=True)
    _load_env(data_dir)

    db_path = data_dir / "user.db"
    kb = KnowledgeBase(data_dir / "kb")
    srs = SM2Engine(db_path)
    user_model = UserModel(db_path)
    ai = load_client(cfg, data_dir)

    active_uid = cfg.get("active_user_id")
    profile = user_model.get_profile(active_uid) if active_uid else user_model.get_first_profile()

    _components = (kb, srs, user_model, ai, profile)
    return _components


def reset_components():
    """Force reload on next call (e.g. after setup or user switch)."""
    global _components
    _components = None
