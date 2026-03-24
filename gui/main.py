"""
Entry point for the GUI — starts FastAPI on a background thread, opens PyWebView window.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

# Static imports for PyInstaller compatibility
# NOTE: uvicorn imported dynamically to avoid Python 3.13 type annotation issues
from gui.coach_runtime import start_coach_scheduler
from gui.deps import warm_components
from gui.server import create_app

# Ensure project root is on sys.path when running as exe
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Debug log — written to user home so we can diagnose startup issues
_LOG = os.path.join(os.path.expanduser("~"), "english_coach_debug.log")

def _log(msg: str) -> None:
    try:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def _env_flag(name: str) -> bool:
    value = str(os.environ.get(name, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _write_probe_file(path: str, payload: dict[str, object]) -> None:
    if not path:
        return
    try:
        probe_path = Path(path)
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"Wrote probe file: {probe_path}")
    except Exception as e:
        _log(f"Failed to write probe file {path}: {type(e).__name__}: {e}")

_LOADING_HTML = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:#1a1a2e; display:flex; flex-direction:column;
         align-items:center; justify-content:center; height:100vh;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; color:#e0e0e0; }
  .logo { font-size:56px; margin-bottom:16px; }
  h1 { font-size:24px; font-weight:600; margin-bottom:8px; }
  p  { font-size:14px; color:#888; margin-bottom:32px; }
  .bar { width:200px; height:4px; background:#2a2a4a; border-radius:2px; overflow:hidden; }
  .fill { height:100%; background:linear-gradient(90deg,#4f8ef7,#7c5cfc);
          border-radius:2px; animation:load 1.8s ease-in-out infinite; }
  @keyframes load { 0%{width:0%} 60%{width:80%} 100%{width:100%} }
  #status { font-size:12px; color:#555; margin-top:16px; }
</style>
</head>
<body>
  <div class="logo">🎓</div>
  <h1>English Coach</h1>
  <p>Starting up…</p>
  <div class="bar"><div class="fill"></div></div>
  <div id="status">Initializing…</div>
  <script>
    var start = Date.now();
    var port = PORT_PLACEHOLDER;
    function tryConnect() {
      var elapsed = Math.round((Date.now() - start) / 1000);
      document.getElementById('status').textContent = 'Loading… ' + elapsed + 's';
      fetch('http://127.0.0.1:' + port + '/')
        .then(function(r) {
          if (r.ok) { location.href = 'http://127.0.0.1:' + port + '/'; }
          else { setTimeout(tryConnect, 500); }
        })
        .catch(function() { setTimeout(tryConnect, 500); });
    }
    setTimeout(tryConnect, 500);
  </script>
</body>
</html>"""


def _find_existing_server(candidates: list[int]) -> int | None:
    import urllib.request

    for port in candidates:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as resp:
                if resp.status == 200:
                    _log(f"Reusing existing healthy server on port {port}")
                    return port
        except Exception:
            continue
    return None


def _find_free_port(candidates: list[int]) -> int:
    """Find a free port from candidates, or any free port if all fail."""
    import random

    # Shuffle candidates to avoid always trying the same port first
    candidates = list(candidates)
    random.shuffle(candidates)

    for port in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # Try to bind and immediately close
                s.bind(("127.0.0.1", port))
                _log(f"Found free port: {port}")
                return port
        except OSError as e:
            _log(f"Port {port} unavailable: {e}")
            continue

    # If all candidates fail, let OS assign a random free port
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            _log(f"Using OS-assigned port: {port}")
            return port
    except Exception as e:
        _log(f"CRITICAL: Cannot find any free port: {e}")
        # Last resort: try a high random port
        import random
        port = random.randint(10000, 60000)
        _log(f"Last resort: trying random port {port}")
        return port


