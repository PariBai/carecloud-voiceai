"""Pydantic schemas — the API's request/response contract.

The same `validators` used by the voice layer run here too, so a record created
via `POST /patients` is validated identically to one created over the phone.
Invalid input raises a `ValidationError` (a `ValueError`), which Pydantic
surfaces as a 422 with a field-specific, human-readable message.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app import validators as v


class PatientCreate(BaseModel):
    """Payload to register a new patient. Required fields mirror the brief."""

    # Required
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    address_line_1: str
    city: str
    state: str
    zip_code: str

    # Optional
    email: Optional[str] = None
    address_line_2: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: str = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # --- Normalising validators (run before type coercion) -----------------
    @field_validator("first_name", mode="before")
    @classmethod
    def _first(cls, val):
        return v.validate_name(val, field="first_name")

    @field_validator("last_name", mode="before")
    @classmethod
    def _last(cls, val):
        return v.validate_name(val, field="last_name")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _dob(cls, val):
        return v.validate_date_of_birth(val)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, val):
        return v.validate_sex(val)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _phone(cls, val):
        return v.normalize_phone(val)

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def _ec_phone(cls, val):
        if val is None or not str(val).strip():
            return None
        return v.normalize_phone(val, field="emergency_contact_phone")

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, val):
        return v.validate_email(val)

    @field_validator("state", mode="before")
    @classmethod
    def _state(cls, val):
        return v.validate_state(val)

    @field_validator("zip_code", mode="before")
    @classmethod
    def _zip(cls, val):
        return v.validate_zip(val)

    @field_validator("city", mode="before")
    @classmethod
    def _city(cls, val):
        return v.validate_city(val)


class PatientUpdate(BaseModel):
    """Partial update — every field optional. Only provided fields change."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    email: Optional[str] = None
    address_line_2: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _names(cls, val, info):
        return None if val is None else v.validate_name(val, field=info.field_name)

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _dob(cls, val):
        return None if val is None else v.validate_date_of_birth(val)

    @field_validator("sex", mode="before")
    @classmethod
    def _sex(cls, val):
        return None if val is None else v.validate_sex(val)

    @field_validator("phone_number", mode="before")
    @classmethod
    def _phone(cls, val):
        return None if val is None else v.normalize_phone(val)

    @field_validator("emergency_contact_phone", mode="before")
    @classmethod
    def _ec_phone(cls, val):
        if val is None or not str(val).strip():
            return None
        return v.normalize_phone(val, field="emergency_contact_phone")

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, val):
        return v.validate_email(val)

    @field_validator("state", mode="before")
    @classmethod
    def _state(cls, val):
        return None if val is None else v.validate_state(val)

    @field_validator("zip_code", mode="before")
    @classmethod
    def _zip(cls, val):
        return None if val is None else v.validate_zip(val)

    @field_validator("city", mode="before")
    @classmethod
    def _city(cls, val):
        return None if val is None else v.validate_city(val)


class PatientOut(BaseModel):
    """Response shape. DOB is rendered back as MM/DD/YYYY for readability."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    state: str
    zip_code: str
    email: Optional[str]
    insurance_provider: Optional[str]
    insurance_member_id: Optional[str]
    preferred_language: str
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    @field_serializer("date_of_birth")
    def _dob_out(self, value: date) -> str:
        return value.strftime("%m/%d/%Y")
