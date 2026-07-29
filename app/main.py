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
from fastapi.responses import HTMLResponse

from app.config import settings
from app.database import init_db
from app.responses import err
from app.routers import dashboard, patients, vapi

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
app.include_router(dashboard.router)


@app.get("/", response_class=HTMLResponse, tags=["meta"])
def index():
    """Human-friendly landing page so the base URL isn't a bare 404."""
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CareCloud Patient Registration API</title>
<style>
  body{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:640px;margin:6vh auto;padding:0 20px;color:#1a2233;line-height:1.55}
  h1{font-size:1.5rem;margin-bottom:.25rem}.tag{color:#5a6b8c}
  code{background:#eef2f8;padding:2px 6px;border-radius:5px}
  a{color:#2456c6;text-decoration:none}a:hover{text-decoration:underline}
  li{margin:.35rem 0}.ok{color:#178a4c;font-weight:600}
</style></head><body>
<h1>CareCloud — Patient Registration API</h1>
<p class="tag">Voice AI intake agent &middot; status: <span class="ok">live</span></p>
<p>Call the agent at <strong>+1 (346) 292-9312</strong> to register a patient by voice.</p>
<p>&rarr; <a href="/dashboard"><strong>Open the patients dashboard</strong></a> for a friendly table view.</p>
<h3>Endpoints</h3>
<ul>
  <li><a href="/dashboard">/dashboard</a> &mdash; web UI (searchable patient table)</li>
  <li><a href="/patients">/patients</a> &mdash; list all patients as JSON (filters: <code>?last_name=</code>, <code>?date_of_birth=</code>, <code>?phone_number=</code>)</li>
  <li><code>/patients/{id}</code> &mdash; one patient</li>
  <li><code>POST /patients</code> &middot; <code>PUT /patients/{id}</code> &middot; <code>DELETE /patients/{id}</code> (soft-delete)</li>
  <li><a href="/health">/health</a> &mdash; liveness</li>
  <li><a href="/docs">/docs</a> &mdash; interactive API docs</li>
</ul>
</body></html>"""


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
