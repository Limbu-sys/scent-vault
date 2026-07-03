"""Configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
DB_PATH = DATA_DIR / "scent_vault.db"
UPLOADS_DIR = DATA_DIR / "uploads"
PORT = int(os.getenv("PORT", "8781"))
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() in {"1", "true", "yes"}
ALLOW_LOCAL_DEV = os.getenv("ALLOW_LOCAL_DEV", "false").lower() in {"1", "true", "yes"}
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "").rstrip("/")
TRIBUTE_API_KEY = os.getenv("TRIBUTE_API_KEY", "")
TRIBUTE_SHOP_URL = os.getenv("TRIBUTE_SHOP_URL", "")
WAREHOUSE_CITY = os.getenv("WAREHOUSE_CITY", "Краснодар")

LEGAL_SELF_EMPLOYED_NAME = os.getenv("LEGAL_SELF_EMPLOYED_NAME", "")
LEGAL_INN = os.getenv("LEGAL_INN", "")
LEGAL_CONTACT_EMAIL = os.getenv("LEGAL_CONTACT_EMAIL", "dvetochkiinfo@gmail.com")
LEGAL_PHONE = os.getenv("LEGAL_PHONE", "")
LEGAL_ADDRESS = os.getenv("LEGAL_ADDRESS", "")

_default_admins = os.getenv("ADMIN_TELEGRAM_IDS", "122429011")
ADMIN_TELEGRAM_IDS = {x.strip() for x in _default_admins.split(",") if x.strip()}

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
