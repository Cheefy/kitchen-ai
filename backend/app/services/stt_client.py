"""Client for the self-hosted whisper.cpp server (kitchen_ai_spec.md §12).
Audio in, transcript out -- kept fully local (no cloud STT) to match how
Postgres/the LLM are run, and because voice audio leaving the house is a
meaningfully different privacy tradeoff than the text it gets turned into.

whisper.cpp's server example takes multipart uploads at /inference and, run
with --convert (needs ffmpeg, already in the runtime image), accepts
whatever container format the browser's MediaRecorder produced -- no
client-side transcoding to WAV needed.
"""

import os

import httpx

STT_BASE_URL = os.environ.get("STT_BASE_URL", "http://localhost:8082")


async def transcribe(audio_bytes: bytes, filename: str, content_type: str) -> str:
    files = {"file": (filename, audio_bytes, content_type)}
    data = {"response_format": "json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{STT_BASE_URL}/inference", files=files, data=data)
        response.raise_for_status()
        result = response.json()
    return (result.get("text") or "").strip()
