"""
License verification helpers for English Coach Cloud Edition.

Key format: XXXX-XXXX-XXXX-XXXX (opaque, registered server-side only)

Current local record format:
  v2|key|machine_id|activate_ts|days|payload_kind|payload_hex|hmac

Security properties:
  - Only server-registered keys can activate.
  - Activation timestamp is issued by the server.
  - The local HMAC covers key, machine, activate_ts, days, payload kind,
    and encrypted payload, so editing any field invalidates the record.
  - The real upstream AI provider key never needs to leave the backend.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from gui import cloud_license_defaults

_FILE_SIGN_KEY = b"ec-file-sign-v2-pB4mQx2Lr9Ns7Kv1"
_LICENSE_RECORD_VERSION = "v2"
_PAYLOAD_KIND_PROXY_TOKEN = "proxy_token"


def _candidate_activation_config_paths() -> list[Path]:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        return [base / "cloud_activation_config.json"]
    root = Path(__file__).resolve().parents[1]
    return [
        root / "cloud_activation_config.json",
        root / "releases" / "cloud_activation_config.json",
    ]


def _load_runtime_activation_config() -> dict:
    for path in _candidate_activation_config_paths():
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            return data
    return {}


_RUNTIME_CFG = _load_runtime_activation_config()

WORKER_URL = os.environ.get(
    "EC_WORKER_URL",
    str(_RUNTIME_CFG.get("worker_url", cloud_license_defaults.WORKER_URL)),
).strip()
WORKER_CLIENT_TOKEN = os.environ.get(
    "EC_WORKER_CLIENT_TOKEN",
    os.environ.get(
        "EC_WORKER_TOKEN",
        str(_RUNTIME_CFG.get("client_token", cloud_license_defaults.CLIENT_TOKEN)),
    ),
).strip()


@dataclass
class LicenseRecord:
    format: str
    key: str = ""
    machine_id: str = ""
    activate_ts: int = 0
    days: int = 0
    payload_kind: str = ""
    payload_hex: str = ""
    sig: str = ""


def get_machine_id() -> str:
    """Return a stable machine identifier."""
    try:
        node = uuid.getnode()
        raw = f"{platform.node()}:{node}:{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]
    except Exception:
        return "unknown"


def verify_key_format(key: str) -> dict:
    """Verify opaque key format only."""
    norm = key.strip().upper().replace("-", "")
    if not re.fullmatch(r"[0-9A-F]{16}", norm):
        return {"valid": False, "days": 0, "error": "Key 格式无效"}
    return {"valid": True, "days": 0, "error": ""}


def get_activation_capability() -> dict:
    """Return whether this build is configured to activate cloud licenses."""
    if WORKER_URL and WORKER_CLIENT_TOKEN:
        return {"available": True, "reason": ""}
    if not WORKER_URL and not WORKER_CLIENT_TOKEN:
        return {
            "available": False,
            "reason": "当前构建未配置激活服务。没有服务器时请直接使用自己的 API key；无 API key 也可使用离线功能。",
        }
    if not WORKER_URL:
        return {"available": False, "reason": "缺少 EC_WORKER_URL，无法连接激活服务。"}
    return {"available": False, "reason": "缺少 EC_WORKER_CLIENT_TOKEN，无法连接激活服务。"}


def _make_hmac_v2(
    key: str,
    machine_id: str,
    activate_ts: int,
    days: int,
    payload_kind: str,
    payload_hex: str,
) -> str:
    msg = (
        f"{_LICENSE_RECORD_VERSION}|{key}|{machine_id}|{activate_ts}|{days}|"
        f"{payload_kind}|{payload_hex}"
    ).encode()
    return hmac.new(_FILE_SIGN_KEY, msg, hashlib.sha256).hexdigest()


def _derive_local_encrypt_key(key: str, machine_id: str) -> str:
    norm = key.strip().upper().replace("-", "")
    seed = f"{norm}:{machine_id}:{_FILE_SIGN_KEY.hex()}"
    return hashlib.sha256(seed.encode()).hexdigest()


def _xor_with_key_hex(data: bytes, key_hex: str) -> bytes:
    key_bytes = bytes.fromhex(key_hex)
    return bytes(data[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(data)))


def encrypt_local_payload(key: str, machine_id: str, payload: str) -> str:
    encrypted = _xor_with_key_hex(payload.encode("utf-8"), _derive_local_encrypt_key(key, machine_id))
    return encrypted.hex()


def decrypt_local_payload(key: str, machine_id: str, encrypted_hex: str) -> str:
    data = bytes.fromhex(encrypted_hex)
    decoded = _xor_with_key_hex(data, _derive_local_encrypt_key(key, machine_id)).decode("utf-8")
    if not decoded:
        raise ValueError("空的 license 载荷")
    return decoded


def make_license_record(
    key: str,
    machine_id: str,
    activate_ts: int,
    days: int,
    payload_kind: str,
    payload_hex: str,
) -> str:
    sig = _make_hmac_v2(key, machine_id, activate_ts, days, payload_kind, payload_hex)
    return (
        f"{_LICENSE_RECORD_VERSION}|{key}|{machine_id}|{activate_ts}|{days}|"
        f"{payload_kind}|{payload_hex}|{sig}"
    )


def parse_license_record(content: str) -> LicenseRecord:
    parts = content.strip().split("|")
    if len(parts) == 8 and parts[0] == _LICENSE_RECORD_VERSION:
        try:
            return LicenseRecord(
                format="v2",
                key=parts[1],
                machine_id=parts[2],
                activate_ts=int(parts[3]),
                days=int(parts[4]),
                payload_kind=parts[5],
                payload_hex=parts[6],
                sig=parts[7],
            )
        except ValueError:
            return LicenseRecord(format="invalid")
    if len(parts) == 6:
        return LicenseRecord(format="legacy_embedded")
    if len(parts) == 5:
        return LicenseRecord(format="legacy_env")
    if len(parts) == 4:
        return LicenseRecord(format="legacy")
    return LicenseRecord(format="invalid")


def verify_license_record(record: LicenseRecord) -> dict:
    """
    Verify a parsed record.

    Returns:
      {"valid": bool, "days_left": int, "error": str, "needs_reactivation": bool}
    """
    if record.format != "v2":
        if record.format.startswith("legacy"):
            return {
                "valid": False,
                "days_left": 0,
                "error": "旧版 License 格式已停用，请重新激活以升级安全记录。",
                "needs_reactivation": True,
            }
        return {"valid": False, "days_left": 0, "error": "License 文件格式无效", "needs_reactivation": False}

    fmt = verify_key_format(record.key)
    if not fmt["valid"]:
        return {"valid": False, "days_left": 0, "error": fmt["error"], "needs_reactivation": False}

    if record.days <= 0:
        return {"valid": False, "days_left": 0, "error": "License 有效期无效", "needs_reactivation": False}

    if record.payload_kind != _PAYLOAD_KIND_PROXY_TOKEN:
        return {"valid": False, "days_left": 0, "error": "License 载荷类型无效", "needs_reactivation": False}

    expected_sig = _make_hmac_v2(
        record.key,
        record.machine_id,
        record.activate_ts,
        record.days,
        record.payload_kind,
        record.payload_hex,
    )
    if not hmac.compare_digest(record.sig, expected_sig):
        return {"valid": False, "days_left": 0, "error": "License 文件已被篡改", "needs_reactivation": False}

    expire_ts = record.activate_ts + record.days * 86400
    remaining = expire_ts - int(time.time())
    if remaining <= 0:
        return {"valid": False, "days_left": 0, "error": "Key 已过期", "needs_reactivation": False}

    return {
        "valid": True,
        "days_left": remaining // 86400,
        "error": "",
        "needs_reactivation": False,
    }


def _license_file_path(data_dir) -> Path:
    return Path(data_dir) / "license.key"


def read_license_record(data_dir) -> LicenseRecord | None:
    try:
        license_file = _license_file_path(data_dir)
        if not license_file.exists():
            return None
        return parse_license_record(license_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _worker_proxy_base_url() -> str:
    if not WORKER_URL:
        return ""
    return f"{WORKER_URL.rstrip('/')}/v1"


def get_license_ai_config(data_dir) -> dict | None:
    """
    Return the local cloud AI config if a valid v2 license record exists.

    The returned api_key is a license-bound worker session token, not the
    upstream provider key.
    """
    record = read_license_record(data_dir)
    if not record:
        return None

    result = verify_license_record(record)
    if not result["valid"]:
        return None

    base_url = _worker_proxy_base_url()
    if not base_url:
        return None

    try:
        token = decrypt_local_payload(record.key, record.machine_id, record.payload_hex)
    except Exception:
        return None

    return {
        "mode": "proxy_token",
        "api_key": token,
        "base_url": base_url,
        "days_left": result["days_left"],
    }


def get_license_api_key(data_dir) -> str:
    """
    Legacy compatibility wrapper.

    The cloud version no longer returns the upstream provider key to clients,
    so this function intentionally returns an empty string for v2 licenses.
    """
    _ = data_dir
    return ""


def decode_session_token_preview(token: str) -> dict:
    """
    Best-effort decode of the signed worker session token payload for debugging.
    Does not verify the signature.
    """
    try:
        body, _, _sig = token.partition(".")
        if not body:
            return {}
        padded = body + "=" * (-len(body) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        data = json.loads(decoded)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
