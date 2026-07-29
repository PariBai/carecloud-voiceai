"""Vapi server webhook.

Vapi is the ears and mouth; this endpoint is where it reaches into our data.
Only two message types matter:

- `tool-calls`  — SYNCHRONOUS and blocking. The caller hears silence until we
  respond, so handlers are fast and always return a string.
- `end-of-call-report` — fire-and-forget after hangup. We log the transcript
  and final payload for observability.

Everything else (status-update, etc.) is acknowledged and ignored.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.vapi_tools import TOOL_HANDLERS

logger = logging.getLogger("carecloud.webhook")

router = APIRouter(tags=["vapi"])


def _extract_tool_calls(message: dict) -> list[dict]:
    """Vapi has shipped a few shapes for the tool-call list; accept them all."""
    return (
        message.get("toolCallList")
        or message.get("toolCalls")
        or message.get("toolWithToolCallList")
        or []
    )


def _extract_one(tc: dict) -> tuple[str | None, str | None, object]:
    """Pull (id, name, arguments) from one tool-call item, flat or nested."""
    tc_id = tc.get("id") or tc.get("toolCallId")
    fn = tc.get("function") or {}
    name = tc.get("name") or fn.get("name")
    arguments = tc.get("arguments")
    if arguments is None:
        arguments = tc.get("parameters")
    if arguments is None:
        arguments = fn.get("arguments")
    return tc_id, name, arguments


@router.post("/webhook")
async def vapi_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_vapi_secret: str | None = Header(default=None),
):
    # Optional shared-secret check — only enforced if we've configured one.
    if settings.VAPI_WEBHOOK_SECRET and x_vapi_secret != settings.VAPI_WEBHOOK_SECRET:
        logger.warning("Rejected webhook with bad/missing secret")
        return {"results": []}

    body = await request.json()
    message = body.get("message", {}) if isinstance(body, dict) else {}
    mtype = message.get("type")

    if mtype == "tool-calls":
        results = []
        for tc in _extract_tool_calls(message):
            tc_id, name, arguments = _extract_one(tc)
            logger.info("tool-call: name=%s id=%s args=%s", name, tc_id, arguments)
            try:
                handler = TOOL_HANDLERS.get(name)
                if handler is None:
                    result = "I'm sorry, I can't do that right now."
                else:
                    result = handler(db, arguments)
            except Exception:  # last-resort guard: never 500 into a live call
                logger.exception("Handler crashed for tool %s", name)
                result = (
                    "I'm sorry, something went wrong on my end. "
                    "Could you say that once more?"
                )
            results.append({"toolCallId": tc_id, "result": result})
        return {"results": results}

    if mtype == "end-of-call-report":
        # Fire-and-forget: persist-to-log for observability. `transcript` is
        # duplicated at message.transcript and message.artifact.transcript.
        call = message.get("call", {}) or {}
        transcript = message.get("transcript") or message.get("artifact", {}).get(
            "transcript"
        )
        logger.info(
            "end-of-call-report: call_id=%s duration=%ss ended=%s",
            call.get("id"),
            message.get("durationSeconds"),
            message.get("endedReason"),
        )
        if transcript:
            logger.info("transcript: %s", transcript)
        return {"received": True}

    # status-update and anything else — acknowledge and move on.
    logger.debug("Ignored webhook message type: %s", mtype)
    return {"received": True}
