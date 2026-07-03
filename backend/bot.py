"""Telegram bot: Menu Button + welcome."""

from __future__ import annotations

import logging

from telegram import (
    BotCommand,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import Application, CommandHandler, ContextTypes

from config import APP_PUBLIC_URL, TELEGRAM_BOT_TOKEN, WAREHOUSE_CITY
from telegram_setup import setup_telegram_mini_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scent-vault-bot")


def _keyboard() -> ReplyKeyboardMarkup | None:
    if not APP_PUBLIC_URL:
        return None
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🛍 Открыть магазин", web_app=WebAppInfo(url=APP_PUBLIC_URL))]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    text = (
        "<b>Scent Vault</b> — парфюм известных брендов на розлив.\n\n"
        "Оригинальные ароматы с официальных флаконов.\n"
        f"📍 Склад: {WAREHOUSE_CITY}\n"
        "🚚 Доставка по России\n\n"
        "Нажмите кнопку <b>«🛍 Открыть магазин»</b> ниже\n"
        "или кнопку меню слева от поля ввода."
    )
    await update.message.reply_html(text, reply_markup=_keyboard())


async def post_init(application: Application) -> None:
    bot = application.bot
    await bot.set_my_commands([
        BotCommand("start", "Открыть магазин"),
    ])
    await setup_telegram_mini_app()


def run_bot() -> None:
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")
        return
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    log.info("Bot polling started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run_bot()
