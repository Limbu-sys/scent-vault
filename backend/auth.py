"""Telegram init data validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.parse

from fastapi import HTTPException, Request

from config import ALLOW_LOCAL_DEV, PRODUCTION_MODE, TELEGRAM_BOT_TOKEN


def verify_telegram_init_data(init_data: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        return True
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, received_hash)


def require_telegram_auth(request: Request) -> None:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        if TELEGRAM_BOT_TOKEN and not verify_telegram_init_data(init_data):
            raise HTTPException(status_code=403, detail="invalid_telegram_auth")
        return
    if PRODUCTION_MODE and not ALLOW_LOCAL_DEV:
        raise HTTPException(status_code=401, detail="telegram_required")


def parse_telegram_user(request: Request) -> tuple[str, str]:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        if ALLOW_LOCAL_DEV or not PRODUCTION_MODE:
            dev_id = request.headers.get("X-Dev-User-Id", "122429011")
            return dev_id, "Dev"
        raise HTTPException(status_code=401, detail="telegram_required")
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    raw_user = parsed.get("user")
    if not raw_user:
        raise HTTPException(status_code=401, detail="telegram_user_missing")
    try:
        user = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_user_json") from exc
    uid = str(user.get("id") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="telegram_user_missing")
    name = (user.get("first_name") or user.get("username") or "User").strip()
    return uid, name


def telegram_init_header(request: Request) -> dict[str, str]:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        return {"X-Telegram-Init-Data": init_data}
    if ALLOW_LOCAL_DEV or not PRODUCTION_MODE:
        return {"X-Dev-User-Id": request.headers.get("X-Dev-User-Id", "122429011")}
    return {}
