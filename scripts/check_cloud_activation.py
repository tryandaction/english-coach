#!/usr/bin/env python3
"""
Check the full Cloud activation loop without launching the GUI.

Verifies:
1. seller register
2. buyer activate
3. buyer verify
4. cloud AI proxy
5. seller inspect
6. seller revoke

Required configuration:
- EC_LICENSE_ADMIN_URL
- EC_LICENSE_ADMIN_TOKEN
- EC_WORKER_URL
- EC_WORKER_CLIENT_TOKEN

If env vars are missing, the script falls back to:
- private_commercial/seller_cloud_config.json
- private_commercial/cloud_activation_config.json
- legacy root config files
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.private_paths import cloud_activation_config_candidates, display_path, seller_config_candidates


def _load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Invalid {label} at {display_path(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid {label} at {display_path(path)}: expected JSON object")
    return payload


def _first_config(candidates: list[Path], label: str) -> tuple[dict, str]:
    for path in candidates:
        if path.exists():
            return _load_json(path, label), display_path(path)
    return {}, ""


def _required(name: str, config_value: str = "", source_label: str = "") -> str:
    value = os.environ.get(name, "").strip() or str(config_value or "").strip()
    if not value:
        if source_label:
            raise SystemExit(f"Missing required value: {name} (checked env and {source_label})")
        raise SystemExit(f"Missing required env: {name}")
    return value


def _post(url: str, token: str, path: str, body: dict) -> dict:
    payload = json.dumps(body).encode("utf-8")
    target = f"{url.rstrip('/')}{path}"
    host = urlparse(target).hostname or "unknown-host"
    base = f"{urlparse(target).scheme}://{host}"
    req = urllib.request.Request(
        target,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Worker-Token": token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Origin": base,
            "Referer": f"{base}/",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"{path} failed: HTTP {exc.code} {text}")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise SystemExit(f"{path} failed: network error while reaching {host}: {reason}")
    except TimeoutError:
        raise SystemExit(f"{path} failed: timeout while reaching {host}")


def _post_bearer(url: str, bearer_token: str, path: str, body: dict) -> dict:
    payload = json.dumps(body).encode("utf-8")
    target = f"{url.rstrip('/')}{path}"
    host = urlparse(target).hostname or "unknown-host"
    base = f"{urlparse(target).scheme}://{host}"
    req = urllib.request.Request(
        target,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Origin": base,
            "Referer": f"{base}/",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"{path} failed: HTTP {exc.code} {text}")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise SystemExit(f"{path} failed: network error while reaching {host}: {reason}")
    except TimeoutError:
        raise SystemExit(f"{path} failed: timeout while reaching {host}")


def main() -> int:
    seller_cfg, seller_source = _first_config(seller_config_candidates(), "seller_cloud_config.json")
    activation_cfg, activation_source = _first_config(
        cloud_activation_config_candidates(),
        "cloud_activation_config.json",
    )

    admin_url = _required("EC_LICENSE_ADMIN_URL", str(seller_cfg.get("admin_url", "")), seller_source)
    admin_token = _required("EC_LICENSE_ADMIN_TOKEN", str(seller_cfg.get("admin_token", "")), seller_source)
    worker_url = _required("EC_WORKER_URL", str(activation_cfg.get("worker_url", "")), activation_source)
    client_token = _required(
        "EC_WORKER_CLIENT_TOKEN",
        str(activation_cfg.get("client_token", "")),
        activation_source,
    )

    raw = secrets.token_hex(8).upper()
    key = f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"
    machine_id = "cloud-check-machine"

    print("== Cloud activation loop check ==")
    print(f"register key: {key}")

    register = _post(admin_url, admin_token, "/register", {"key": key, "days": 7})
    if not register.get("ok"):
        raise SystemExit(f"register rejected: {register}")
    print(f"register ok: serial={register.get('serial')}")

    activate = _post(worker_url, client_token, "/activate", {"key": key, "machine_id": machine_id})
    if not activate.get("ok"):
        raise SystemExit(f"activate rejected: {activate}")
    print(f"activate ok: days={activate.get('days')}")
    session_token = str(activate.get("session_token", "")).strip()
    if not session_token:
        raise SystemExit(f"activate missing session_token: {activate}")

    verify = _post(worker_url, client_token, "/verify", {"key": key, "machine_id": machine_id})
    if not verify.get("ok"):
        raise SystemExit(f"verify rejected: {verify}")
    print(f"verify ok: days_left={verify.get('days_left')}")

    proxy = _post_bearer(
        worker_url,
        session_token,
        "/v1/chat/completions",
        {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "Reply with exactly OK"}],
            "max_tokens": 8,
        },
    )
    choice = (((proxy.get("choices") or [{}])[0]).get("message") or {}).get("content", "").strip()
    if not choice:
        raise SystemExit(f"proxy rejected or empty response: {proxy}")
    print(f"proxy ok: sample_reply={choice[:40]}")

    inspect = _post(admin_url, admin_token, "/inspect", {"key": key})
    if not inspect.get("ok"):
        raise SystemExit(f"inspect rejected: {inspect}")
    if not inspect.get("record", {}).get("activated"):
        raise SystemExit(f"inspect shows non-activated record: {inspect}")
    print(
        "inspect ok: "
        f"requests={inspect.get('usage_today', {}).get('requests', 0)} "
        f"blocked={inspect.get('usage_today', {}).get('blocked', 0)}"
    )

    revoke = _post(admin_url, admin_token, "/revoke", {"key": key})
    if not revoke.get("ok"):
        raise SystemExit(f"revoke rejected: {revoke}")
    print("revoke ok")
    print("Cloud activation + proxy + inspect loop is healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
