"""
Text-to-speech via edge-tts (free, uses Microsoft Edge voices, no API key needed).
Falls back silently if edge-tts is not installed or audio playback fails.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path


# Best voice for English learners — clear American English
_VOICE = "en-US-JennyNeural"


def speak(text: str, voice: str = _VOICE) -> bool:
    """
    Speak text aloud. Returns True if successful, False if unavailable.
    Blocks until audio finishes playing.
    """
    try:
        import edge_tts
    except ImportError:
        return False

    try:
        asyncio.run(_speak_async(text, voice))
        return True
    except Exception:
        return False


async def _speak_async(text: str, voice: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name

    try:
        await communicate.save(tmp_path)
        _play(tmp_path)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def _play(path: str) -> None:
    """Play an audio file using the best available player."""
    import sys
    import subprocess

    if sys.platform == "win32":
        # Use Windows Media Player via PowerShell (no extra install needed)
        subprocess.run(
            ["powershell", "-c", f"(New-Object Media.SoundPlayer '{path}').PlaySync()"],
            capture_output=True,
        )
        # SoundPlayer only handles WAV; fall back to Start-Process for mp3
        subprocess.run(
            ["powershell", "-c",
             f"$p = New-Object System.Windows.Media.MediaPlayer; "
             f"$p.Open([uri]'{path}'); $p.Play(); Start-Sleep -s 4"],
            capture_output=True,
        )
    elif sys.platform == "darwin":
        subprocess.run(["afplay", path], capture_output=True)
    else:
        # Linux: try mpg123, then ffplay
        for player in ["mpg123", "ffplay"]:
            result = subprocess.run([player, "-q", path], capture_output=True)
            if result.returncode == 0:
                break
