"""Telegram Bot API setup (menu button, etc.)."""

from __future__ import annotations

import logging

import httpx

from config import APP_PUBLIC_URL, TELEGRAM_BOT_TOKEN

log = logging.getLogger("scent-vault.telegram")


async def setup_telegram_mini_app() -> bool:
    """Set default Menu Button → Web App. Called on every server start."""
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN missing — skip menu button")
        return False
    if not APP_PUBLIC_URL:
        log.warning("APP_PUBLIC_URL missing — skip menu button")
        return False

    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "🛍 Магазин",
            "web_app": {"url": APP_PUBLIC_URL},
        }
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{api}/setChatMenuButton", json=payload)
            data = r.json()
            if not data.get("ok"):
                log.error("setChatMenuButton failed: %s", data)
                return False
            log.info("Menu button set → %s", APP_PUBLIC_URL)
            return True
    except Exception as exc:
        log.error("telegram setup failed: %s", exc)
        return False
