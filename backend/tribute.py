"""Tribute payment webhook."""

from __future__ import annotations

import hmac
from typing import Any

from config import TRIBUTE_API_KEY
from db import get_db


def verify_tribute_signature(body: bytes, signature: str | None) -> bool:
    if not TRIBUTE_API_KEY:
        return True
    if not signature:
        return False
    computed = hmac.new(TRIBUTE_API_KEY.encode(), body, digestmod="sha256").hexdigest()
    return hmac.compare_digest(computed, signature)


def process_tribute_webhook(data: dict[str, Any]) -> dict[str, Any]:
    event = str(data.get("name", "")).replace("-", "_").lower()
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "invalid_payload"}

    metadata = payload.get("metadata")
    order_id = payload.get("order_id") or payload.get("orderId") or payload.get("custom_order_id")
    if not order_id and isinstance(metadata, dict):
        order_id = metadata.get("order_id")
    if not order_id and payload.get("comment"):
        comment = str(payload["comment"])
        if comment.startswith("#"):
            order_id = comment.lstrip("#").split()[0]

    paid_events = {
        "new_order",
        "order_paid",
        "payment_success",
        "new_donation",
        "donation_paid",
        "new_digital_product",
        "digital_product_paid",
    }
    if event in paid_events or "paid" in event:
        if order_id:
            order = get_db().mark_order_paid(str(order_id).upper())
            if order:
                return {"ok": True, "action": "paid", "order_id": order_id}
        return {"ok": True, "skipped": "no_order_id"}

    return {"ok": True, "skipped": event or "unknown"}
