"""License API — verify and activate cloud license keys."""
from __future__ import annotations

import os
import time
from pathlib import Path

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from gui.license import (
    verify_key_format,
    verify_license_with_days,
    make_license_record,
    get_machine_id,
    xor_decrypt,
    WORKER_URL,
    WORKER_TOKEN,
)
from gui.deps import load_config, _CONFIG_PATH

router = APIRouter(prefix="/api/license", tags=["license"])


def _license_file() -> Path:
    cfg = load_config()
    raw = cfg.get("data_dir", "data")
    p = Path(raw)
    data_dir = p if p.is_absolute() else _CONFIG_PATH.parent / raw
    return data_dir / "license.key"


def load_saved_license() -> tuple[str, str, int, int, str]:
    """Returns (key, machine_id, activate_ts, days, sig) or ('','',0,0,'')."""
    lf = _license_file()
    if not lf.exists():
        return "", "", 0, 0, ""
    content = lf.read_text(encoding="utf-8").strip()
    parts = content.split("|")
    # New format: key|machine_id|activate_ts|days|sig (5 parts)
    if len(parts) == 5:
        try:
            return parts[0], parts[1], int(parts[2]), int(parts[3]), parts[4]
        except ValueError:
            pass
    # Legacy 4-part format: key|machine_id|activate_ts|sig
    if len(parts) == 4:
        try:
            return parts[0], parts[1], int(parts[2]), 0, parts[3]
        except ValueError:
            pass
    return "", "", 0, 0, ""


def save_license(key: str, machine_id: str, activate_ts: int, days: int) -> None:
    lf = _license_file()
    lf.parent.mkdir(parents=True, exist_ok=True)
    record = make_license_record(key, machine_id, activate_ts, days)
    lf.write_text(record, encoding="utf-8")


class LicenseRequest(BaseModel):
    key: str


@router.get("/status")
def license_status():
    key, machine_id, activate_ts, days, sig = load_saved_license()
    if not key:
        return {"active": False, "days_left": 0, "mode": "self_key"}
    if days == 0:
        # Legacy record without days — treat as expired
        return {"active": False, "days_left": 0, "mode": "self_key", "error": "请重新激活以更新 License 格式"}
    result = verify_license_with_days(key, machine_id, activate_ts, days, sig)
    if result["valid"]:
        return {"active": True, "days_left": result["days_left"], "mode": "cloud"}
    return {"active": False, "days_left": 0, "mode": "self_key", "error": result["error"]}


@router.post("/activate")
def activate_license(req: LicenseRequest):
    # 1. Validate key format locally (fast fail)
    fmt = verify_key_format(req.key)
    if not fmt["valid"]:
        return {"ok": False, "error": fmt["error"]}

    machine_id = get_machine_id()

    # 2. Call Cloudflare Worker to activate
    try:
        import urllib.request
        import json as _json

        # Normalize key to XXXX-XXXX-XXXX-XXXX format for display
        norm = req.key.strip().upper().replace("-", "")
        display_key = f"{norm[0:4]}-{norm[4:8]}-{norm[8:12]}-{norm[12:16]}"

        payload = _json.dumps({"key": display_key, "machine_id": machine_id}).encode()
        worker_req = urllib.request.Request(
            f"{WORKER_URL}/activate",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Worker-Token": WORKER_TOKEN,
                "User-Agent": "EnglishCoach/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(worker_req, timeout=10) as resp:
            result = _json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "error": f"无法连接激活服务器，请检查网络（{e}）"}

    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "激活失败")}

    # 3. Decrypt the cloud API key
    try:
        import hashlib
        derived = hashlib.sha256(
            f"{norm}:{machine_id}:{WORKER_TOKEN}".encode()
        ).hexdigest()
        cloud_api_key = xor_decrypt(result["encrypted_key"], derived)
    except Exception as e:
        return {"ok": False, "error": f"解密 API Key 失败（{e}）"}

    # 4. Save license file with days
    activate_ts = result["activate_ts"]
    days = result["days"]
    save_license(display_key, machine_id, activate_ts, days)

    # 5. Write cloud API key to .env next to config.yaml
    env_file = _CONFIG_PATH.parent / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    lines = [l for l in lines if not l.startswith("DEEPSEEK_API_KEY=")]
    lines.append(f"DEEPSEEK_API_KEY={cloud_api_key}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["DEEPSEEK_API_KEY"] = cloud_api_key

    # 6. Update config to use deepseek backend
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        cfg["backend"] = "deepseek"
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    except Exception:
        pass

    from gui.deps import reset_components
    reset_components()

    return {"ok": True, "days_left": days}


@router.post("/deactivate")
def deactivate_license():
    lf = _license_file()
    if lf.exists():
        lf.unlink()
    return {"ok": True}
