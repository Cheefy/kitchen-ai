"""Orchestration loop for voice/text commands (kitchen_ai_spec.md §12):
sends the transcript + tool definitions to the LLM, executes any tool
calls it requests, feeds results back, and repeats until it produces a
final natural-language reply (or a safety cap on iterations is hit).

The Guiding Principle's assume-and-announce vs. ask-first split is
encoded directly in the system prompt rather than in code -- the model
decides when to act vs. ask, same as a human would from written
instructions. Whether it actually follows this reliably is exactly what
the spec's own benchmark plan (§12/§14) exists to check.
"""

import json

from app.services.llm_client import chat_completion
from app.services.voice_tools import TOOLS, dispatch_tool_call

MAX_TOOL_ITERATIONS = 5

SYSTEM_PROMPT = """You are the voice assistant for Kitchen AI, a home kitchen assistant that manages recipes, inventory, cooking sessions, and nutrition tracking. You have tools to take real actions -- use them rather than just describing what you would do, and always report back what you actually did.

Behavioral rules:
- For cheap, reversible actions -- recipe edits default to this-time-only, ambiguous absolute-vs-scale phrasing defaults to the narrower single-ingredient interpretation, an explicit direct command like "I'm finished cooking" defaults to 100% eaten -- just take the action and clearly state what you did, so the user can correct it if it's wrong. Don't ask permission first for these.
- For anything where a wrong guess would silently corrupt tracking data -- which meal-prep batch when more than one is pending (call list_pending_meal_prep_batches and ask), which specific product when several are in stock, whether food was eaten vs. disposed -- ask a clarifying question instead of guessing.
- The "is this still one meal or does this make more servings" question when scaling a recipe genuinely can't be inferred -- always ask if the user hasn't said.
- Keep spoken replies short and conversational -- this is a voice interface, not a chat window. Don't recite raw tool output; summarize what happened in plain language.
"""


async def run_voice_command(transcript: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": transcript},
    ]
    tool_call_log = []

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await chat_completion(messages, tools=TOOLS)
        message = response["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return {"reply": message.get("content", "") or "", "tool_calls": tool_call_log}

        for call in tool_calls:
            name = call["function"]["name"]
            try:
                arguments = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            result = await dispatch_tool_call(name, arguments)
            tool_call_log.append({"name": name, "arguments": arguments, "result": result})
            messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)}
            )

    return {
        "reply": "I made several changes but hit my step limit before finishing -- check what happened so far.",
        "tool_calls": tool_call_log,
    }
