from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_COMMERCIAL_DIR = ROOT / "private_commercial"


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def _unique(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def private_commercial_dir() -> Path:
    return PRIVATE_COMMERCIAL_DIR


def cloud_activation_config_candidates() -> list[Path]:
    env_path = _env_path("EC_ACTIVATION_CONFIG_PATH")
    paths = [
        env_path,
        PRIVATE_COMMERCIAL_DIR / "cloud_activation_config.json",
        PRIVATE_COMMERCIAL_DIR / "release" / "cloud_activation_config.json",
        ROOT / "cloud_activation_config.json",
        ROOT / "releases" / "cloud_activation_config.json",
    ]
    return _unique([path for path in paths if path is not None])


def seller_config_candidates() -> list[Path]:
    env_path = _env_path("EC_SELLER_CONFIG_PATH")
    paths = [
        env_path,
        PRIVATE_COMMERCIAL_DIR / "seller_cloud_config.json",
        ROOT / "seller_cloud_config.json",
    ]
    return _unique([path for path in paths if path is not None])


def preferred_key_log_path() -> Path:
    env_path = _env_path("EC_KEY_LOG_PATH")
    if env_path is not None:
        return env_path
    legacy_path = ROOT / "key_log.jsonl"
    if legacy_path.exists():
        return legacy_path
    return PRIVATE_COMMERCIAL_DIR / "key_log.jsonl"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
