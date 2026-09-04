"""Pushover notifications (kitchen_ai_spec.md §10). Single shared function,
not scattered calls. Real credentials come from the environment (.env),
never hardcoded.
"""

import os

import httpx

PUSHOVER_API_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")
PUSHOVER_USER_KEY = os.environ.get("PUSHOVER_USER_KEY")


async def notify(
    message: str, title: str = "Kitchen AI", priority: int = 0, sound: str | None = None
) -> dict | None:
    if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY:
        print("Pushover notify skipped -- PUSHOVER_API_TOKEN/PUSHOVER_USER_KEY not set")
        return None

    payload = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message,
        "title": title,
        "priority": priority,
    }
    if sound:
        payload["sound"] = sound

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.pushover.net/1/messages.json", data=payload, timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        # A failed notification should never crash the caller.
        print(f"Pushover notify failed: {exc}")
        return None
