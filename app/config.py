"""Central configuration.

Every secret and tunable lives here and is read from the environment (loaded
from a local .env in development). Nothing sensitive is hardcoded — the
challenge explicitly requires API keys to come from environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env sitting at the project root, if present. In production (systemd)
# the same variables are provided by the service environment instead.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings, resolved once at import time."""

    # --- Database -----------------------------------------------------------
    # SQLite file lives under data/ so it survives restarts (persistence is a
    # hard requirement). Override with DATABASE_URL for Postgres if ever needed.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'data' / 'patients.db').as_posix()}",
    )

    # --- Vapi ---------------------------------------------------------------
    # Private (server) key — used only by our setup script to create the
    # assistant/tools. Never shipped to the client.
    VAPI_PRIVATE_KEY: str = os.getenv("VAPI_PRIVATE_KEY", "")
    # Optional shared secret: Vapi can sign webhooks with a header we verify,
    # so random internet traffic can't POST fake patients to our webhook.
    VAPI_WEBHOOK_SECRET: str = os.getenv("VAPI_WEBHOOK_SECRET", "")

    # --- App ----------------------------------------------------------------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    APP_NAME: str = "CareCloud Patient Registration API"


settings = Settings()
