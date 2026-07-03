"""Product catalog — volumes, pricing, enrichment."""

from __future__ import annotations

from suppliers import CATALOG_SEED, SEED_PRODUCTS, SEED_SUPPLIERS, SUPPLIER_MAP

VOLUMES_ML = [1, 2, 3, 5, 10]

VOLUME_MULTIPLIERS = {
    1: 1.0,
    2: 1.85,
    3: 2.65,
    5: 4.2,
    10: 7.5,
}


def price_for_volume(base_price_per_ml: float, volume_ml: int) -> int:
    mult = VOLUME_MULTIPLIERS.get(volume_ml, volume_ml * 0.95)
    return int(round(base_price_per_ml * mult))


def enrich_product(product: dict) -> dict:
    p = dict(product)
    p["volumes"] = [
        {
            "ml": v,
            "price": int(round(p["base_price_per_ml"] * VOLUME_MULTIPLIERS[v])),
        }
        for v in VOLUMES_ML
    ]
    stock = int(p.get("stock_ml", 0))
    p["stock_ml"] = stock
    p["in_stock"] = stock > 0
    sid = p.get("supplier_id")
    if sid and sid in SUPPLIER_MAP:
        s = SUPPLIER_MAP[sid]
        p["supplier"] = {
            "id": s["id"],
            "name": s["name"],
            "country": s["country"],
            "has_certificate": s["has_quality_certificate"],
            "honest_sign": s["honest_sign"],
        }
    return p
