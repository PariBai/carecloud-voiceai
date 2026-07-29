"""Voice tool handlers.

Each function takes the arguments Vapi extracted from the conversation and
returns a plain string that is read aloud to the caller. Golden rules:

- Never raise. An unhandled exception becomes a 500, and a 500 is dead silence
  in the caller's ear. Every handler returns a sentence a receptionist could say.
- Validation reuses the exact same schemas as the REST API, so a phone
  registration is validated identically to an API one. On a bad field we return
  a specific re-prompt so the agent asks again for just that field.
- Arguments come from a non-deterministic model, so we read them defensively
  (key aliases, JSON-string values).
"""
from __future__ import annotations

import json
import logging

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app import crud
from app.schemas import PatientCreate, PatientUpdate

logger = logging.getLogger("carecloud.tools")

# Accept common aliases the model might emit for our canonical field names.
_ALIASES = {
    "dob": "date_of_birth",
    "birthdate": "date_of_birth",
    "birth_date": "date_of_birth",
    "phone": "phone_number",
    "phone_no": "phone_number",
    "zip": "zip_code",
    "zipcode": "zip_code",
    "postal_code": "zip_code",
    "gender": "sex",
    "address": "address_line_1",
    "address1": "address_line_1",
    "address2": "address_line_2",
    "language": "preferred_language",
}


def _normalize_args(arguments) -> dict:
    """Coerce the incoming arguments into a plain dict with canonical keys."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            arguments = {}
    if not isinstance(arguments, dict):
        return {}
    out: dict = {}
    for key, value in arguments.items():
        canonical = _ALIASES.get(key, key)
        # Treat empty strings / "null" as absent so optional fields stay optional.
        if value in ("", "null", "none", "N/A", "n/a"):
            continue
        out[canonical] = value
    return out


def _first_error_message(exc: PydanticValidationError) -> str:
    """Extract our caller-safe message from a Pydantic validation error."""
    err = exc.errors()[0]
    if err.get("type") == "missing":
        field = str(err.get("loc", ["that field"])[-1]).replace("_", " ")
        return f"I still need your {field}. Could you tell me that?"
    return err.get("msg", "Something about that wasn't valid.").replace(
        "Value error, ", ""
    )


# --- Tool: lookup_patient ---------------------------------------------------
def handle_lookup_patient(db: Session, arguments) -> str:
    args = _normalize_args(arguments)
    raw_phone = args.get("phone_number")
    if not raw_phone:
        return "Sure — what's the best phone number for you?"
    try:
        from app.validators import normalize_phone

        phone = normalize_phone(str(raw_phone))
    except Exception:
        return "I didn't catch a valid phone number. Could you say it again?"

    existing = crud.find_by_phone(db, phone)
    if existing:
        return (
            f"EXISTING_RECORD_FOUND: We already have a record for "
            f"{existing.first_name} {existing.last_name}. Ask if they'd like to "
            f"update their existing information instead of creating a new record."
        )
    return "NO_EXISTING_RECORD: No patient on file with that number. Proceed to collect their details."


# --- Tool: register_patient -------------------------------------------------
def handle_register_patient(db: Session, arguments) -> str:
    args = _normalize_args(arguments)
    try:
        payload = PatientCreate(**args)
    except PydanticValidationError as exc:
        return _first_error_message(exc)

    # Duplicate detection (bonus): don't silently create a second record.
    existing = crud.find_by_phone(db, payload.phone_number)
    if existing:
        return (
            f"It looks like we already have a record for {existing.first_name} "
            f"{existing.last_name} at that phone number. Would you like to update "
            f"your existing information instead?"
        )

    try:
        patient = crud.create_patient(db, payload.model_dump())
    except Exception:
        logger.exception("DB write failed during register_patient")
        return (
            "I'm sorry, I couldn't save your information just now. "
            "Please try again in a moment."
        )

    # Observability: log the final collected payload (no full record read aloud).
    logger.info("Registered patient %s (%s %s)", patient.patient_id,
                patient.first_name, patient.last_name)
    return (
        f"You're all set, {patient.first_name}. Your registration is complete "
        f"and saved. Is there anything else I can help you with?"
    )


# --- Tool: update_patient ---------------------------------------------------
def handle_update_patient(db: Session, arguments) -> str:
    args = _normalize_args(arguments)
    patient_id = args.pop("patient_id", None)
    phone = args.get("phone_number")

    patient = None
    if patient_id:
        patient = crud.get_patient(db, str(patient_id))
    if patient is None and phone:
        try:
            from app.validators import normalize_phone

            patient = crud.find_by_phone(db, normalize_phone(str(phone)))
        except Exception:
            patient = None
    if patient is None:
        return "I couldn't find an existing record to update. Shall I create a new one instead?"

    try:
        changes = PatientUpdate(**args).model_dump(exclude_unset=True)
    except PydanticValidationError as exc:
        return _first_error_message(exc)

    if not changes:
        return "What would you like me to update?"

    try:
        updated = crud.update_patient(db, patient.patient_id, changes)
    except Exception:
        logger.exception("DB write failed during update_patient")
        return "I'm sorry, I couldn't update your information just now. Please try again."

    return f"Done — I've updated your information, {updated.first_name}. Anything else?"


# Dispatch table used by the webhook.
TOOL_HANDLERS = {
    "lookup_patient": handle_lookup_patient,
    "register_patient": handle_register_patient,
    "update_patient": handle_update_patient,
}
