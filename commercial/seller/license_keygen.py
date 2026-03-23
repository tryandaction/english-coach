#!/usr/bin/env python3
"""
License Key Generator — English Coach Cloud Edition

Key format: XXXX-XXXX-XXXX-XXXX  (16 random hex chars, grouped for readability)
  - Fully opaque — no days/serial visible in the key
  - Days and serial stored in Cloudflare KV at generation time
  - Verification: Cloudflare KV lookup only (no offline forgery possible)

Usage:
  python license_keygen.py --days 30
  python license_keygen.py --days 365 --note "Zhang Wei wechat order"
  python license_keygen.py --list
  python license_keygen.py --inspect XXXX-XXXX-XXXX-XXXX
  python license_keygen.py --revoke XXXX-XXXX-XXXX-XXXX

Seller config resolution priority:
  1. EC_LICENSE_ADMIN_URL + EC_LICENSE_ADMIN_TOKEN
  2. private_commercial/seller_cloud_config.json
  3. seller_cloud_config.json
"""

import argparse
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from commercial.seller import seller_cloud_defaults
from utils.private_paths import display_path, preferred_key_log_path, seller_config_candidates

_CONFIG_CANDIDATES = seller_config_candidates()
_EXAMPLE_CONFIG = ROOT / "commercial" / "examples" / "seller_cloud_config.example.json"
_WORKER_WRANGLER = ROOT / "commercial" / "deploy" / "pages" / "wrangler.toml"
_KV_BINDING = "LICENSE_KV"

_LOG_FILE = preferred_key_log_path()
_PLAN_OPTIONS = {
    "1": {"days": 30, "label": "首次激活 30天", "note": "首购30天", "renewal": False},
    "2": {"days": 365, "label": "首次激活 365天", "note": "首购365天", "renewal": False},
    "3": {"days": 30, "label": "赠送 30天", "note": "赠送30天", "renewal": False},
    "4": {"days": 30, "label": "续期 30天", "note": "续费30天", "renewal": True},
    "5": {"days": 90, "label": "续期 90天", "note": "续费90天", "renewal": True},
    "6": {"days": 365, "label": "续期 365天", "note": "续费365天", "renewal": True},
}


def get_plan_options() -> dict[str, dict]:
    return {key: dict(value) for key, value in _PLAN_OPTIONS.items()}


def _load_json_from_candidates(paths: list[Path], label: str) -> dict:
    for path in paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"ERROR: invalid {label} at {display_path(path)}: {exc}")
            sys.exit(1)
        if isinstance(payload, dict):
            return payload
        print(f"ERROR: invalid {label} at {display_path(path)}: expected JSON object")
        sys.exit(1)
    return {}


def _load_seller_config() -> tuple[str, str]:
    cfg = _load_json_from_candidates(_CONFIG_CANDIDATES, "seller_cloud_config.json")

    admin_url = os.environ.get("EC_LICENSE_ADMIN_URL", cfg.get("admin_url", seller_cloud_defaults.ADMIN_URL)).strip()
    admin_token = os.environ.get("EC_LICENSE_ADMIN_TOKEN", cfg.get("admin_token", seller_cloud_defaults.ADMIN_TOKEN)).strip()

    if not admin_url or not admin_token:
        print("ERROR: seller admin configuration is missing.")
        print("Set EC_LICENSE_ADMIN_URL and EC_LICENSE_ADMIN_TOKEN,")
        print(
            "or create a local config based on "
            f"{_EXAMPLE_CONFIG.name} at private_commercial/seller_cloud_config.json."
        )
        sys.exit(1)

    return admin_url, admin_token


def _seller_mode() -> str:
    cfg = _load_json_from_candidates(_CONFIG_CANDIDATES, "seller_cloud_config.json")
    return str(os.environ.get("EC_LICENSE_ADMIN_MODE", cfg.get("admin_mode", "http"))).strip().lower() or "http"


