"""Opt-in access control for destructive data-service administration."""

import os
import secrets
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
_bearer = HTTPBearer(auto_error=False)


def require_raster_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
):
    if os.getenv("RS_ENABLE_ADMIN_OPERATIONS", "false").strip().lower() != "true":
        raise HTTPException(status_code=404, detail="Admin operations are disabled")
    expected = os.getenv("RS_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin token is not configured")
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid administrator credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
