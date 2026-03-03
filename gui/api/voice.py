"""Voice API — edge-tts TTS endpoint + WebSocket voice call mode."""
from __future__ import annotations

import asyncio
import json
import tempfile
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Default voice
_DEFAULT_VOICE = "en-US-AriaNeural"

# Available voices for the UI selector
VOICES = [
    {"id": "en-US-AriaNeural",     "label": "Aria (US Female)",      "accent": "American"},
    {"id": "en-US-JennyNeural",    "label": "Jenny (US Female)",     "accent": "American"},
    {"id": "en-US-GuyNeural",      "label": "Guy (US Male)",         "accent": "American"},
    {"id": "en-US-EricNeural",     "label": "Eric (US Male)",        "accent": "American"},
    {"id": "en-GB-SoniaNeural",    "label": "Sonia (UK Female)",     "accent": "British"},
    {"id": "en-GB-RyanNeural",     "label": "Ryan (UK Male)",        "accent": "British"},
    {"id": "en-AU-NatashaNeural",  "label": "Natasha (AU Female)",   "accent": "Australian"},
]


@router.get("/voices")
def list_voices():
    return {"voices": VOICES, "default": _DEFAULT_VOICE}


@router.get("/tts")
async def tts(
    text: str = Query(...),
    voice: str = Query(default=_DEFAULT_VOICE),
    rate: str = Query(default="-10%"),
):
    """Stream MP3 audio for the given text using edge-tts."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate)

        async def audio_stream():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]

        return StreamingResponse(audio_stream(), media_type="audio/mpeg")
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(500, f"TTS error: {e}")


# ── Voice call WebSocket ──────────────────────────────────────────────────────

_whisper_model = None

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("语音识别模块未安装，请运行: pip install faster-whisper")
        # Use mirror for users in China where huggingface.co is blocked
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model


@router.websocket("/call/{session_id}")
async def voice_call(websocket: WebSocket, session_id: str):
    """
    WebSocket voice call endpoint.
    Protocol:
      client → server: binary audio (webm/opus chunks) OR text JSON {"type":"end"}
      server → client: JSON {"type":"transcript","text":"..."}
                        JSON {"type":"response","text":"..."}
                        binary audio (MP3 TTS chunks)
                        JSON {"type":"done"}
    """
    from gui.deps import get_components, load_config
    from gui.api.chat import _sessions

    await websocket.accept()

    kb, srs, user_model, ai, profile = get_components()
    if not profile or not ai:
        await websocket.send_text(json.dumps({"type": "error", "text": "No profile or AI configured"}))
        await websocket.close()
        return

    # Get or create chat session for context
    sess = _sessions.get(session_id)
    voice = _DEFAULT_VOICE

    try:
        while True:
            msg = await websocket.receive()

            # Text control message
            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "set_voice":
                    voice = data.get("voice", _DEFAULT_VOICE)
                continue

            # Binary audio data
            if "bytes" not in msg:
                continue

            audio_bytes = msg["bytes"]
            if not audio_bytes:
                continue

            # Save to temp file for Whisper
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            try:
                # STT
                model = _get_whisper()
                segments, _ = model.transcribe(tmp_path, language="en", beam_size=1)
                transcript = " ".join(s.text for s in segments).strip()
            finally:
                os.unlink(tmp_path)

            if not transcript:
                continue

            # Send transcript back
            await websocket.send_text(json.dumps({"type": "transcript", "text": transcript}))

            # Build messages for AI
            history = []
            if sess:
                history = sess.history[-10:]  # last 10 turns for context

            system_prompt = (
                f"You are an English conversation tutor. The student's CEFR level is {profile.cefr_level}. "
                f"Keep responses concise (2-4 sentences), natural, and conversational. "
                f"Gently correct grammar errors if any. Speak as if in a real voice conversation."
            )
            messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": transcript}]

            # Get AI response
            response_text = ai.chat(messages, cefr_level=profile.cefr_level)

            # Send text response
            await websocket.send_text(json.dumps({"type": "response", "text": response_text}))

            # Stream TTS audio back
            import edge_tts
            communicate = edge_tts.Communicate(response_text, voice, rate="-10%")
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    await websocket.send_bytes(chunk["data"])

            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "text": str(e)}))
        except Exception:
            pass