def _run_wrangler_kv(args: list[str]) -> str:
    if not _WORKER_WRANGLER.exists():
        raise RuntimeError(f"Missing Wrangler config: {_WORKER_WRANGLER}")
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [
        npx_cmd, "wrangler", "kv", "key", *args,
        "--binding", _KV_BINDING,
        "--remote",
        "--config", str(_WORKER_WRANGLER),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(_WORKER_WRANGLER.parent),
        capture_output=True,
        timeout=60,
    )
    stdout = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        detail = stderr or stdout or "unknown wrangler error"
        raise RuntimeError(detail)
    return stdout


def _kv_get_text(key: str) -> str:
    try:
        return _run_wrangler_kv(["get", key, "--text"])
    except RuntimeError as exc:
        if "404: Not Found" in str(exc):
            return ""
        raise


def _kv_direct_request(path: str, body: dict) -> dict:
    if path not in {"/register", "/revoke", "/inspect"}:
        raise RuntimeError(f"KV direct mode does not support path: {path}")

    if path == "/register":
        key = str(body.get("key", "")).strip().upper()
        days = int(body.get("days", 0))
        if not key or days <= 0:
            return {"ok": False, "error": "Missing key or days"}

        existing = _kv_get_text(key)
        if existing:
            return {"ok": False, "error": "Key already registered"}

        counter_raw = _kv_get_text("__serial__")
        serial = int(counter_raw or "0") + 1
        record = {
            "days": days,
            "serial": serial,
            "activated": False,
            "machine_id": None,
            "activate_ts": None,
        }
        _run_wrangler_kv(["put", "__serial__", str(serial)])
        _run_wrangler_kv(["put", key, json.dumps(record, ensure_ascii=False)])
        return {"ok": True, "serial": serial}

    key = str(body.get("key", "")).strip().upper()
    if not key:
        return {"ok": False, "error": "Missing key"}

    if path == "/inspect":
        raw = _kv_get_text(key)
        if not raw:
            return {"ok": False, "error": "Key not found"}
        try:
            record = json.loads(raw)
        except Exception:
            return {"ok": False, "error": "Corrupted key record"}
        today = datetime.utcnow().strftime("%Y-%m-%d")
        usage_raw = _kv_get_text(f"usage:{key.replace('-', '')}:{today}")
        usage = {}
        if usage_raw:
            try:
                usage = json.loads(usage_raw)
            except Exception:
                usage = {}
        return {"ok": True, "key": key, "record": record, "usage_today": usage}

    _run_wrangler_kv(["delete", key])
    return {"ok": True}


def _worker_post(path: str, body: dict) -> dict:
    if _seller_mode() == "kv_direct":
        return _kv_direct_request(path, body)

    admin_url, admin_token = _load_seller_config()
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{admin_url}{path}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Worker-Token": admin_token,
            "User-Agent": "EnglishCoach-Keygen/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as exc:
        if path in {"/register", "/revoke", "/inspect"}:
            print(f"WARN: HTTP seller endpoint unreachable ({exc}); falling back to direct Cloudflare KV mode.")
            return _kv_direct_request(path, body)
        raise


def _format_key(raw_hex: str) -> str:
    """Format 16 hex chars as XXXX-XXXX-XXXX-XXXX."""
    h = raw_hex.upper()
    return f"{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


