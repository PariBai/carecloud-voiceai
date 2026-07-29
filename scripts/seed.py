"""Seed 1-2 demo patients so the API has something to show immediately.

Idempotent: skips a patient if one with the same phone already exists. Run:
    python -m scripts.seed
"""
from __future__ import annotations

from app.database import SessionLocal, init_db
from app import crud
from app.schemas import PatientCreate

DEMO_PATIENTS = [
    {
        "first_name": "Jane", "last_name": "Doe", "date_of_birth": "04/12/1985",
        "sex": "Female", "phone_number": "4155550142",
        "address_line_1": "123 Market Street", "city": "San Francisco",
        "state": "CA", "zip_code": "94103", "email": "jane.doe@example.com",
        "preferred_language": "English",
    },
    {
        "first_name": "John", "last_name": "Smith", "date_of_birth": "11/30/1972",
        "sex": "Male", "phone_number": "2125550188",
        "address_line_1": "500 5th Avenue", "address_line_2": "Apt 12B",
        "city": "New York", "state": "NY", "zip_code": "10018",
        "insurance_provider": "Blue Cross", "insurance_member_id": "BC123456789",
    },
]


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        for raw in DEMO_PATIENTS:
            payload = PatientCreate(**raw)
            if crud.find_by_phone(db, payload.phone_number):
                print(f"skip: {raw['first_name']} {raw['last_name']} (exists)")
                continue
            p = crud.create_patient(db, payload.model_dump())
            print(f"seeded: {p.first_name} {p.last_name} -> {p.patient_id}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
