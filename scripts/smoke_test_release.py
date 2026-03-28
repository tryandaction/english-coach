#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import winreg
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.private_paths import cloud_activation_config_candidates, display_path, seller_config_candidates

RELEASES = ROOT / "releases"
DEFAULT_PORTABLE_EXE = RELEASES / "english-coach-opensource.exe"
DEFAULT_INSTALLER_EXE = RELEASES / "english-coach-opensource-setup.exe"
DEFAULT_PORTABLE_CLOUD_EXE = RELEASES / "english-coach-cloud.exe"
DEFAULT_INSTALLER_CLOUD_EXE = RELEASES / "english-coach-cloud-setup.exe"
PAGE_MODULES = [
    "home",
    "progress",
    "history",
    "practice",
    "mock-exam",
]
_UNINSTALL_REGISTRY_SUBKEYS = {
    "opensource": [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}_is1"),
    ],
    "cloud": [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{B2C3D4E5-F6A7-8901-BCDE-F12345678901}_is1"),
    ],
}
_SANITIZED_ENV_KEYS = [
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DASHSCOPE_API_KEY",
    "EC_WORKER_URL",
    "EC_WORKER_CLIENT_TOKEN",
    "EC_WORKER_TOKEN",
    "EC_LICENSE_ADMIN_URL",
    "EC_LICENSE_ADMIN_TOKEN",
]

_SMOKE_PATH_MARKER = "english_coach_release_smoke_"