def choose_plan_interactive() -> dict:
    print("=" * 50)
    print("  英语教练 — License Key 生成器")
    print("=" * 50)
    print()
    print("选择套餐：")
    print("  --- 首次激活 / 含可执行版 ---")
    for key in ("1", "2", "3"):
        item = _PLAN_OPTIONS[key]
        print(f"  {key}. {item['label']}")
    print("  --- 已有可执行版 / 续期 ---")
    for key in ("4", "5", "6"):
        item = _PLAN_OPTIONS[key]
        print(f"  {key}. {item['label']}")
    print("  7. 自定义天数")
    print()

    choice = input("输入数字 [1-7]：").strip()
    if choice in _PLAN_OPTIONS:
        return dict(_PLAN_OPTIONS[choice])
    if choice == "7":
        raw_days = input("输入可激活天数：").strip()
        try:
            days = int(raw_days)
        except ValueError:
            raise SystemExit("无效天数，退出。")
        if days <= 0:
            raise SystemExit("天数必须大于 0，退出。")
        note = input("备注（可留空）：").strip()
        return {
            "days": days,
            "label": f"自定义 {days}天",
            "note": note,
            "renewal": False,
        }
    raise SystemExit("无效选择，退出。")


def generate_key(days: int, note: str = "") -> str:
    raw = secrets.token_hex(8)  # 16 hex chars
    key = _format_key(raw)

    # Register in Cloudflare KV
    result = _worker_post("/register", {"key": key, "days": days})
    if not result.get("ok"):
        print(f"ERROR: Worker rejected key registration: {result.get('error')}")
        sys.exit(1)

    serial = result.get("serial", 0)

    # Append to local log
    entry = {
        "key": key, "days": days, "serial": serial,
        "note": note, "created": datetime.now().isoformat()
    }
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if note:
        print(f"Note   : {note}")
    print(f"Key    : {key}")
    print(f"Serial : #{serial}")
    print(f"Valid  : {days} days from activation")
    return key


def revoke_key(key: str):
    result = _worker_post("/revoke", {"key": key})
    if result.get("ok"):
        print(f"Revoked: {key}")
    else:
        print(f"Error: {result.get('error')}")


def inspect_key(key: str):
    result = _worker_post("/inspect", {"key": key})
    if not result.get("ok"):
        print(f"Error: {result.get('error')}")
        return

    record = result.get("record", {})
    usage = result.get("usage_today", {})
    print(f"Key       : {result.get('key', key)}")
    print(f"Serial    : #{record.get('serial', '?')}")
    print(f"Days      : {record.get('days', '?')}")
    print(f"Activated : {record.get('activated', False)}")
    print(f"Machine   : {record.get('machine_id') or '-'}")
    print(f"ActivateTS: {record.get('activate_ts') or '-'}")
    if "days_left" in record:
        print(f"Days Left : {record.get('days_left')}")
    print("Usage Today:")
    print(f"  requests      : {usage.get('requests', 0)}")
    print(f"  input_chars   : {usage.get('input_chars', 0)}")
    print(f"  output_tokens : {usage.get('output_tokens', 0)}")
    print(f"  blocked       : {usage.get('blocked', 0)}")
    if usage.get("last_block_reason"):
        print(f"  last_block    : {usage.get('last_block_reason')}")


def list_keys():
    if not _LOG_FILE.exists():
        print("No keys generated yet.")
        return
    print(f"{'#':<6} {'Key':<22} {'Days':<6} {'Created':<20} Note")
    print("-" * 75)
    for line in _LOG_FILE.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
            print(f"#{e.get('serial','?'):<5} {e['key']:<22} {e['days']:<6} {e['created'][:19]:<20} {e.get('note','')}")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="English Coach License Key Tool")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--note", type=str, default="")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--inspect", type=str, default="")
    parser.add_argument("--revoke", type=str, default="")
    args = parser.parse_args()

    if args.list:
        list_keys()
    elif args.inspect:
        inspect_key(args.inspect)
    elif args.revoke:
        revoke_key(args.revoke)
    else:
        if args.days is not None:
            generate_key(args.days, args.note)
            return
        if not sys.stdin.isatty():
            raise SystemExit("非交互模式下请显式传入 --days。")
        choice = choose_plan_interactive()
        note = args.note or choice.get("note", "")
        print(f"\n正在生成 Key 并注册到服务器... [{choice['label']}]")
        generate_key(int(choice["days"]), note)


if __name__ == "__main__":
    main()
