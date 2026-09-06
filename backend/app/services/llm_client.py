"""Client for the tool-calling LLM (kitchen_ai_spec.md §12). llama.cpp
exposes an OpenAI-compatible endpoint, so this is a thin wrapper, not a
vendor SDK -- keeps the door open to swap models/engines later without
touching the orchestration logic in voice_tools.py.
"""

import os

import httpx

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8081/v1")


async def chat_completion(
    messages: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto"
) -> dict:
    payload = {"model": "local", "messages": messages, "temperature": 0.2}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{LLM_BASE_URL}/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()
