import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from app import schemas
from app.services.stt_client import transcribe
from app.services.voice_orchestrator import run_voice_command

router = APIRouter()


@router.post("/voice/command", response_model=schemas.VoiceCommandResult)
async def voice_command(body: schemas.VoiceCommandRequest):
    """kitchen_ai_spec.md §12 -- text in, tool calls executed, reply out.
    This is the text-only harness for testing the tool-calling loop before
    any real STT/TTS or Home Assistant wiring exists."""
    return await run_voice_command(body.transcript)


@router.post("/voice/command-audio", response_model=schemas.VoiceCommandResult)
async def voice_command_audio(file: UploadFile = File(...)):
    """The push-to-talk button's endpoint: audio in (whatever container
    format MediaRecorder produced), transcribed locally via whisper.cpp,
    then run through the same tool-calling loop as the text endpoint. The
    transcript is echoed back so the UI can show what was actually heard
    -- a voice interface with no visibility into misheard words is much
    harder to trust or correct than a chat window."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="empty audio upload")

    try:
        transcript = await transcribe(audio_bytes, file.filename or "audio", file.content_type or "audio/webm")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="speech-to-text service unavailable") from exc

    if not transcript:
        raise HTTPException(status_code=422, detail="couldn't make out any speech in that recording")

    result = await run_voice_command(transcript)
    result["transcript"] = transcript
    return result
