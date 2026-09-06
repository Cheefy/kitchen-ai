from fastapi import APIRouter

from app import schemas
from app.services.voice_orchestrator import run_voice_command

router = APIRouter()


@router.post("/voice/command", response_model=schemas.VoiceCommandResult)
async def voice_command(body: schemas.VoiceCommandRequest):
    """kitchen_ai_spec.md §12 -- text in, tool calls executed, reply out.
    This is the text-only harness for testing the tool-calling loop before
    any real STT/TTS or Home Assistant wiring exists."""
    return await run_voice_command(body.transcript)