def _worker_headers(token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Worker-Token": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }


def log(message: str) -> None:
    print(f"[release-smoke] {message}", flush=True)


def request_json(url: str, method: str = "GET", body: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def request_text(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def request_json_with_retry(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: int = 25,
    attempts: int = 4,
    sleep_sec: int = 5,
) -> Any:
    errors: list[str] = []
    for attempt in range(attempts):
        if attempt:
            time.sleep(sleep_sec)
        try:
            return request_json(url, method=method, body=body, timeout=timeout)
        except Exception as exc:
            errors.append(str(exc))
    raise TimeoutError(f"{url} 超时: {' | '.join(errors)}")


def request_worker_json(url: str, token: str, body: dict[str, Any], timeout: int = 30) -> Any:
    base = url.rstrip("/")
    target = base
    origin = base
    headers = {
        **_worker_headers(token),
        "Origin": origin,
        "Referer": f"{origin}/",
    }
    req = urllib.request.Request(
        target,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"{label} 无法解析: {display_path(path)} ({exc})") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} 格式无效: {display_path(path)}")
    return payload


def _load_seller_admin_credentials() -> tuple[str, str]:
    admin_url = str(os.environ.get("EC_LICENSE_ADMIN_URL", "") or "").strip()
    admin_token = str(os.environ.get("EC_LICENSE_ADMIN_TOKEN", "") or "").strip()
    if admin_url and admin_token:
        return admin_url, admin_token

    worker_url = ""
    for candidate in cloud_activation_config_candidates():
        if not candidate.exists():
            continue
        cfg = _load_json(candidate, "cloud_activation_config.json")
        worker_url = str(cfg.get("worker_url", "") or "").strip()
        if worker_url:
            break

    for candidate in seller_config_candidates():
        if not candidate.exists():
            continue
        cfg = _load_json(candidate, "seller_cloud_config.json")
        admin_url = str(cfg.get("admin_url", "") or "").strip() or worker_url
        admin_token = str(cfg.get("admin_token", "") or "").strip()
        if admin_url and admin_token:
            return admin_url, admin_token
    return "", ""


def wait_for_probe(process: subprocess.Popen[Any], probe_path: Path, timeout_sec: int, label: str) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if probe_path.exists():
            payload = json.loads(probe_path.read_text(encoding="utf-8"))
            if payload.get("status") == "ready":
                return payload
            raise RuntimeError(f"{label} 启动失败: {payload}")
        if process.poll() is not None:
            raise RuntimeError(f"{label} 进程提前退出，exit={process.returncode}")
        time.sleep(0.5)
    raise TimeoutError(f"{label} 启动超时，未生成 probe 文件: {probe_path}")


def stop_process(process: subprocess.Popen[Any], label: str) -> None:
    stop_process_by_pid(process, label, actual_pid=None)


def stop_process_by_pid(
    process: subprocess.Popen[Any],
    label: str,
    actual_pid: int | None,
) -> None:
    seen: set[int] = set()
    pids = [pid for pid in [actual_pid, process.pid] if isinstance(pid, int) and pid > 0]
    if not pids:
        return
    log(f"停止 {label} 进程")
    for pid in pids:
        if pid in seen:
            continue
        seen.add(pid)
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if process.poll() is None:
        try:
            process.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def cleanup_installed_app(install_dir: Path) -> None:
    uninstaller = install_dir / "unins000.exe"
    if not uninstaller.exists():
        return
    log(f"卸载 smoke 安装目录: {install_dir}")
    subprocess.run(
        [
            str(uninstaller),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
        ],
        check=False,
        cwd=str(install_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _backup_registry_entry(hive, subkey: str) -> dict[str, tuple[object, int]] | None:
    try:
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            values: dict[str, tuple[object, int]] = {}
            index = 0
            while True:
                try:
                    name, value, reg_type = winreg.EnumValue(key, index)
                    values[name] = (value, reg_type)
                    index += 1
                except OSError:
                    break
            return values
    except FileNotFoundError:
        return None


def _restore_registry_entry(hive, subkey: str, snapshot: dict[str, tuple[object, int]] | None) -> None:
    if snapshot is None:
        try:
            winreg.DeleteKey(hive, subkey)
        except OSError:
            pass
        return
    key = winreg.CreateKeyEx(hive, subkey, 0, winreg.KEY_WRITE)
    try:
        for name, (value, reg_type) in snapshot.items():
            winreg.SetValueEx(key, name, 0, reg_type, value)
    finally:
        winreg.CloseKey(key)


def backup_uninstall_registry(mode: str) -> list[tuple[int, str, dict[str, tuple[object, int]] | None]]:
    snapshots = []
    for hive, subkey in _UNINSTALL_REGISTRY_SUBKEYS.get(mode, []):
        snapshots.append((hive, subkey, _backup_registry_entry(hive, subkey)))
    return snapshots


def restore_uninstall_registry(snapshots: list[tuple[int, str, dict[str, tuple[object, int]] | None]]) -> None:
    for hive, subkey, snapshot in snapshots:
        _restore_registry_entry(hive, subkey, snapshot)


def cleanup_stale_smoke_uninstall_entries() -> None:
    hives = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, subkey in hives:
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as root:
                index = 0
                names: list[str] = []
                while True:
                    try:
                        names.append(winreg.EnumKey(root, index))
                        index += 1
                    except OSError:
                        break
                for name in names:
                    try:
                        with winreg.OpenKey(root, name, 0, winreg.KEY_READ) as item:
                            display_name = str(winreg.QueryValueEx(item, "DisplayName")[0])
                            install_location = str(winreg.QueryValueEx(item, "InstallLocation")[0]) if _has_reg_value(item, "InstallLocation") else ""
                            uninstall_string = str(winreg.QueryValueEx(item, "UninstallString")[0]) if _has_reg_value(item, "UninstallString") else ""
                        lowered = f"{install_location}\n{uninstall_string}".lower()
                        if display_name.startswith("English Coach") and _SMOKE_PATH_MARKER in lowered:
                            winreg.DeleteKey(root, name)
                    except FileNotFoundError:
                        continue
                    except OSError:
                        continue
        except OSError:
            continue


def _has_reg_value(key, value_name: str) -> bool:
    try:
        winreg.QueryValueEx(key, value_name)
        return True
    except OSError:
        return False


def _query_registry_string(hive, subkey: str, value_name: str) -> str:
    try:
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            return str(winreg.QueryValueEx(key, value_name)[0])
    except OSError:
        return ""


def _mode_shortcut_paths(mode: str) -> list[Path]:
    appdata = Path(os.environ["APPDATA"])
    desktop = Path(
        subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$ws = New-Object -ComObject WScript.Shell; $ws.SpecialFolders('Desktop')",
            ],
            text=True,
        ).strip()
    )
    if mode == "cloud":
        return [
            appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "English Coach Cloud",
            desktop / "English Coach.lnk",
        ]
    if mode == "opensource":
        return [
            appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "English Coach Open Source",
            desktop / "English Coach.lnk",
        ]
    return []


def _app_shortcut_links(mode: str) -> list[Path]:
    paths = _mode_shortcut_paths(mode)
    if not paths:
        return []
    start_menu_dir = paths[0]
    desktop_link = paths[1] if len(paths) > 1 else None
    links = [start_menu_dir / "English Coach.lnk"]
    if desktop_link is not None:
        links.append(desktop_link)
    return links


def _read_shortcut_target(path: Path) -> Path:
    escaped = str(path).replace("'", "''")
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $shell.CreateShortcut('{escaped}'); "
        "[Console]::WriteLine($shortcut.TargetPath)"
    )
    target = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", script],
        text=True,
    ).strip()
    return Path(target)


