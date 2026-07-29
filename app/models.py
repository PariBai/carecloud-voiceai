"""SQLAlchemy ORM model for a patient record.

Design notes
------------
- `patient_id` is a UUID string (portable across DB engines, and safe to read
  aloud / expose in URLs without leaking a sequential count of patients).
- `date_of_birth` is stored as a real DATE, not text — so "not in the future"
  and range queries are correct. The API/voice layer speaks MM/DD/YYYY and
  converts at the boundary.
- `sex` is constrained at the database level (CHECK) to the four allowed
  values, so a bad write is rejected even if it bypasses the API validators.
- Soft delete: `deleted_at` is set instead of removing the row. Every read
  filters out soft-deleted rows. The challenge explicitly forbids hard delete.
- `created_at` / `updated_at` are UTC and maintained by the ORM.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SEX_VALUES = ("Male", "Female", "Other", "Decline to Answer")


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"

    __table_args__ = (
        CheckConstraint(
            "sex IN ('Male', 'Female', 'Other', 'Decline to Answer')",
            name="ck_patients_sex",
        ),
    )

    # --- Identity -----------------------------------------------------------
    patient_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )

    # --- Required demographics ---------------------------------------------
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False)
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # --- Optional demographics ---------------------------------------------
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insurance_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurance_member_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_language: Mapped[str] = mapped_column(
        String(50), nullable=False, default="English"
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # --- Bookkeeping --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
