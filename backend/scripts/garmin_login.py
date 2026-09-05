"""One-time (or occasional) interactive Garmin Connect login. Run this
directly -- not part of the FastAPI app -- to (re)establish the session
tokenstore the backend resumes from (kitchen_ai_spec.md §9). Only needed
again if the saved tokens ever expire or get revoked; the running backend
resumes from the saved session on its own otherwise.

Usage: python scripts/garmin_login.py
"""

import getpass
import os

from garminconnect import Garmin

tokenstore = os.environ.get("GARMIN_TOKENSTORE", "/data/garmin_tokens")

email = input("Garmin Connect email: ").strip()
password = getpass.getpass("Garmin Connect password: ")


def prompt_mfa() -> str:
    return input("MFA code: ").strip()


client = Garmin(email=email, password=password, prompt_mfa=prompt_mfa)
client.login(tokenstore)
print(f"Logged in as {client.get_full_name()}. Session saved to {tokenstore}.")