def _copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def preserve_existing_install(mode: str, temp_root: Path) -> dict[str, Any] | None:
    for hive, subkey in _UNINSTALL_REGISTRY_SUBKEYS.get(mode, []):
        install_location = _query_registry_string(hive, subkey, "InstallLocation").strip()
        if not install_location:
            continue
        lowered = install_location.lower()
        if _SMOKE_PATH_MARKER in lowered:
            continue
        install_dir = Path(install_location)
        if not install_dir.exists():
            continue

        backup_root = temp_root / f"preserved-{mode}-install"
        install_backup = backup_root / "install"
        shortcuts: list[dict[str, str]] = []
        _copy_path(install_dir, install_backup)
        for src in _mode_shortcut_paths(mode):
            if not src.exists():
                continue
            dst = backup_root / "shortcuts" / src.name
            _copy_path(src, dst)
            shortcuts.append({"source": str(src), "backup": str(dst)})
        return {
            "mode": mode,
            "install_dir": str(install_dir),
            "install_backup": str(install_backup),
            "shortcuts": shortcuts,
        }
    return None


def restore_existing_install(state: dict[str, Any] | None) -> None:
    if not state:
        return
    install_dir = Path(state["install_dir"])
    install_backup = Path(state["install_backup"])
    if install_backup.exists():
        _remove_path(install_dir)
        install_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(install_backup, install_dir)
    for item in state.get("shortcuts", []):
        src = Path(item["source"])
        backup = Path(item["backup"])
        if not backup.exists():
            continue
        _remove_path(src)
        _copy_path(backup, src)


def wait_for_installed_exe(install_dir: Path, timeout_sec: int = 180) -> Path:
    exe_candidates = [
        install_dir / "english-coach-opensource.exe",
        install_dir / "english-coach-cloud.exe",
    ]
    uninstaller = install_dir / "unins000.exe"
    uninstall_data = install_dir / "unins000.dat"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        exe_path = next((path for path in exe_candidates if path.exists()), None)
        uninstall_ready = (
            not uninstaller.exists()
            or (uninstall_data.exists() and uninstall_data.stat().st_size > 0)
        )
        if exe_path is not None and uninstall_ready:
            return exe_path
        time.sleep(1)
    raise TimeoutError(f"安装后未在限定时间内准备好 exe: {install_dir}")


def launch_app(exe_path: Path, appdata_root: Path, label: str, timeout_sec: int = 90) -> tuple[subprocess.Popen[Any], dict[str, Any]]:
    appdata_root.mkdir(parents=True, exist_ok=True)
    probe_path = appdata_root / "ready.json"
    if probe_path.exists():
        probe_path.unlink()
    env = os.environ.copy()
    env["APPDATA"] = str(appdata_root)
    env["ENGLISH_COACH_NO_WEBVIEW"] = "1"
    env["ENGLISH_COACH_READY_FILE"] = str(probe_path)
    env["ENGLISH_COACH_ALLOW_DEV_MACHINE_PATH"] = "1"
    for key in _SANITIZED_ENV_KEYS:
        env.pop(key, None)
    log(f"启动 {label}: {exe_path}")
    process = subprocess.Popen(
        [str(exe_path)],
        cwd=str(exe_path.parent),
        env=env,
    )
    try:
        payload = wait_for_probe(process, probe_path, timeout_sec=timeout_sec, label=label)
        return process, payload
    except Exception:
        stop_process(process, label)
        raise


