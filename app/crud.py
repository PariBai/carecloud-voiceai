"""Data-access layer.

All database reads/writes live here so the routers and the voice webhook share
one code path (and one place to reason about soft-delete filtering). Every read
excludes soft-deleted rows.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Patient


def _active(stmt):
    """Restrict a select() to non-soft-deleted rows."""
    return stmt.where(Patient.deleted_at.is_(None))


def create_patient(db: Session, data: dict) -> Patient:
    patient = Patient(**data)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: str) -> Patient | None:
    stmt = _active(select(Patient).where(Patient.patient_id == patient_id))
    return db.execute(stmt).scalar_one_or_none()


def find_by_phone(db: Session, phone_number: str) -> Patient | None:
    """Used for duplicate detection — most recent active match wins."""
    stmt = _active(
        select(Patient)
        .where(Patient.phone_number == phone_number)
        .order_by(Patient.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def list_patients(
    db: Session,
    *,
    last_name: str | None = None,
    date_of_birth: date | None = None,
    phone_number: str | None = None,
) -> list[Patient]:
    stmt = _active(select(Patient))
    if last_name:
        stmt = stmt.where(Patient.last_name.ilike(last_name.strip()))
    if date_of_birth:
        stmt = stmt.where(Patient.date_of_birth == date_of_birth)
    if phone_number:
        stmt = stmt.where(Patient.phone_number == phone_number)
    stmt = stmt.order_by(Patient.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def update_patient(db: Session, patient_id: str, data: dict) -> Patient | None:
    patient = get_patient(db, patient_id)
    if patient is None:
        return None
    for key, value in data.items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    return patient


def soft_delete_patient(db: Session, patient_id: str) -> Patient | None:
    patient = get_patient(db, patient_id)
    if patient is None:
        return None
    patient.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(patient)
    return patient
