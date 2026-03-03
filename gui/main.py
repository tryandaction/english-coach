"""
Entry point for the GUI — starts FastAPI on a background thread, opens PyWebView window.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

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


def _find_free_port(candidates: list[int]) -> int:
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port available in candidates")


def _start_server(port: int) -> None:
    _log(f"server thread starting on port {port}")
    try:
        import uvicorn
        from gui.server import create_app
        _log("imports done, calling uvicorn.run")
        uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="error")
    except Exception as e:
        _log(f"server ERROR: {e}")


def _wait_and_load(window, port: int) -> None:
    """Poll HTTP until server is ready, then navigate via evaluate_js."""
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
                    # evaluate_js is thread-safe; load_url can silently fail
                    window.evaluate_js(f"location.href='{url}'")
                    return
        except Exception as e:
            if attempt % 10 == 0:
                _log(f"attempt {attempt}: {e}")
            time.sleep(0.5)
    _log("TIMEOUT: server never became ready")


def main() -> None:
    _log("=== main() started ===")
    import urllib.request
    import webview

    port = _find_free_port([8765, 8766, 8767, 8768])
    _log(f"port: {port}")
    threading.Thread(target=_start_server, args=(port,), daemon=True).start()

    # Wait for server in main thread before opening window
    # Reduced timeout - server should start quickly now
    url = f"http://127.0.0.1:{port}/"
    for i in range(60):  # 30 seconds max (was 120 seconds)
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    _log(f"server ready after {i} attempts")
                    break
        except Exception as e:
            if i % 10 == 0:
                _log(f"waiting attempt {i}: {e}")
            time.sleep(0.5)
    else:
        _log("WARNING: server never ready, opening anyway")

    _log("creating window")
    webview.create_window(
        "English Coach", url=url,
        width=1100, height=750, min_size=(800, 600),
    )
    webview.start()
    _log("webview.start() returned")


if __name__ == "__main__":
    main()
