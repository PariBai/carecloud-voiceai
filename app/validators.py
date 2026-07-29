"""Field-level validation and normalisation.

These are the single source of truth for "is this value acceptable", used by
BOTH the REST API (server-side validation, as required) and the voice tool
handlers. Each function either returns a cleaned value or raises `ValidationError`
with a message that is safe to read aloud to a caller.

Voice input is messy: callers say "California" not "CA", "(555) 123-4567" not
"5551234567", and dates in a dozen shapes. We normalise aggressively so the
same spoken answer always lands as the same stored value.
"""
from __future__ import annotations

import re
from datetime import date, datetime

# --- U.S. states ------------------------------------------------------------
US_STATES: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
STATE_ABBRS: set[str] = set(US_STATES.values())

SEX_CANONICAL = {
    "male": "Male", "m": "Male",
    "female": "Female", "f": "Female",
    "other": "Other",
    "decline to answer": "Decline to Answer", "decline": "Decline to Answer",
    "prefer not to say": "Decline to Answer",
}

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\-' ]{0,49}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


class ValidationError(ValueError):
    """Raised when a field fails validation. `message` is caller-safe."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)


def validate_name(value: str, *, field: str) -> str:
    v = (value or "").strip()
    if not _NAME_RE.match(v):
        raise ValidationError(
            field,
            f"That {field.replace('_', ' ')} doesn't look right. It should be "
            "letters only, up to 50 characters.",
        )
    return v


def validate_date_of_birth(value: str | date) -> date:
    """Accept a date object or a string in several common shapes.

    Rejects future dates and implausibly old ones. Returns a `date`.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        dob = value
    else:
        raw = str(value).strip()
        dob = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
            try:
                dob = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue
        if dob is None:
            raise ValidationError(
                "date_of_birth",
                "I didn't catch a valid date of birth. Please say it as month, "
                "day, and year.",
            )

    today = date.today()
    if dob > today:
        raise ValidationError(
            "date_of_birth",
            "A date of birth can't be in the future. Could you say it again?",
        )
    if dob.year < 1900:
        raise ValidationError(
            "date_of_birth",
            "That date of birth seems too far in the past. Could you repeat it?",
        )
    return dob


def validate_sex(value: str) -> str:
    key = (value or "").strip().lower()
    if key in SEX_CANONICAL:
        return SEX_CANONICAL[key]
    raise ValidationError(
        "sex",
        "For sex, I can record Male, Female, Other, or Decline to Answer. "
        "Which would you like?",
    )


def normalize_phone(value: str, *, field: str = "phone_number") -> str:
    """Reduce any spoken/typed phone to 10 U.S. digits, or raise."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValidationError(
            field,
            "That doesn't look like a valid 10-digit U.S. phone number. "
            "Could you say it one more time?",
        )
    if digits[0] in "01":
        raise ValidationError(
            field,
            "A U.S. phone number can't start with a zero or one. "
            "Could you repeat it?",
        )
    return digits


def validate_email(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    v = str(value).strip().lower().replace(" at ", "@").replace(" dot ", ".")
    if not _EMAIL_RE.match(v):
        raise ValidationError(
            "email", "That email address doesn't look valid. Could you spell it out?"
        )
    return v


def validate_state(value: str) -> str:
    v = (value or "").strip()
    if len(v) == 2 and v.upper() in STATE_ABBRS:
        return v.upper()
    if v.lower() in US_STATES:
        return US_STATES[v.lower()]
    raise ValidationError(
        "state", "I need a valid U.S. state. Which state are you in?"
    )


def validate_zip(value: str) -> str:
    v = (value or "").strip()
    if not _ZIP_RE.match(v):
        raise ValidationError(
            "zip_code",
            "That ZIP code doesn't look right. It should be five digits. "
            "Could you say it again?",
        )
    return v


def validate_city(value: str) -> str:
    v = (value or "").strip()
    if not (1 <= len(v) <= 100):
        raise ValidationError("city", "Could you tell me the city again?")
    return v


def clean_text(value: str | None, *, max_len: int) -> str | None:
    """Trim a free-text optional field, return None if empty."""
    if value is None:
        return None
    v = str(value).strip()
    return v[:max_len] if v else None
