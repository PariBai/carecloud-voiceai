"""REST endpoints for patient records.

    GET    /patients          list (filter by last_name, date_of_birth, phone_number)
    GET    /patients/{id}     fetch one
    POST   /patients          create
    PUT    /patients/{id}     partial update
    DELETE /patients/{id}     soft delete

Validation happens in the Pydantic schemas (shared with the voice layer); the
router's job is HTTP status codes and the response envelope.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.responses import err, ok
from app.schemas import PatientCreate, PatientOut, PatientUpdate
from app.validators import ValidationError, validate_date_of_birth, normalize_phone

router = APIRouter(prefix="/patients", tags=["patients"])


def _serialize(patient) -> dict:
    return PatientOut.model_validate(patient).model_dump(mode="json")


@router.get("")
def list_patients(
    db: Session = Depends(get_db),
    last_name: str | None = Query(default=None),
    date_of_birth: str | None = Query(default=None),
    phone_number: str | None = Query(default=None),
):
    # Normalise filter inputs the same way we store them, so filters actually
    # match. Bad filter values are a 400, not a 500.
    dob: date | None = None
    try:
        if date_of_birth:
            dob = validate_date_of_birth(date_of_birth)
        phone = normalize_phone(phone_number) if phone_number else None
    except ValidationError as e:
        return err(e.message, code="invalid_filter", status_code=400, field=e.field)

    patients = crud.list_patients(
        db, last_name=last_name, date_of_birth=dob, phone_number=phone
    )
    return ok([_serialize(p) for p in patients])


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        return err("Patient not found.", code="not_found", status_code=404)
    return ok(_serialize(patient))


@router.post("")
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    patient = crud.create_patient(db, payload.model_dump())
    return ok(_serialize(patient), status_code=201)


@router.put("/{patient_id}")
def update_patient(
    patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)
):
    # Only fields actually supplied are updated (true partial update).
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return err(
            "No fields provided to update.",
            code="empty_update",
            status_code=400,
        )
    patient = crud.update_patient(db, patient_id, changes)
    if patient is None:
        return err("Patient not found.", code="not_found", status_code=404)
    return ok(_serialize(patient))


@router.delete("/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.soft_delete_patient(db, patient_id)
    if patient is None:
        return err("Patient not found.", code="not_found", status_code=404)
    return ok(_serialize(patient))