def _start_server(port: int) -> None:
    """Start FastAPI server on given port."""
    _log(f"=== Starting server on port {port} ===")
    try:
        _log("Creating FastAPI app...")
        app = create_app()
        _log("FastAPI app created successfully")

        _log("Starting uvicorn server...")
        # Import uvicorn dynamically to avoid Python 3.13 type annotation issues at import time
        import uvicorn
        # Use uvicorn.run() with proper configuration
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error",  # Only show errors
            access_log=False,
            log_config=None,
            timeout_keep_alive=5,
            limit_concurrency=100,
            backlog=100
        )
        _log("Server stopped normally")
    except OSError as e:
        _log(f"SERVER ERROR (OSError): {e}")
        _log(f"This usually means port {port} is already in use")
    except Exception as e:
        _log(f"SERVER ERROR (Exception): {type(e).__name__}: {e}")
        import traceback
        _log(f"Traceback: {traceback.format_exc()}")


def _wait_and_load(window, port: int) -> None:
    """Poll HTTP until server is ready, then navigate via load_url."""
    import urllib.request
    url = f"http://127.0.0.1:{port}/"
    _log(f"polling started for {url}")
    deadline = time.time() + 120.0
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    _log(f"server ready after {attempt} attempts, navigating")
                    # Use load_url instead of evaluate_js for more reliable navigation
                    window.load_url(url)
                    return
        except Exception as e:
            if attempt % 10 == 0:
                _log(f"attempt {attempt}: {e}")
            time.sleep(0.5)
    _log("TIMEOUT: server never became ready")


