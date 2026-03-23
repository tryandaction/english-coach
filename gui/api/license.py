"""License API for activating and verifying cloud licenses."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import urllib.error
import urllib.request
import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from gui.deps import load_config, _CONFIG_PATH, _load_env, reset_components
from gui.license import (
    WORKER_CLIENT_TOKEN,
    WORKER_URL,
    encrypt_local_payload,
    get_activation_capability,
    get_license_ai_config,
    get_machine_id,
    make_license_record,
    read_license_record,
    verify_key_format,
    verify_license_record,
)

router = APIRouter(prefix="/api/license", tags=["license"])

_LICENSE_STATUS_CACHE: dict[str, object] = {
    "fingerprint": "",
    "expires_at": 0.0,
    "value": None,
}


_ENV_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _resolve_data_dir(cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    raw = cfg.get("data_dir", "data")
    p = Path(raw)
    return p if p.is_absolute() else _CONFIG_PATH.parent / raw


def _license_file(cfg: dict | None = None) -> Path:
    return _resolve_data_dir(cfg) / "license.key"


def _storage_format(cfg: dict | None = None) -> str:
    record = read_license_record(_license_file(cfg).parent)
    return record.format if record else "missing"


def _license_cache_fingerprint(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    license_path = _license_file(cfg)
    stat = None
    try:
        stat = license_path.stat()
    except FileNotFoundError:
        stat = None
    payload = {
        "data_dir": str(_resolve_data_dir(cfg)),
        "backend": str(cfg.get("backend", "") or "").strip().lower(),
        "license_path": str(license_path),
        "license_exists": bool(stat),
        "license_mtime_ns": int(stat.st_mtime_ns) if stat else 0,
        "license_size": int(stat.st_size) if stat else 0,
        "worker_url": WORKER_URL,
        "client_token_present": bool(WORKER_CLIENT_TOKEN),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _get_cached_license_status(cfg: dict | None = None) -> dict | None:
    fingerprint = _license_cache_fingerprint(cfg)
    if (
        _LICENSE_STATUS_CACHE.get("fingerprint") == fingerprint
        and float(_LICENSE_STATUS_CACHE.get("expires_at", 0.0) or 0.0) > time.time()
        and isinstance(_LICENSE_STATUS_CACHE.get("value"), dict)
    ):
        return dict(_LICENSE_STATUS_CACHE["value"])  # shallow copy
    return None


def _store_cached_license_status(cfg: dict | None, value: dict) -> None:
    _LICENSE_STATUS_CACHE["fingerprint"] = _license_cache_fingerprint(cfg)
    _LICENSE_STATUS_CACHE["expires_at"] = time.time() + 10.0
    _LICENSE_STATUS_CACHE["value"] = dict(value)


def _clear_cached_license_status() -> None:
    _LICENSE_STATUS_CACHE["fingerprint"] = ""
    _LICENSE_STATUS_CACHE["expires_at"] = 0.0
    _LICENSE_STATUS_CACHE["value"] = None


def _self_key_status(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    data_dir = _resolve_data_dir(cfg)
    _load_env(data_dir)

    configured_backend = str(cfg.get("backend", "") or "").strip().lower()
    backend = ""
    env_var = ""
    if configured_backend:
        env_var = _ENV_KEYS.get(configured_backend, "")
        if env_var and os.environ.get(env_var, "").strip():
            backend = configured_backend

    if not backend:
        for candidate, candidate_env in _ENV_KEYS.items():
            if os.environ.get(candidate_env, "").strip():
                backend = candidate
                env_var = candidate_env
                break

    return {
        "has_self_key": bool(backend),
        "self_key_backend": backend,
        "self_key_env_var": env_var,
    }


def _save_proxy_license(
    key: str,
    machine_id: str,
    activate_ts: int,
    days: int,
    session_token: str,
) -> None:
    lf = _license_file()
    lf.parent.mkdir(parents=True, exist_ok=True)
    payload_hex = encrypt_local_payload(key, machine_id, session_token)
    record = make_license_record(
        key=key,
        machine_id=machine_id,
        activate_ts=activate_ts,
        days=days,
        payload_kind="proxy_token",
        payload_hex=payload_hex,
    )
    lf.write_text(record, encoding="utf-8")


def _post_worker(path: str, body: dict) -> dict:
    payload = json.dumps(body).encode("utf-8")
    worker_base = WORKER_URL.rstrip("/")
    last_error = None
    for timeout in (10, 20, 30):
        req = urllib.request.Request(
            f"{worker_base}{path}",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Worker-Token": WORKER_CLIENT_TOKEN,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
                "Origin": worker_base,
                "Referer": f"{worker_base}/",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(error_body)
                if isinstance(parsed, dict):
                    parsed.setdefault("ok", False)
                    parsed.setdefault("http_status", exc.code)
                    return parsed
            except Exception:
                last_error = exc
                continue
        except Exception as exc:
            last_error = exc
    raise last_error


def _verify_remote(key: str, machine_id: str) -> dict:
    if not WORKER_URL or not WORKER_CLIENT_TOKEN:
        return {"reachable": False, "ok": False, "error": "激活服务未配置"}
    try:
        result = _post_worker("/verify", {"key": key, "machine_id": machine_id})
    except Exception as exc:
        return {"reachable": False, "ok": False, "error": f"无法连接激活服务器（{exc}）"}
    return {"reachable": True, **result}


class LicenseRequest(BaseModel):
    key: str


def build_license_status(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    cached = _get_cached_license_status(cfg)
    if cached is not None:
        return cached
    capability = get_activation_capability()
    data_dir = _resolve_data_dir(cfg)
    record = read_license_record(data_dir)
    storage_format = record.format if record else "missing"
    self_key = _self_key_status(cfg)

    def _base_status(**kwargs):
        active = bool(kwargs.get("active", False))
        cloud_ai_ready = bool(kwargs.get("ai_ready", False))
        ai_ready = cloud_ai_ready or self_key["has_self_key"]
        ai_mode = "cloud" if active and cloud_ai_ready else ("self_key" if self_key["has_self_key"] else "none")
        return {
            "active": active,
            "cloud_license_active": active,
            "days_left": int(kwargs.get("days_left", 0) or 0),
            "mode": kwargs.get("mode", "self_key"),
            "ai_mode": ai_mode,
            "ai_ready": ai_ready,
            "cloud_ai_ready": cloud_ai_ready,
            "has_self_key": self_key["has_self_key"],
            "self_key_backend": self_key["self_key_backend"],
            "activation_available": capability["available"],
            "activation_reason": capability["reason"],
            "needs_reactivation": bool(kwargs.get("needs_reactivation", False)),
            "storage_format": storage_format,
            "server_verified": kwargs.get("server_verified"),
            "verification_warning": kwargs.get("verification_warning", ""),
            "error": kwargs.get("error", ""),
        }

    if not record:
        result = _base_status()
        _store_cached_license_status(cfg, result)
        return result

    local = verify_license_record(record)
    if not local["valid"]:
        result = _base_status(
            error=local["error"],
            needs_reactivation=local.get("needs_reactivation", False),
        )
        _store_cached_license_status(cfg, result)
        return result

    remote = _verify_remote(record.key, record.machine_id) if capability["available"] else {"reachable": False}
    if remote.get("reachable"):
        if not remote.get("ok"):
            result = _base_status(
                error=remote.get("error", "License 校验失败"),
                server_verified=True,
            )
            _store_cached_license_status(cfg, result)
            return result
        days_left = int(remote.get("days_left", 0))
        verification_warning = ""
        server_verified = True
    else:
        days_left = int(local["days_left"])
        verification_warning = remote.get("error", "")
        server_verified = False

    ai_cfg = get_license_ai_config(data_dir)
    result = _base_status(
        active=True,
        days_left=days_left,
        mode="cloud",
        ai_ready=bool(ai_cfg),
        server_verified=server_verified,
        verification_warning=verification_warning,
    )
    _store_cached_license_status(cfg, result)
    return result


@router.get("/status")
def license_status():
    return build_license_status()


@router.post("/activate")
def activate_license(req: LicenseRequest):
    capability = get_activation_capability()
    if not capability["available"]:
        return {"ok": False, "error": capability["reason"]}

    fmt = verify_key_format(req.key)
    if not fmt["valid"]:
        return {"ok": False, "error": fmt["error"]}

    machine_id = get_machine_id()
    norm = req.key.strip().upper().replace("-", "")
    display_key = f"{norm[0:4]}-{norm[4:8]}-{norm[8:12]}-{norm[12:16]}"

    try:
        result = _post_worker("/activate", {"key": display_key, "machine_id": machine_id})
    except Exception as exc:
        return {"ok": False, "error": f"无法连接激活服务器，请检查网络（{exc}）"}

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "激活失败")}

    session_token = str(result.get("session_token", "")).strip()
    if not session_token:
        return {"ok": False, "error": "激活服务器未返回有效会话令牌"}

    try:
        activate_ts = int(result["activate_ts"])
        days = int(result["days"])
    except Exception:
        return {"ok": False, "error": "激活服务器返回了无效的有效期数据"}

    _save_proxy_license(display_key, machine_id, activate_ts, days, session_token)

    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        cfg["backend"] = "deepseek"
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    except Exception:
        pass

    _clear_cached_license_status()
    reset_components()
    return {"ok": True, "days_left": days}


@router.post("/deactivate")
def deactivate_license():
    lf = _license_file()
    if lf.exists():
        lf.unlink()
    _clear_cached_license_status()
    reset_components()
    return {"ok": True}
