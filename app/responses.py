"""Consistent JSON envelope helpers.

Every API response uses the shape required by the brief:
    { "data": <payload-or-null>, "error": <null-or-{code,message,field?}> }
Centralising it here means no endpoint can drift from the contract.
"""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def ok(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": jsonable_encoder(data), "error": None},
    )


def err(
    message: str,
    *,
    code: str,
    status_code: int,
    field: str | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if field is not None:
        error["field"] = field
    return JSONResponse(
        status_code=status_code,
        content={"data": None, "error": error},
    )
