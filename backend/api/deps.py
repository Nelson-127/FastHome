"""FastAPI dependencies: auth, optional internal API key."""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import get_settings

security = HTTPBasic()


async def require_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.internal_api_key:
        return
    if not x_internal_key or not secrets.compare_digest(x_internal_key, settings.internal_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing internal key")


async def verify_admin_basic(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    settings = get_settings()
    ok_user = secrets.compare_digest(credentials.username, settings.admin_username)
    ok_pass = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})
    return credentials.username
