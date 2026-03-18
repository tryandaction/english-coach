"""Setup wizard API — first-run configuration."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from gui.deps import load_config, reset_components, _CONFIG_PATH

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupRequest(BaseModel):
    name: str
    backend: str = "deepseek"
    api_key: str = ""
    target_exam: str = "toefl"
    content_path: str = ""
    history_retention_days: int = 30
    data_dir: str = ""


_ENV_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _resolve_data_dir(cfg: dict) -> Path:
    raw = cfg.get("data_dir", "data")
    p = Path(raw)
    return p if p.is_absolute() else _CONFIG_PATH.parent / raw


class CheckDataDirRequest(BaseModel):
    data_dir: str


@router.post("/check_data_dir")
def check_data_dir(req: CheckDataDirRequest):
    """Check if a directory contains valid English Coach data (user.db with a profile)."""
    p = Path(req.data_dir.strip())
    db = p / "user.db"
    if not p.exists():
        return {"valid": False, "error": f"Folder not found: {req.data_dir}"}
    if not db.exists():
        return {"valid": False, "error": f"No user.db found in {req.data_dir}"}
    try:
        from core.user_model.profile import UserModel
        um = UserModel(db)
        profile = um.get_first_profile()
        if not profile:
            return {"valid": False, "error": "Data folder found but contains no user profile"}
        cfg = load_config() or {}
        return {
            "valid": True,
            "name": profile.name,
            "target_exam": getattr(profile, "target_exam", "general"),
            "backend": cfg.get("backend", "deepseek"),
        }
    except Exception as e:
        return {"valid": False, "error": f"Could not read data: {e}"}


@router.get("/data_dir")
def get_data_dir():
    """Return the resolved absolute path of the current data directory."""
    cfg = load_config()
    raw = cfg.get("data_dir", "data")
    p = Path(raw)
    resolved = str((p if p.is_absolute() else _CONFIG_PATH.parent / raw).resolve())
    return {"data_dir": resolved}


@router.get("/status")
def setup_status():
    from gui.version import get_version_mode
    from gui.api.license import build_license_status

    cfg = load_config()
    version_mode = get_version_mode()
    has_profile = False
    data_dir = _resolve_data_dir(cfg)
    try:
        from core.user_model.profile import UserModel
        um = UserModel(data_dir / "user.db")
        has_profile = um.get_first_profile() is not None
    except Exception:
        pass

    runtime = build_license_status(cfg)
    if version_mode != "cloud":
        runtime["active"] = False
        runtime["cloud_license_active"] = False
        runtime["days_left"] = 0
        runtime["needs_reactivation"] = False
        runtime["activation_available"] = False
        runtime["activation_reason"] = "当前版本不提供 Cloud 激活。"
        runtime["server_verified"] = None
        runtime["verification_warning"] = ""
        runtime["ai_mode"] = "self_key" if runtime["has_self_key"] else "none"

    backend = runtime["self_key_backend"] or str(cfg.get("backend", "") or "").lower()
    has_ai_access = bool(runtime["ai_ready"])

    return {
        "configured": has_profile,
        "has_profile": has_profile,
        "version_mode": version_mode,
        "backend": backend,
        "has_api_key": has_ai_access,
        "has_ai_access": has_ai_access,
        "has_self_key": runtime["has_self_key"],
        "has_cloud_license": bool(runtime["cloud_license_active"]),
        "cloud_license_active": bool(runtime["cloud_license_active"]),
        "ai_mode": runtime["ai_mode"],
        "ai_ready": bool(runtime["ai_ready"]),
        "cloud_ai_ready": bool(runtime.get("cloud_ai_ready", False)),
        "activation_available": bool(runtime["activation_available"]),
        "activation_reason": runtime["activation_reason"],
        "needs_reactivation": bool(runtime["needs_reactivation"]),
        "server_verified": runtime["server_verified"],
        "verification_warning": runtime["verification_warning"],
        "license_days_left": int(runtime["days_left"] or 0),
        "self_key_backend": runtime["self_key_backend"],
        "license_error": runtime.get("error", ""),
        "target_exam": cfg.get("user", {}).get("target_exam", ""),
        "name": cfg.get("user", {}).get("name", ""),
        "history_retention_days": int(cfg.get("history_retention_days", 30)),
        "data_dir": cfg.get("data_dir", "data"),
    }


@router.post("")
def run_setup(req: SetupRequest):
    cfg = load_config() or {}
    cfg.setdefault("user", {})
    cfg["user"]["name"] = req.name
    cfg["user"]["target_exam"] = req.target_exam
    cfg["backend"] = req.backend
    cfg["history_retention_days"] = req.history_retention_days

    if req.data_dir:
        cfg["data_dir"] = req.data_dir

    # Save API key to .env next to config.yaml
    if req.api_key:
        env_file = _CONFIG_PATH.parent / ".env"
        env_var = _ENV_KEYS.get(req.backend, "DEEPSEEK_API_KEY")
        lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
        lines = [l for l in lines if not l.startswith(env_var + "=")]
        lines.append(f"{env_var}={req.api_key}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ[env_var] = req.api_key

    if req.content_path:
        cfg.setdefault("content_paths", ["./content"])
        if req.content_path not in cfg["content_paths"]:
            cfg["content_paths"].append(req.content_path)

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

    # Create user profile
    data_dir = _resolve_data_dir(cfg)
    data_dir.mkdir(parents=True, exist_ok=True)
    from core.user_model.profile import UserModel
    um = UserModel(data_dir / "user.db")
    existing = um.get_first_profile()
    if not existing:
        um.create_profile(name=req.name, target_exam=req.target_exam)

    reset_components()
    return {"ok": True}
