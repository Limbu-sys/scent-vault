"""Admin access control."""

from __future__ import annotations

from fastapi import HTTPException, Request

from auth import parse_telegram_user, require_telegram_auth
from db import get_db


def is_admin_user(user_id: str) -> bool:
    return get_db().is_admin(str(user_id))


def require_admin(request: Request) -> str:
    require_telegram_auth(request)
    uid, _ = parse_telegram_user(request)
    if not is_admin_user(uid):
        raise HTTPException(status_code=403, detail="admin_required")
    return uid
