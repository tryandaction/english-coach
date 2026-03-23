"""
Shared dependency injection for GUI — mirrors _get_components() in cli/app.py.
Components are loaded once at startup and cached as module-level singletons.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
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
_user_components = None  # cached (user_model, profile)
_components_lock = threading.Lock()
_user_components_lock = threading.Lock()
_warm_thread: Optional[threading.Thread] = None
_vocab_sync_thread: Optional[threading.Thread] = None
_BUILTIN_CONTENT_DIRS = ("grammar", "listening", "reading")
_BUILTIN_VOCAB_DIRS = ("vocab", "vocab_selected", "vocab_expanded")
_ALLOWED_BACKENDS = {"", "deepseek", "qwen", "anthropic", "openai"}
_ALLOW_DEV_MACHINE_PATH_ENV = "ENGLISH_COACH_ALLOW_DEV_MACHINE_PATH"


def _default_config() -> dict:
    return {
        "backend": "",
        "api_key": "",
        "data_dir": "data",
        "history_retention_days": 30,
        "user": {
            "name": "",
            "target_exam": "",
            "target_exam_date": "",
        },
    }


def _normalize_path_text(raw: object) -> str:
    return str(raw or "").strip().lower().replace("/", "\\")


def _looks_like_dev_machine_path(raw: object) -> bool:
    if os.environ.get(_ALLOW_DEV_MACHINE_PATH_ENV, "").strip() == "1":
        return False
    text = _normalize_path_text(raw)
    if not text:
        return False
    if "english_coach_release_smoke_" in text:
        return True
    return "\\temp\\" in text and ("english coach" in text or "english_coach" in text)


def _sanitize_content_paths(content_paths: object) -> list[str]:
    if not isinstance(content_paths, list):
        return []
    return [
        str(path).strip()
        for path in content_paths
        if str(path or "").strip() and not _looks_like_dev_machine_path(path)
    ]


def _should_reset_frozen_user_config(cfg: object) -> bool:
    if not isinstance(cfg, dict):
        return True
    if _looks_like_dev_machine_path(cfg.get("data_dir", "")):
        return True
    content_paths = cfg.get("content_paths", [])
    if not isinstance(content_paths, list):
        return False
    return any(_looks_like_dev_machine_path(path) for path in content_paths)


def _build_sanitized_user_config(cfg: dict) -> dict:
    sanitized = _default_config()
    backend = str(cfg.get("backend", "") or "").strip().lower()
    if backend in _ALLOWED_BACKENDS:
        sanitized["backend"] = backend

    try:
        history_days = int(cfg.get("history_retention_days", 30))
        if history_days > 0:
            sanitized["history_retention_days"] = history_days
    except Exception:
        pass

    user = cfg.get("user")
    if isinstance(user, dict):
        for key in ("name", "target_exam", "target_exam_date"):
            value = str(user.get(key, "") or "").strip()
            if value:
                sanitized["user"][key] = value

    clean_content_paths = _sanitize_content_paths(cfg.get("content_paths"))
    if clean_content_paths:
        sanitized["content_paths"] = clean_content_paths

    return sanitized


def sanitize_frozen_user_config() -> bool:
    if not getattr(sys, "frozen", False):
        return False
    if not _CONFIG_PATH.exists():
        return False

    raw_text = ""
    parsed: object = {}
    parse_failed = False
    try:
        raw_text = _CONFIG_PATH.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw_text) or {}
    except Exception:
        parsed = None
        parse_failed = True

    if not parse_failed and not _should_reset_frozen_user_config(parsed):
        return False

    cfg = parsed if isinstance(parsed, dict) else {}
    backup_path = _CONFIG_PATH.parent / "config.dev-backup.yaml"
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if raw_text.strip():
        backup_path.write_text(raw_text, encoding="utf-8")
    sanitized = _build_sanitized_user_config(cfg)
    _CONFIG_PATH.write_text(
        yaml.dump(sanitized, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    return True


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


def _sync_builtin_vocab_if_needed(srs, profile) -> None:
    if not profile:
        return
    row = srs._db.execute(
        "SELECT COUNT(*) AS count FROM vocabulary WHERE source != 'user'"
    ).fetchone()
    if int(row["count"] or 0) > 0:
        return

    from core.vocab.catalog import sync_builtin_vocabulary

    content_root = get_content_dir()
    vocab_dirs = [content_root / dirname for dirname in _BUILTIN_VOCAB_DIRS]
    sync_builtin_vocabulary(vocab_dirs, srs, profile)


def _schedule_builtin_vocab_sync(data_dir: Path, profile) -> None:
    global _vocab_sync_thread
    if not profile:
        return
    if _vocab_sync_thread and _vocab_sync_thread.is_alive():
        return

    def _runner() -> None:
        try:
            from core.srs.engine import SM2Engine

            srs = SM2Engine(data_dir / "user.db")
            try:
                _sync_builtin_vocab_if_needed(srs, profile)
            finally:
                try:
                    srs._db.close()
                except Exception:
                    pass
        except Exception:
            pass

    _vocab_sync_thread = threading.Thread(target=_runner, daemon=True, name="vocab-sync")
    _vocab_sync_thread.start()


def load_config() -> dict:
    default_config = _default_config()
    if not _CONFIG_PATH.exists():
        # Create default config on first run
        try:
            _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, allow_unicode=True)
            return default_config
        except Exception:
            return default_config
    if getattr(sys, "frozen", False):
        try:
            sanitize_frozen_user_config()
        except Exception:
            pass
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except Exception:
        if getattr(sys, "frozen", False):
            try:
                _CONFIG_PATH.write_text(
                    yaml.dump(default_config, allow_unicode=True, default_flow_style=False),
                    encoding="utf-8",
                )
            except Exception:
                pass
        return default_config
    return loaded if isinstance(loaded, dict) else default_config


def _resolve_data_dir(cfg: dict) -> Path:
    raw = cfg.get("data_dir", "data")
    path = Path(raw)
    return path if path.is_absolute() else _CONFIG_PATH.parent / path


def _build_user_context(cfg: dict):
    from core.user_model.profile import UserModel

    data_dir = _resolve_data_dir(cfg)
    data_dir.mkdir(parents=True, exist_ok=True)
    user_model = UserModel(data_dir / "user.db")
    active_uid = cfg.get("active_user_id")
    profile = user_model.get_profile(active_uid) if active_uid else user_model.get_first_profile()
    return user_model, profile


def get_user_components():
    """Return cached lightweight (user_model, profile) without forcing KB/SRS init."""
    global _user_components

    if _components is not None:
        return _components[2], _components[4]

    if _user_components is not None:
        return _user_components

    with _user_components_lock:
        if _components is not None:
            return _components[2], _components[4]
        if _user_components is None:
            cfg = load_config()
            _user_components = _build_user_context(cfg)
        return _user_components


def get_components():
    """Return cached (kb, srs, user_model, ai, profile). Thread-safe after first call."""
    global _components, _user_components
    if _components is not None:
        kb, srs, user_model, ai, profile = _components
        # If ai was None (no key at startup), retry loading it
        if ai is None:
            with _components_lock:
                if _components is not None:
                    kb, srs, user_model, ai, profile = _components
                if ai is None:
                    cfg = load_config()
                    data_dir = _resolve_data_dir(cfg)
                    _load_env(data_dir)
                    from ai.client import load_client
                    ai = load_client(cfg, data_dir)
                    if ai is not None:
                        _components = (kb, srs, user_model, ai, profile)
        return _components

    with _components_lock:
        if _components is not None:
            return _components

        from core.knowledge_base.store import KnowledgeBase
        from core.srs.engine import SM2Engine

        cfg = load_config()
        data_dir = _resolve_data_dir(cfg)
        data_dir.mkdir(parents=True, exist_ok=True)

        # IMPORTANT: Load .env BEFORE loading AI client to ensure old-format licenses work
        _load_env(data_dir)

        db_path = data_dir / "user.db"
        kb = KnowledgeBase(data_dir)
        _sync_builtin_content(kb, data_dir)
        srs = SM2Engine(db_path)

        with _user_components_lock:
            if _user_components is not None:
                user_model, profile = _user_components
            else:
                user_model, profile = _build_user_context(cfg)
                _user_components = (user_model, profile)

        # Lazy load AI client - don't block startup if license check is slow
        ai = None
        try:
            from ai.client import load_client
            ai = load_client(cfg, data_dir)
        except Exception:
            pass  # AI client will be None, can be loaded later

        _components = (kb, srs, user_model, ai, profile)
        return _components


def warm_components(blocking: bool = False) -> None:
    """Warm the heavy component cache after setup/license changes."""
    global _warm_thread

    def _runner() -> None:
        try:
            get_components()
        except Exception:
            pass

    if blocking:
        _runner()
        return

    if _components is not None:
        return
    if _warm_thread and _warm_thread.is_alive():
        return
    _warm_thread = threading.Thread(target=_runner, daemon=True, name="deps-warm")
    _warm_thread.start()


def reset_components():
    """Force reload on next call (e.g. after setup or user switch)."""
    global _components, _user_components, _warm_thread, _vocab_sync_thread

    def _safe_close(obj, attr: str) -> None:
        try:
            handle = getattr(obj, attr, None)
            if handle is not None:
                handle.close()
        except Exception:
            pass

    if _components is not None:
        kb, srs, user_model, _ai, _profile = _components
        _safe_close(kb, "_sql")
        _safe_close(srs, "_db")
        if _user_components is None or _user_components[0] is not user_model:
            _safe_close(user_model, "_db")
    if _user_components is not None:
        user_model, _profile = _user_components
        _safe_close(user_model, "_db")

    _components = None
    _user_components = None
    _warm_thread = None
    _vocab_sync_thread = None
