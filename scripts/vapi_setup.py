"""Create (or update) the Vapi assistant + tools from code.

Why a script instead of dashboard clicks: it's reproducible, version-controlled,
and — critically — it keeps the assistant's server URL and every tool's server
URL in lockstep. When the tunnel URL changes, re-running this with the existing
assistant id updates all of them at once, avoiding the classic "updated the
assistant, forgot the tools" bug.

Usage
-----
    # First time (creates a new assistant, prints its id):
    python -m scripts.vapi_setup --webhook-url https://xxxx.trycloudflare.com/webhook

    # After the tunnel URL changes (updates the same assistant + tools):
    python -m scripts.vapi_setup --webhook-url https://yyyy.trycloudflare.com/webhook \
        --assistant-id <id-from-first-run>

Reads VAPI_PRIVATE_KEY (and optionally VAPI_WEBHOOK_SECRET) from the environment/.env.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

from app.config import settings

VAPI_BASE = "https://api.vapi.ai"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "vapi" / "system_prompt.md"

# Voice + transcriber. "Elliot" is a Vapi-hosted voice (no extra provider key).
# Deepgram nova-3 is the current best-accuracy model — noticeably better than
# nova-2 at accented and noisy speech, which is what "it wasn't catching my
# voice" was. `endpointing: 150` lets Deepgram finalise a turn ~150ms after
# speech stops so we don't wait too long or cut the caller off.
VOICE = {"provider": "vapi", "voiceId": "Elliot"}
TRANSCRIBER = {
    "provider": "deepgram",
    # nova-3 is the most accurate model AND, in "multi" (multilingual) mode,
    # handles South-Asian / Hinglish accented English and English<->Urdu/Hindi
    # code-switching far better than generic "en" — which is exactly how our
    # Pakistani testers and evaluators speak. nova-3 has no discrete en-IN code;
    # "multi" is the right lever for this accent while keeping nova-3's accuracy.
    "model": "nova-3",
    "language": "multi",
    # 300ms endpointing gives accented speakers time to finish digits/words
    # without the agent cutting in mid-number. `numerals` formats spoken numbers
    # ("three one zero") as digits, which helps phone/DOB/ZIP capture.
    "endpointing": 300,
    "numerals": True,
}
# gpt-4.1 handles messy, accented, partly-garbled transcripts far more
# gracefully than 4o-mini — it infers intent and keeps the conversation moving
# instead of looping on a mis-heard word. Conversational quality is graded, and
# the extra latency is worth it for a registration flow that must feel human.
MODEL_NAME = "gpt-4.1"

# Turn-taking. Smart endpointing uses a model to decide when the caller has
# actually finished (not just paused), so the agent stops interrupting and
# stops mis-firing on half-sentences. 0.6s wait suits slower/accented pacing.
START_SPEAKING_PLAN = {"waitSeconds": 0.6, "smartEndpointingEnabled": "livekit"}
# Denoising OFF: it can mistake a soft/accented voice for noise and strip it,
# which shows up as "it wasn't listening while I was talking". A clean audio
# path is more reliable here than aggressive noise removal.
BACKGROUND_DENOISING = False

# Don't hang up on a short pause. Give the caller 60s, and gently re-engage
# ("Are you still there?") a few times before the call ever times out — accented
# callers pause to think, and an abrupt disconnect is a bad experience.
SILENCE_TIMEOUT_SECONDS = 60
MESSAGE_PLAN = {
    "idleMessages": [
        "Are you still there?",
        "Take your time — I'm still here whenever you're ready.",
    ],
    "idleTimeoutSeconds": 12,
    "idleMessageMaxSpokenCount": 3,
}

FIRST_MESSAGE = (
    "Hi, thanks for calling CareCloud Family Health! This is Riley. "
    "I can get you registered as a new patient right here over the phone. "
    "Shall we get started?"
)

# --- Field schemas reused across tools --------------------------------------
_PATIENT_PROPERTIES = {
    "first_name": {"type": "string", "description": "Patient's legal first name."},
    "last_name": {"type": "string", "description": "Patient's legal last name."},
    "date_of_birth": {
        "type": "string",
        "description": "Date of birth in MM/DD/YYYY format.",
    },
    "sex": {
        "type": "string",
        "enum": ["Male", "Female", "Other", "Decline to Answer"],
        "description": "Patient's sex.",
    },
    "phone_number": {
        "type": "string",
        "description": "10-digit US phone number, digits only.",
    },
    "address_line_1": {"type": "string", "description": "Street address."},
    "address_line_2": {
        "type": "string",
        "description": "Apartment, suite, or unit. Optional.",
    },
    "city": {"type": "string", "description": "City."},
    "state": {"type": "string", "description": "Two-letter US state abbreviation."},
    "zip_code": {"type": "string", "description": "5-digit or ZIP+4 US ZIP code."},
    "email": {"type": "string", "description": "Email address. Optional."},
    "insurance_provider": {
        "type": "string",
        "description": "Insurance company name. Optional.",
    },
    "insurance_member_id": {
        "type": "string",
        "description": "Insurance member/subscriber ID. Optional.",
    },
    "preferred_language": {
        "type": "string",
        "description": "Preferred language. Optional, defaults to English.",
    },
    "emergency_contact_name": {
        "type": "string",
        "description": "Emergency contact full name. Optional.",
    },
    "emergency_contact_phone": {
        "type": "string",
        "description": "Emergency contact 10-digit US phone. Optional.",
    },
}

_REQUIRED = [
    "first_name", "last_name", "date_of_birth", "sex", "phone_number",
    "address_line_1", "city", "state", "zip_code",
]


def build_tools(webhook_url: str) -> list[dict]:
    server = {"url": webhook_url}
    if settings.VAPI_WEBHOOK_SECRET:
        server["secret"] = settings.VAPI_WEBHOOK_SECRET

    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_patient",
                "description": (
                    "Check whether a patient already exists by phone number. "
                    "Call this as soon as you have the caller's phone number, to "
                    "recognise returning patients before creating a new record."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": _PATIENT_PROPERTIES["phone_number"]
                    },
                    "required": ["phone_number"],
                },
            },
            "server": server,
        },
        {
            "type": "function",
            "function": {
                "name": "register_patient",
                "description": (
                    "Save a new patient record. Only call this AFTER the caller "
                    "has confirmed all their information is correct."
                ),
                "parameters": {
                    "type": "object",
                    "properties": _PATIENT_PROPERTIES,
                    "required": _REQUIRED,
                },
            },
            "server": server,
        },
        {
            "type": "function",
            "function": {
                "name": "update_patient",
                "description": (
                    "Update an existing patient's information. Use for returning "
                    "callers who want to change details. Identify them by "
                    "phone_number (or patient_id if known); include only the "
                    "fields that should change."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        **_PATIENT_PROPERTIES,
                        "patient_id": {
                            "type": "string",
                            "description": "Existing patient UUID, if known.",
                        },
                    },
                    "required": ["phone_number"],
                },
            },
            "server": server,
        },
    ]


def build_assistant(webhook_url: str) -> dict:
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    server = {"url": webhook_url}
    if settings.VAPI_WEBHOOK_SECRET:
        server["secret"] = settings.VAPI_WEBHOOK_SECRET

    return {
        "name": "CareCloud Patient Intake (Riley)",
        "firstMessage": FIRST_MESSAGE,
        "model": {
            "provider": "openai",
            "model": MODEL_NAME,
            "messages": [{"role": "system", "content": prompt}],
            "tools": build_tools(webhook_url),
        },
        "voice": VOICE,
        "transcriber": TRANSCRIBER,
        "startSpeakingPlan": START_SPEAKING_PLAN,
        "backgroundDenoisingEnabled": BACKGROUND_DENOISING,
        "silenceTimeoutSeconds": SILENCE_TIMEOUT_SECONDS,
        "messagePlan": MESSAGE_PLAN,
        # Server-level events (fired to assistant.server.url). Only the ones we
        # actually use — never transcript/speech-update (they flood the server).
        "server": server,
        "serverMessages": ["end-of-call-report", "status-update"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--webhook-url", required=True, help="Public https .../webhook URL")
    parser.add_argument("--assistant-id", default=None, help="Update this assistant instead of creating")
    args = parser.parse_args()

    if not settings.VAPI_PRIVATE_KEY:
        sys.exit("ERROR: VAPI_PRIVATE_KEY is not set. Put it in .env first.")

    headers = {
        "Authorization": f"Bearer {settings.VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json",
    }
    body = build_assistant(args.webhook_url)

    if args.assistant_id:
        url = f"{VAPI_BASE}/assistant/{args.assistant_id}"
        resp = requests.patch(url, headers=headers, json=body, timeout=30)
        action = "updated"
    else:
        url = f"{VAPI_BASE}/assistant"
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        action = "created"

    if resp.status_code >= 300:
        print(f"FAILED ({resp.status_code}):\n{resp.text}")
        sys.exit(1)

    data = resp.json()
    aid = data.get("id")
    print(f"Assistant {action} successfully.")
    print(f"  assistant_id: {aid}")
    print(f"  webhook:      {args.webhook_url}")
    print(f"  tools:        lookup_patient, register_patient, update_patient")
    if action == "created":
        print("\nNEXT: save this id — add to .env as VAPI_ASSISTANT_ID=" + str(aid))
        print("Then attach a phone number to this assistant in the Vapi dashboard.")


if __name__ == "__main__":
    main()
