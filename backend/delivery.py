"""Delivery cost estimation from Krasnodar warehouse."""

from __future__ import annotations

from config import WAREHOUSE_CITY

# Zone codes for tariff lookup
ZONE_KRASNODAR_CITY = "krasnodar_city"
ZONE_KRASNODAR_REGION = "krasnodar_region"
ZONE_SOUTH = "south_russia"
ZONE_CENTRAL = "central_russia"
ZONE_URAL_SIBERIA = "ural_siberia"
ZONE_FAR_EAST = "far_east"

DELIVERY_METHODS = {
    "cdek_pvz": {
        "id": "cdek_pvz",
        "name_ru": "СДЭК — пункт выдачи",
        "name_en": "CDEK pickup point",
        "days_min": 2,
        "days_max": 7,
    },
    "cdek_courier": {
        "id": "cdek_courier",
        "name_ru": "СДЭК — курьер до двери",
        "name_en": "CDEK courier",
        "days_min": 2,
        "days_max": 6,
    },
    "russian_post": {
        "id": "russian_post",
        "name_ru": "Почта России",
        "name_en": "Russian Post",
        "days_min": 5,
        "days_max": 14,
    },
    "courier_local": {
        "id": "courier_local",
        "name_ru": "Курьер по Краснодару",
        "name_en": "Krasnodar courier",
        "days_min": 0,
        "days_max": 1,
    },
}

# Base tariffs (RUB) by zone and method — preliminary estimates
TARIFFS: dict[str, dict[str, int]] = {
    ZONE_KRASNODAR_CITY: {
        "cdek_pvz": 0,
        "cdek_courier": 250,
        "russian_post": 200,
        "courier_local": 300,
    },
    ZONE_KRASNODAR_REGION: {
        "cdek_pvz": 280,
        "cdek_courier": 380,
        "russian_post": 250,
        "courier_local": 0,
    },
    ZONE_SOUTH: {
        "cdek_pvz": 320,
        "cdek_courier": 450,
        "russian_post": 280,
        "courier_local": 0,
    },
    ZONE_CENTRAL: {
        "cdek_pvz": 380,
        "cdek_courier": 520,
        "russian_post": 320,
        "courier_local": 0,
    },
    ZONE_URAL_SIBERIA: {
        "cdek_pvz": 450,
        "cdek_courier": 620,
        "russian_post": 380,
        "courier_local": 0,
    },
    ZONE_FAR_EAST: {
        "cdek_pvz": 580,
        "cdek_courier": 780,
        "russian_post": 450,
        "courier_local": 0,
    },
}

# City → zone mapping (partial; fallback by region keyword)
CITY_ZONES: dict[str, str] = {
    "краснодар": ZONE_KRASNODAR_CITY,
    "сочи": ZONE_SOUTH,
    "ростов-на-дону": ZONE_SOUTH,
    "ростов": ZONE_SOUTH,
    "ставрополь": ZONE_SOUTH,
    "волгоград": ZONE_SOUTH,
    "новороссийск": ZONE_SOUTH,
    "анапа": ZONE_SOUTH,
    "москва": ZONE_CENTRAL,
    "санкт-петербург": ZONE_CENTRAL,
    "спб": ZONE_CENTRAL,
    "петербург": ZONE_CENTRAL,
    "воронеж": ZONE_CENTRAL,
    "казань": ZONE_CENTRAL,
    "нижний новгород": ZONE_CENTRAL,
    "екатеринбург": ZONE_URAL_SIBERIA,
    "новосибирск": ZONE_URAL_SIBERIA,
    "омск": ZONE_URAL_SIBERIA,
    "челябинск": ZONE_URAL_SIBERIA,
    "красноярск": ZONE_URAL_SIBERIA,
    "владивосток": ZONE_FAR_EAST,
    "хабаровск": ZONE_FAR_EAST,
}

REGION_KEYWORDS: list[tuple[str, str]] = [
    ("краснодарск", ZONE_KRASNODAR_REGION),
    ("адыге", ZONE_SOUTH),
    ("ростовск", ZONE_SOUTH),
    ("ставропольск", ZONE_SOUTH),
    ("волгоградск", ZONE_SOUTH),
    ("крым", ZONE_SOUTH),
    ("московск", ZONE_CENTRAL),
    ("ленинградск", ZONE_CENTRAL),
    ("татарстан", ZONE_CENTRAL),
    ("свердловск", ZONE_URAL_SIBERIA),
    ("новосибирск", ZONE_URAL_SIBERIA),
    ("омск", ZONE_URAL_SIBERIA),
    ("приморск", ZONE_FAR_EAST),
    ("хабаровск", ZONE_FAR_EAST),
    ("сахалин", ZONE_FAR_EAST),
]


def detect_zone(city: str, region: str = "") -> str:
    city_key = city.strip().lower()
    region_key = region.strip().lower()
    if city_key in CITY_ZONES:
        return CITY_ZONES[city_key]
    for keyword, zone in REGION_KEYWORDS:
        if keyword in city_key or keyword in region_key:
            return zone
    if "краснодар" in region_key:
        return ZONE_KRASNODAR_REGION
    return ZONE_CENTRAL


def estimate_delivery(
    city: str,
    region: str = "",
    method: str = "cdek_pvz",
    items_count: int = 1,
) -> dict:
    zone = detect_zone(city, region)
    method_info = DELIVERY_METHODS.get(method, DELIVERY_METHODS["cdek_pvz"])
    base = TARIFFS.get(zone, TARIFFS[ZONE_CENTRAL]).get(method, 380)
    if base == 0 and method == "courier_local" and zone != ZONE_KRASNODAR_CITY:
        base = 0
        available = False
    else:
        available = True if method != "courier_local" or zone == ZONE_KRASNODAR_CITY else False

    extra = max(0, items_count - 1) * 40
    cost = base + extra if available else 0

    return {
        "warehouse": WAREHOUSE_CITY,
        "zone": zone,
        "method": method,
        "method_name_ru": method_info["name_ru"],
        "method_name_en": method_info["name_en"],
        "cost_rub": cost,
        "available": available,
        "days_min": method_info["days_min"],
        "days_max": method_info["days_max"],
        "preliminary": True,
        "note_ru": "Предварительный расчёт. Точная стоимость доставки оплачивается отдельно при отправке.",
        "note_en": "Preliminary estimate. Exact delivery cost is paid separately upon shipment.",
    }


def list_methods(city: str, region: str = "", items_count: int = 1) -> list[dict]:
    result = []
    for method_id, info in DELIVERY_METHODS.items():
        est = estimate_delivery(city, region, method_id, items_count=items_count)
        result.append({
            "id": method_id,
            "name_ru": info["name_ru"],
            "name_en": info["name_en"],
            "days_min": info["days_min"],
            "days_max": info["days_max"],
            "cost_rub": est["cost_rub"],
            "available": est["available"],
        })
    return result