def verify_single_instance_guard(exe_path: Path, appdata_root: Path, label: str) -> None:
    log(f"验证 {label} 单实例保护")
    probe_path = appdata_root / "duplicate-ready.json"
    if probe_path.exists():
        probe_path.unlink()
    env = os.environ.copy()
    env["APPDATA"] = str(appdata_root)
    env["ENGLISH_COACH_NO_WEBVIEW"] = "1"
    env["ENGLISH_COACH_READY_FILE"] = str(probe_path)
    env["ENGLISH_COACH_ALLOW_DEV_MACHINE_PATH"] = "1"
    for key in _SANITIZED_ENV_KEYS:
        env.pop(key, None)
    process = subprocess.Popen(
        [str(exe_path)],
        cwd=str(exe_path.parent),
        env=env,
    )
    payload: dict[str, Any] | None = None
    deadline = time.time() + 60
    try:
        while time.time() < deadline:
            if probe_path.exists():
                payload = json.loads(probe_path.read_text(encoding="utf-8"))
                break
            if process.poll() is not None:
                break
            time.sleep(0.5)
        if process.poll() is None:
            process.wait(timeout=30)
        assert_true(payload is not None, "重复启动时未写出 probe 文件")
        assert_true(payload.get("status") == "already_running", f"单实例保护未生效: {payload}")
        assert_true(process.returncode == 0, f"重复启动退出码异常: {process.returncode}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def verify_shortcuts(mode: str, install_dir: Path, exe_path: Path) -> None:
    log("验证桌面与开始菜单快捷方式")
    expected = exe_path.resolve()
    for shortcut in _app_shortcut_links(mode):
        assert_true(shortcut.exists(), f"缺少快捷方式: {shortcut}")
        actual = _read_shortcut_target(shortcut).resolve()
        assert_true(actual == expected, f"快捷方式目标未更新: {shortcut} -> {actual}, expected {expected}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def complete_setup(base_url: str, data_dir: Path) -> None:
    log("完成最小离线 Setup")
    request_json(
        f"{base_url}/api/setup",
        method="POST",
        body={
            "name": "Release Smoke",
            "backend": "deepseek",
            "api_key": "",
            "target_exam": "toefl",
            "target_exam_date": "",
            "content_path": "",
            "history_retention_days": 30,
            "data_dir": str(data_dir),
        },
    )
    try:
        request_json(
            f"{base_url}/api/coach/settings",
            method="POST",
            body={
                "preferred_study_time": "20:00",
                "quiet_hours": {"start": "22:30", "end": "08:00"},
                "reminder_level": "basic",
                "desktop_enabled": False,
                "bark_enabled": False,
                "webhook_enabled": False,
                "bark_key": "",
                "webhook_url": "",
            },
            timeout=30,
        )
    except Exception as exc:
        log(f"跳过 coach/settings 验证：{exc}")
    status = request_json(f"{base_url}/api/setup/status")
    assert_true(status["configured"] is True, "Setup 后 configured 应为 true")


def maybe_activate_cloud(base_url: str, expected_version_mode: str) -> None:
    if expected_version_mode != "cloud":
        return
    admin_url, admin_token = _load_seller_admin_credentials()
    if not admin_url or not admin_token:
        raise AssertionError("cloud smoke 缺少可用的卖家配置，不能跳过激活链路")

    status = request_json(f"{base_url}/api/license/status")
    assert_true(status.get("activation_available") is True, f"cloud build 未启用激活能力: {status}")
    raw = secrets.token_hex(8).upper()
    key = f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"
    register = request_worker_json(
        f"{admin_url.rstrip('/')}/register",
        admin_token,
        {"key": key, "days": 7},
        timeout=30,
    )
    assert_true(register.get("ok") is True, f"cloud register 失败: {register}")
    activate = request_json(f"{base_url}/api/license/activate", method="POST", body={"key": key}, timeout=60)
    assert_true(activate.get("ok") is True, f"cloud activate 失败: {activate}")
    post_status = request_json(f"{base_url}/api/license/status")
    assert_true(post_status.get("active") is True, f"cloud activate 后 status 异常: {post_status}")
    assert_true(post_status.get("cloud_license_active") is True, f"cloud license 未激活: {post_status}")
    assert_true(post_status.get("ai_ready") is True, f"cloud AI 未就绪: {post_status}")


def verify_chat_memory_smoke(base_url: str) -> None:
    log("验证 chat remember / word-status / context")
    started = request_json(f"{base_url}/api/chat/start", method="POST", body={}, timeout=60)
    session_id = str(started.get("session_id") or "")
    assert_true(bool(session_id), f"chat/start 未返回 session_id: {started}")
    remembered = request_json(
        f"{base_url}/api/chat/remember/{session_id}",
        method="POST",
        body={
            "fact_type": "goal",
            "fact_key": "smoke_goal",
            "value": {"goal": "TOEFL 105"},
        },
        timeout=60,
    )
    assert_true(remembered.get("ok") is True, f"chat/remember 失败: {remembered}")
    marked = request_json(
        f"{base_url}/api/chat/word-status/{session_id}",
        method="POST",
        body={
            "word": "mitigate",
            "status": "unknown",
            "definition_en": "to reduce severity",
            "tags": ["toefl"],
        },
        timeout=60,
    )
    assert_true(marked.get("ok") is True, f"chat/word-status 失败: {marked}")
    context = request_json(f"{base_url}/api/chat/context/{session_id}", timeout=60)
    assert_true(any(item.get("fact_key") == "smoke_goal" for item in context.get("facts", [])), f"chat/context 缺少 remember 事实: {context}")
    assert_true("mitigate" in context.get("review_words", []) or context.get("memory_summary", {}).get("review_due_count", 0) >= 1, f"chat/context 缺少 word-status 结果: {context}")
    ended = request_json(f"{base_url}/api/chat/end/{session_id}", method="POST", body={}, timeout=60)
    assert_true(ended.get("ok") is True, f"chat/end 失败: {ended}")


def verify_first_launch(base_url: str, expected_version_mode: str) -> None:
    log("验证首启状态")
    status = request_json(f"{base_url}/api/setup/status")
    assert_true(status["version_mode"] == expected_version_mode, f"version_mode 异常: {status}")
    assert_true(status["configured"] is False, f"首次启动不应已有 profile: {status}")


def verify_page_shells(base_url: str, expected_version_mode: str) -> None:
    log("验证主页面壳与核心 API")
    index_html = request_text(f"{base_url}/")
    assert_true("English Coach" in index_html, "首页 HTML 未返回主壳")
    for page in PAGE_MODULES:
        text = request_text(f"{base_url}/static/pages/{page}.js")
        assert_true(len(text.strip()) > 0, f"页面模块为空: {page}")

    coach = request_json_with_retry(f"{base_url}/api/coach/status")
    progress = request_json_with_retry(f"{base_url}/api/progress")
    history = request_json_with_retry(f"{base_url}/api/history/daily?limit_days=7")
    practice = request_json_with_retry(f"{base_url}/api/practice/catalog")
    recommendation = request_json_with_retry(f"{base_url}/api/practice/recommendation")
    memory = request_json_with_retry(f"{base_url}/api/memory/status")
    topic = request_json_with_retry(f"{base_url}/api/chat/topic")
    assert_true("plan" in coach, "coach/status 缺少 plan")
    assert_true(progress["has_profile"] is True, "progress 未识别 profile")
    assert_true("days" in history, "history/daily 返回异常")
    assert_true("exams" in practice, "practice/catalog 返回异常")
    assert_true("next_action" in recommendation, "practice/recommendation 缺少 next_action")
    assert_true("action_candidates" in recommendation, "practice/recommendation 缺少 action_candidates")
    assert_true(recommendation.get("has_profile") is True, "practice/recommendation 未识别 profile")
    assert_true("summary" in memory, "memory/status 缺少 summary")
    assert_true(memory.get("has_profile") is True, "memory/status 未识别 profile")
    assert_true(bool(topic.get("topic")), "chat/topic 未返回话题")
    if expected_version_mode == "cloud":
        license_status = request_json_with_retry(f"{base_url}/api/license/status")
        assert_true("activation_available" in license_status, "cloud build 缺少 license/status")

    mock_session = request_json_with_retry(
        f"{base_url}/api/mock-exam/start",
        method="POST",
        body={"exam": "toefl", "sections": ["reading", "listening"]},
        timeout=40,
    )
    assert_true(bool(mock_session.get("session_id")), "mock-exam/start 未返回 session_id")
    echoed = request_json_with_retry(f"{base_url}/api/mock-exam/session/{mock_session['session_id']}")
    assert_true(echoed["session_id"] == mock_session["session_id"], "mock session 查询失败")


def complete_reading_session(base_url: str) -> None:
    log("完成 1 轮离线 Reading")
    session = request_json(
        f"{base_url}/api/reading/start-filtered",
        method="POST",
        body={
            "exam": "toefl",
            "difficulty": 5,
            "question_types": ["factual"],
            "practice_mode": "targeted",
        },
        timeout=120,
    )
    session_id = session["session_id"]
    question_count = int(session["question_count"])
    assert_true(question_count > 0, "reading session 没有题目")
    final = None
    for index in range(question_count):
        question = request_json(f"{base_url}/api/reading/question/{session_id}/{index}")
        answer = "A"
        if question.get("options"):
            answer = str(question["options"][0])[0]
        final = request_json(
            f"{base_url}/api/reading/answer/{session_id}",
            method="POST",
            body={"question_index": index, "user_answer": answer},
        )
    assert_true(bool(final and final.get("session_complete")), "reading session 未正常完成")


def complete_listening_session(base_url: str) -> None:
    log("完成 1 轮内置 Listening")
    session = request_json(
        f"{base_url}/api/listening/start?exam=toefl&dialogue_type=conversation&question_type=detail",
        method="POST",
        body={},
        timeout=120,
    )
    session_id = session["session_id"]
    question_count = int(session["question_count"])
    assert_true(question_count > 0, "listening session 没有题目")
    final = None
    for index in range(question_count):
        question = request_json(f"{base_url}/api/listening/question/{session_id}/{index}")
        answer = "A"
        if question.get("options"):
            answer = str(question["options"][0])[0]
        final = request_json(
            f"{base_url}/api/listening/answer/{session_id}",
            method="POST",
            body={"question_index": index, "answer": answer},
        )
    assert_true(bool(final and final.get("session_complete")), "listening session 未正常完成")


def verify_post_practice_state(base_url: str) -> None:
    log("验证训练后 Home / Progress / History 数据变化")
    progress = request_json(f"{base_url}/api/progress")
    coach = request_json(f"{base_url}/api/coach/status")
    history = request_json(f"{base_url}/api/history/daily?limit_days=3")
    memory = request_json(f"{base_url}/api/memory/status")
    recommendation = request_json(f"{base_url}/api/practice/recommendation")
    assert_true(progress["today_summary"]["sessions"] >= 2, f"today_summary.sessions 异常: {progress['today_summary']}")
    assert_true(bool(history["days"]), "history/daily 应至少有一天记录")
    first_day = history["days"][0]
    assert_true(len(first_day["sessions"]) >= 2, "当天 session 数量不足")
    assert_true(bool(first_day["plan"]["summary"]["result_card"]), "History 当天结果感为空")
    assert_true(bool(first_day["plan"]["summary"].get("improved_point")), "History 当天进步点为空")
    assert_true(bool(first_day["plan"]["summary"]["tomorrow_reason"]), "History 明天理由为空")
    assert_true(bool(coach["plan"]["summary"]["result_card"]), "coach result_card 为空")
    assert_true(bool(coach["plan"]["summary"].get("improved_point")), "coach improved_point 为空")
    assert_true(bool(coach["plan"]["summary"]["tomorrow_reason"]), "coach tomorrow_reason 为空")
    assert_true("next_action" in coach, "coach/status 缺少 next_action")
    assert_true("action_candidates" in coach, "coach/status 缺少 action_candidates")
    assert_true("summary" in memory and memory["summary"]["review_due_count"] >= 0, "memory/status summary 异常")
    assert_true("next_action" in recommendation, "practice/recommendation 缺少 next_action")
    assert_true("action_candidates" in recommendation, "practice/recommendation 缺少 action_candidates")


def run_flow(exe_path: Path, appdata_root: Path, label: str, expected_version_mode: str) -> None:
    process = None
    actual_pid = None
    try:
        process, probe = launch_app(exe_path, appdata_root, label)
        actual_pid = int(probe.get("pid") or 0) or None
        base_url = str(probe["url"]).rstrip("/")
        data_dir = appdata_root / "smoke-data"
        verify_single_instance_guard(exe_path, appdata_root, label)
        verify_first_launch(base_url, expected_version_mode)
        complete_setup(base_url, data_dir)
        verify_page_shells(base_url, expected_version_mode)
        complete_reading_session(base_url)
        complete_listening_session(base_url)
        verify_post_practice_state(base_url)
        maybe_activate_cloud(base_url, expected_version_mode)
        if expected_version_mode == "cloud":
            verify_chat_memory_smoke(base_url)
        log(f"{label} 验证通过")
    finally:
        if process is not None:
            stop_process_by_pid(process, label, actual_pid)


def run_installer(installer_path: Path, install_dir: Path) -> Path:
    log(f"静默安装 setup: {installer_path}")
    cleanup_stale_smoke_uninstall_entries()
    if install_dir.exists():
        shutil.rmtree(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(installer_path),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/DIR={install_dir}",
        ],
        check=True,
        cwd=str(installer_path.parent),
    )
    exe_path = wait_for_installed_exe(install_dir)
    assert_true(exe_path.exists(), f"安装后未找到 exe: {exe_path}")
    return exe_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test English Coach desktop releases.")
    parser.add_argument("--portable-exe", default="")
    parser.add_argument("--installer-exe", default="")
    parser.add_argument("--expected-version-mode", choices=["opensource", "cloud"], default="opensource")
    parser.add_argument("--keep-temp", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.portable_exe:
        portable_exe = Path(args.portable_exe)
    else:
        portable_exe = DEFAULT_PORTABLE_CLOUD_EXE if args.expected_version_mode == "cloud" else DEFAULT_PORTABLE_EXE
    if args.installer_exe:
        installer_exe = Path(args.installer_exe)
    else:
        installer_exe = DEFAULT_INSTALLER_CLOUD_EXE if args.expected_version_mode == "cloud" else DEFAULT_INSTALLER_EXE
    if not portable_exe.exists():
        raise FileNotFoundError(f"找不到 portable exe: {portable_exe}")
    if not installer_exe.exists():
        raise FileNotFoundError(f"找不到 installer exe: {installer_exe}")

    temp_root_obj = None
    if args.keep_temp:
        temp_root = Path(tempfile.mkdtemp(prefix="english_coach_release_smoke_"))
    else:
        temp_root_obj = tempfile.TemporaryDirectory(
            prefix="english_coach_release_smoke_",
            ignore_cleanup_errors=True,
        )
        temp_root = Path(temp_root_obj.name)
    preserved_install = preserve_existing_install(args.expected_version_mode, temp_root)
    uninstall_snapshots = backup_uninstall_registry(args.expected_version_mode)
    try:
        run_flow(portable_exe, temp_root / "portable-appdata", "portable exe", args.expected_version_mode)
        install_dir = temp_root / "installed-app"
        installed_exe = run_installer(installer_exe, install_dir)
        verify_shortcuts(args.expected_version_mode, install_dir, installed_exe)
        run_flow(installed_exe, temp_root / "installed-appdata", "installed exe", args.expected_version_mode)
        cleanup_installed_app(install_dir)
        cleanup_stale_smoke_uninstall_entries()
        restore_uninstall_registry(uninstall_snapshots)
        log("portable + installer release smoke 全部通过")
        return 0
    finally:
        cleanup_stale_smoke_uninstall_entries()
        restore_uninstall_registry(uninstall_snapshots)
        restore_existing_install(preserved_install)
        if temp_root_obj is not None:
            temp_root_obj.cleanup()
        else:
            log(f"保留临时目录: {temp_root}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, RuntimeError, TimeoutError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        log(f"失败: {exc}")
        raise SystemExit(1)
