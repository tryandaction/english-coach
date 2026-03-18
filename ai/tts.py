"""
Text-to-speech via edge-tts (free, uses Microsoft Edge voices, no API key needed).
Falls back silently if edge-tts is not installed or audio playback fails.
Supports multiple accents and speed control for professional language learning.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path


# Voice profiles for different accents
VOICE_PROFILES = {
    "american": {
        "male": "en-US-GuyNeural",
        "female": "en-US-JennyNeural",
    },
    "british": {
        "male": "en-GB-RyanNeural",
        "female": "en-GB-SoniaNeural",
    },
    "australian": {
        "male": "en-AU-WilliamNeural",
        "female": "en-AU-NatashaNeural",
    },
}

# Default voice for English learners — clear American English
_DEFAULT_VOICE = "en-US-JennyNeural"


def speak(text: str, voice: str = _DEFAULT_VOICE, rate: float = 1.0) -> bool:
    """
    Speak text aloud. Returns True if successful, False if unavailable.
    Blocks until audio finishes playing.

    Args:
        text: Text to speak
        voice: Voice name (e.g., "en-US-JennyNeural")
        rate: Speech rate multiplier (0.5-2.0, default 1.0)
    """
    try:
        import edge_tts
    except ImportError:
        return False

    try:
        asyncio.run(_speak_async(text, voice, rate))
        return True
    except Exception:
        return False


def get_voice(accent: str = "american", gender: str = "female") -> str:
    """
    Get voice name for specified accent and gender.

    Args:
        accent: "american", "british", or "australian"
        gender: "male" or "female"

    Returns:
        Voice name string
    """
    accent = accent.lower()
    gender = gender.lower()

    if accent not in VOICE_PROFILES:
        accent = "american"
    if gender not in ["male", "female"]:
        gender = "female"

    return VOICE_PROFILES[accent][gender]


async def synthesize_with_accent(
    text: str,
    accent: str = "american",
    gender: str = "female",
    rate: float = 1.0,
    output_path: str = None,
) -> str:
    """
    Synthesize speech with specified accent and save to file.

    Args:
        text: Text to synthesize
        accent: "american", "british", or "australian"
        gender: "male" or "female"
        rate: Speech rate multiplier (0.5-2.0)
        output_path: Optional output file path (if None, creates temp file)

    Returns:
        Path to generated audio file
    """
    try:
        import edge_tts
    except ImportError:
        raise ImportError("edge-tts not installed")

    voice = get_voice(accent, gender)

    # Create rate string for edge-tts (e.g., "+20%" or "-30%")
    rate_percent = int((rate - 1.0) * 100)
    rate_str = f"{rate_percent:+d}%" if rate_percent != 0 else "+0%"

    if output_path is None:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            output_path = f.name

    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_path)

    return output_path


async def _speak_async(text: str, voice: str, rate: float = 1.0) -> None:
    import edge_tts

    # Create rate string for edge-tts
    rate_percent = int((rate - 1.0) * 100)
    rate_str = f"{rate_percent:+d}%" if rate_percent != 0 else "+0%"

    communicate = edge_tts.Communicate(text, voice, rate=rate_str)

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


# Convenience functions for different accents
def speak_american(text: str, gender: str = "female", rate: float = 1.0) -> bool:
    """Speak with American accent."""
    voice = get_voice("american", gender)
    return speak(text, voice, rate)


def speak_british(text: str, gender: str = "female", rate: float = 1.0) -> bool:
    """Speak with British accent."""
    voice = get_voice("british", gender)
    return speak(text, voice, rate)


def speak_australian(text: str, gender: str = "female", rate: float = 1.0) -> bool:
    """Speak with Australian accent."""
    voice = get_voice("australian", gender)
    return speak(text, voice, rate)
