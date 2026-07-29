"""FastAPI application entry point.

Wires together the REST API and the Vapi webhook, initialises the database on
startup, and guarantees every response — including framework-level validation
and unexpected errors — uses the `{data, error}` envelope.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import init_db
from app.responses import err
from app.routers import patients, vapi

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("carecloud")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("Database initialised; API ready.")
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.include_router(patients.router)
app.include_router(vapi.router)


@app.get("/health", tags=["meta"])
def health():
    """Liveness probe — the first thing to hit after deploy/tunnel."""
    return {"data": {"status": "ok"}, "error": None}


# --- Envelope-consistent error handling ------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError):
    """Turn Pydantic/validator failures into a caller-friendly 422 envelope.

    Our field validators raise `ValueError("...caller-safe message...")`, which
    Pydantic prefixes with "Value error, ". We strip that and surface the field.
    """
    first = exc.errors()[0]
    loc = first.get("loc", [])
    field = str(loc[-1]) if loc else None
    msg = first.get("msg", "Invalid input.")
    if first.get("type") == "missing":
        msg = f"The field '{field}' is required."
    else:
        msg = msg.replace("Value error, ", "")
    return err(msg, code="validation_error", status_code=422, field=field)


@app.exception_handler(Exception)
async def unhandled_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return err(
        "Something went wrong on our end.",
        code="internal_error",
        status_code=500,
    )
