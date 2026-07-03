"""Telegram notifications for orders."""

from __future__ import annotations

import logging

import httpx

from config import ADMIN_TELEGRAM_IDS, TELEGRAM_BOT_TOKEN
from db import get_db

log = logging.getLogger("scent-vault.notify")


async def send_telegram_message(chat_id: str | int, text: str, parse_mode: str = "HTML") -> bool:
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            )
            return r.is_success
    except Exception as exc:
        log.warning("telegram send failed: %s", exc)
        return False


async def notify_admins_new_order(order: dict) -> None:
    lines = [
        f"<b>Новый заказ #{order['id']}</b>",
        f"Сумма: {order['subtotal_rub']} ₽",
        f"Клиент: {order.get('telegram_username') or order.get('telegram_user_id')}",
        f"{order.get('city')}, {order.get('address')}",
        "",
        "<b>Товары:</b>",
    ]
    for it in order.get("items", []):
        lines.append(f"• {it.get('sku')} {it['brand']} {it['name']} — {it['volume_ml']}мл ×{it['qty']}")
    lines.append(f"\nДоставка (~): {order.get('delivery_estimate_rub')} ₽ ({order.get('delivery_method')})")
    if order.get("payment_url"):
        lines.append(f"\n💳 <a href=\"{order['payment_url']}\">Оплатить в Tribute</a>")
    lines.append(f"\n⚠️ Комментарий к оплате: <code>#{order['id']}</code>")
    text = "\n".join(lines)
    for admin_id in ADMIN_TELEGRAM_IDS:
        await send_telegram_message(admin_id, text)
    db_admins = get_db().list_admins()
    for aid in db_admins:
        if aid not in ADMIN_TELEGRAM_IDS:
            await send_telegram_message(aid, text)


async def notify_user_order_status(order: dict, user_id: str) -> None:
    status_labels = {
        "paid": "✅ Оплачен",
        "processing": "📦 Собирается",
        "shipped": "🚚 Отправлен",
        "delivered": "🎉 Доставлен",
        "cancelled": "❌ Отменён",
    }
    label = status_labels.get(order["status"], order["status"])
    text = f"<b>Заказ #{order['id']}</b>\nСтатус: {label}"
    await send_telegram_message(user_id, text)
