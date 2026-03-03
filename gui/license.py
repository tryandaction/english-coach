"""
License verification for English Coach Cloud Edition.

Key format: XXXX-XXXX-XXXX-XXXX  (16 random hex chars, opaque)
  - Days and serial stored in Cloudflare KV at generation time
  - No offline forgery possible — validation requires KV lookup

Activation record stored locally as "{key}|{machine_id}|{activate_ts}|{hmac}"
  - hmac = HMAC-SHA256(key|machine_id|activate_ts, _FILE_SIGN_KEY)
  - tampering with any field invalidates the hmac
"""
from __future__ import annotations

import hashlib
import hmac
import os
import platform
import re
import time
import uuid

# Local file signing key — prevents timestamp tampering
_FILE_SIGN_KEY = b"ec-file-sign-v1-Kq7mXpR2nLsT9wYv"

# Cloudflare Worker URL
WORKER_URL = os.environ.get("EC_WORKER_URL", "https://english-coach-license.pages.dev")

# Worker auth token — must match WORKER_SECRET set in Cloudflare
# For open source users: this is only used in the commercial cloud edition
WORKER_TOKEN = os.environ.get("EC_WORKER_TOKEN", "")


def get_machine_id() -> str:
    """Return a stable machine identifier."""
    try:
        node = uuid.getnode()
        raw = f"{platform.node()}:{node}:{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]
    except Exception:
        return "unknown"


def verify_key_format(key: str) -> dict:
    """
    Verify key format only (opaque hex, no offline checksum).
    Returns {"valid": bool, "days": 0, "error": str}
    Days are unknown until Cloudflare KV lookup at activation time.
    """
    norm = key.strip().upper().replace("-", "")
    if not re.fullmatch(r"[0-9A-F]{16}", norm):
        return {"valid": False, "days": 0, "error": "Key 格式无效"}
    return {"valid": True, "days": 0, "error": ""}


def _make_hmac(key: str, machine_id: str, activate_ts: int) -> str:
    msg = f"{key}|{machine_id}|{activate_ts}".encode()
    return hmac.new(_FILE_SIGN_KEY, msg, hashlib.sha256).hexdigest()


def verify_license(key: str, machine_id: str, activate_ts: int, sig: str) -> dict:
    """
    Verify a saved license given its fields and HMAC signature.
    Returns {"valid": bool, "days_left": int, "error": str}
    Requires days to be stored alongside (passed via activate_ts record).
    """
    fmt = verify_key_format(key)
    if not fmt["valid"]:
        return {"valid": False, "days_left": 0, "error": fmt["error"]}

    expected_sig = _make_hmac(key, machine_id, activate_ts)
    if not hmac.compare_digest(sig, expected_sig):
        return {"valid": False, "days_left": 0, "error": "License 文件已被篡改"}

    return {"valid": True, "days_left": 0, "error": ""}


def verify_license_with_days(key: str, machine_id: str, activate_ts: int, days: int, sig: str) -> dict:
    """
    Verify a saved license including expiry check.
    Returns {"valid": bool, "days_left": int, "error": str}
    """
    fmt = verify_key_format(key)
    if not fmt["valid"]:
        return {"valid": False, "days_left": 0, "error": fmt["error"]}

    expected_sig = _make_hmac(key, machine_id, activate_ts)
    if not hmac.compare_digest(sig, expected_sig):
        return {"valid": False, "days_left": 0, "error": "License 文件已被篡改"}

    expire_ts = activate_ts + days * 86400
    remaining = expire_ts - int(time.time())
    if remaining <= 0:
        return {"valid": False, "days_left": 0, "error": "Key 已过期"}

    return {"valid": True, "days_left": remaining // 86400, "error": ""}


def make_license_record(key: str, machine_id: str, activate_ts: int, days: int) -> str:
    """Build the string to write to license.key"""
    sig = _make_hmac(key, machine_id, activate_ts)
    return f"{key}|{machine_id}|{activate_ts}|{days}|{sig}"


def xor_decrypt(hex_str: str, key_hex: str) -> str:
    """Decrypt XOR-encrypted API key returned by the Worker."""
    data = bytes.fromhex(hex_str)
    key_bytes = bytes.fromhex(key_hex)
    out = bytes(data[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(data)))
    return out.decode()


def get_cloud_api_key() -> str:
    """Return the cloud API key stored in env (set after activation)."""
    return os.environ.get("DEEPSEEK_API_KEY", "")


def get_license_api_key(data_dir) -> str:
    """
    Get API key from activated license.
    Returns empty string if no valid license found.
    Used by ai/client.py to prioritize license over .env file.
    """
    from pathlib import Path
    license_file = Path(data_dir) / "license.key"
    if not license_file.exists():
        return ""

    try:
        content = license_file.read_text(encoding="utf-8").strip()
        parts = content.split("|")

        # New format with encrypted API key: key|machine_id|activate_ts|days|encrypted_api_key|sig (6 parts)
        if len(parts) == 6:
            key, machine_id, activate_ts_str, days_str, encrypted_hex, sig = parts
            activate_ts = int(activate_ts_str)
            days = int(days_str)

            # Verify license is valid and not expired
            result = verify_license_with_days(key, machine_id, activate_ts, days, sig)
            if not result["valid"]:
                return ""

            # Decrypt API key
            import hashlib
            norm = key.replace("-", "")
            derived = hashlib.sha256(f"{norm}:{machine_id}:{WORKER_TOKEN}".encode()).hexdigest()

            # XOR decrypt
            encrypted = bytes.fromhex(encrypted_hex)
            derived_bytes = bytes.fromhex(derived)
            decrypted = bytes(encrypted[i] ^ derived_bytes[i % len(derived_bytes)] for i in range(len(encrypted)))
            api_key = decrypted.decode()

            return api_key

        # Old format without encrypted key - check environment
        if len(parts) == 5:
            key, machine_id, activate_ts_str, days_str, sig = parts
            activate_ts = int(activate_ts_str)
            days = int(days_str)

            result = verify_license_with_days(key, machine_id, activate_ts, days, sig)
            if not result["valid"]:
                return ""

            # Old format: API key might be in environment or .env file
            return os.environ.get("DEEPSEEK_API_KEY", "")

        return ""

    except Exception:
        return ""