def main() -> None:
    """Main entry point - start server and open window."""
    _log("=" * 60)
    _log("=== English Coach Starting ===")
    _log(f"=== Time: {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    _log("=" * 60)

    import urllib.request

    no_webview = _env_flag("ENGLISH_COACH_NO_WEBVIEW")
    ready_file = str(os.environ.get("ENGLISH_COACH_READY_FILE", "") or "").strip()
    _log(f"Smoke mode: {'enabled' if no_webview else 'disabled'}")
    if ready_file:
        _log(f"Ready file configured: {ready_file}")

    existing_port = _find_existing_server([8765, 8766, 8767, 8768, 8769, 8770])
    if existing_port:
        port = existing_port
        server_ready = True
        server_thread = None
        _log(f"Using existing server on port {port}")
    else:
        server_ready = False
        server_thread = None

    # Find a free port
    if not server_ready:
        _log("Finding free port...")
        try:
            port = _find_free_port([8765, 8766, 8767, 8768, 8769, 8770])
            _log(f"Selected port: {port}")
        except Exception as e:
            _log(f"CRITICAL ERROR finding port: {e}")
            if no_webview:
                _write_probe_file(
                    ready_file,
                    {
                        "status": "failed",
                        "stage": "port_selection",
                        "error": str(e),
                        "log_path": _LOG,
                    },
                )
                raise SystemExit(1)
            # Show error and exit
            import webview
            error_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ background:#1a1a2e; color:#e0e0e0; font-family:sans-serif;
         display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
  .error {{ text-align:center; max-width:500px; }}
  h1 {{ color:#f26b6b; font-size:24px; margin-bottom:16px; }}
  p {{ color:#888; font-size:14px; line-height:1.6; }}
</style>
</head>
<body>
  <div class="error">
    <h1>⚠️ 严重错误</h1>
    <p>无法找到可用端口。请重启计算机后再试。</p>
    <p style="margin-top:24px; font-size:12px;">错误详情：{e}</p>
  </div>
</body>
</html>"""
            webview.create_window("English Coach - 错误", html=error_html, width=500, height=300)
            webview.start()
            return

        # Start server in background thread
        _log("Starting server thread...")
        server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
        server_thread.start()
        _log("Server thread started")

    try:
        start_coach_scheduler()
        _log("Coach scheduler started")
    except Exception as e:
        _log(f"Coach scheduler failed to start: {type(e).__name__}: {e}")

    try:
        warm_components(blocking=False)
        _log("Background component warmup started")
    except Exception as e:
        _log(f"Background component warmup failed to start: {type(e).__name__}: {e}")

    # Wait for server to be ready
    health_url = f"http://127.0.0.1:{port}/health"
    app_url = f"http://127.0.0.1:{port}/"
    _log(f"Waiting for server at {health_url}")

    if not server_ready:
        max_attempts = 90  # 90 attempts × 0.5s = 45 seconds max

        for i in range(max_attempts):
            try:
                with urllib.request.urlopen(health_url, timeout=3.0) as r:
                    if r.status == 200:
                        elapsed = (i + 1) * 0.5
                        _log(f"✓ Server ready after {i+1} attempts ({elapsed:.1f}s)")
                        server_ready = True
                        break
            except urllib.error.URLError as e:
                # Connection refused is expected while server is starting
                if i == 0 or (i + 1) % 10 == 0:
                    _log(f"Attempt {i+1}/{max_attempts}: {type(e).__name__}")
            except Exception as e:
                _log(f"Attempt {i+1}/{max_attempts}: Unexpected error: {type(e).__name__}: {e}")

            time.sleep(0.5)

    if not server_ready:
        _log("✗ ERROR: Server failed to start after readiness timeout")
        _log(f"Check log file for details: {_LOG}")
        if no_webview:
            _write_probe_file(
                ready_file,
                {
                    "status": "failed",
                    "stage": "server_startup",
                    "port": port,
                    "health_url": health_url,
                    "url": app_url,
                    "log_path": _LOG,
                },
            )
            raise SystemExit(1)

        # Show detailed error window
        import webview
        error_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  body {{ background:#1a1a2e; color:#e0e0e0; font-family:sans-serif;
         display:flex; align-items:center; justify-content:center; height:100vh; margin:0; padding:20px; }}
  .error {{ text-align:center; max-width:600px; }}
  h1 {{ color:#f26b6b; font-size:24px; margin-bottom:16px; }}
  p {{ color:#888; font-size:14px; line-height:1.6; margin-bottom:16px; }}
  ul {{ text-align:left; color:#888; font-size:14px; margin:16px 0; }}
  li {{ margin:8px 0; }}
  .log-path {{ background:#2a2a4a; padding:8px 12px; border-radius:4px;
               font-family:monospace; font-size:12px; color:#4f8ef7; margin-top:16px; }}
  .btn {{ display:inline-block; margin-top:20px; padding:10px 20px;
          background:#4f8ef7; color:#fff; text-decoration:none;
          border-radius:4px; font-size:14px; }}
  .btn:hover {{ background:#3d7de0; }}
</style>
</head>
<body>
  <div class="error">
    <h1>⚠️ 启动失败</h1>
    <p>English Coach 无法启动。可能的原因：</p>
    <ul>
      <li>端口被其他程序占用（尝试关闭其他应用）</li>
      <li>防火墙阻止了程序（添加到白名单）</li>
      <li>系统权限不足（以管理员身份运行）</li>
      <li>杀毒软件误报（添加到信任列表）</li>
    </ul>
    <p style="margin-top:24px;">解决方法：</p>
    <ul>
      <li>1. 重启计算机</li>
      <li>2. 关闭其他占用端口的程序</li>
      <li>3. 以管理员身份运行</li>
      <li>4. 查看日志文件获取详细信息</li>
    </ul>
    <div class="log-path">日志文件：{_LOG}</div>
    <a href="#" class="btn" onclick="window.close()">关闭</a>
  </div>
</body>
</html>"""
        webview.create_window("English Coach - 启动失败", html=error_html, width=700, height=600)
        webview.start()
        return

    _write_probe_file(
        ready_file,
        {
            "status": "ready",
            "port": port,
            "health_url": health_url,
            "url": app_url,
            "log_path": _LOG,
            "pid": os.getpid(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )

    if no_webview:
        _log("Smoke mode active; skipping WebView and keeping process alive")
        try:
            while server_thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            _log("Smoke mode interrupted")
        return

    # Server is ready, create main window
    _log("Creating main window...")
    try:
        import webview
        webview.create_window(
            "English Coach",
            url=app_url,
            width=1100,
            height=750,
            min_size=(800, 600),
        )
        _log("Window created, starting webview...")
        webview.start()
        _log("Webview closed normally")
    except Exception as e:
        _log(f"ERROR creating window: {type(e).__name__}: {e}")
        import traceback
        _log(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
