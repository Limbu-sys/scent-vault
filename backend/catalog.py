"""Product catalog — famous brands, decant volumes."""

from __future__ import annotations

VOLUMES_ML = [1, 2, 3, 5, 10]

VOLUME_MULTIPLIERS = {
    1: 1.0,
    2: 1.85,
    3: 2.65,
    5: 4.2,
    10: 7.5,
}

BRANDS = [
    "Chanel",
    "Dior",
    "Tom Ford",
    "Creed",
    "Maison Francis Kurkdjian",
    "Byredo",
    "Amouage",
    "Xerjoff",
    "Louis Vuitton",
    "Hermès",
]

SEED_PRODUCTS = [
    {
        "id": "chanel-no5",
        "brand": "Chanel",
        "name": "N°5",
        "gender": "female",
        "notes": ["aldehydes", "jasmine", "sandalwood"],
        "concentration": "EDP",
        "base_price_per_ml": 420,
        "badge": "icon",
        "gradient": ["#c9a86c", "#8b6914"],
    },
    {
        "id": "chanel-coco",
        "brand": "Chanel",
        "name": "Coco Mademoiselle",
        "gender": "female",
        "notes": ["orange", "rose", "patchouli"],
        "concentration": "EDP",
        "base_price_per_ml": 380,
        "badge": "bestseller",
        "gradient": ["#e8b4b8", "#c77d8a"],
    },
    {
        "id": "dior-sauvage",
        "brand": "Dior",
        "name": "Sauvage",
        "gender": "male",
        "notes": ["bergamot", "pepper", "ambroxan"],
        "concentration": "EDT",
        "base_price_per_ml": 290,
        "badge": "bestseller",
        "gradient": ["#1e3a5f", "#4a90d9"],
    },
    {
        "id": "dior-miss-dior",
        "brand": "Dior",
        "name": "Miss Dior",
        "gender": "female",
        "notes": ["rose", "peony", "musk"],
        "concentration": "EDP",
        "base_price_per_ml": 340,
        "gradient": ["#f4a6c8", "#d4568a"],
    },
    {
        "id": "tf-oud-wood",
        "brand": "Tom Ford",
        "name": "Oud Wood",
        "gender": "unisex",
        "notes": ["oud", "sandalwood", "cardamom"],
        "concentration": "EDP",
        "base_price_per_ml": 520,
        "badge": "premium",
        "gradient": ["#3d2914", "#8b5a2b"],
    },
    {
        "id": "tf-lost-cherry",
        "brand": "Tom Ford",
        "name": "Lost Cherry",
        "gender": "unisex",
        "notes": ["cherry", "almond", "tonka"],
        "concentration": "EDP",
        "base_price_per_ml": 580,
        "badge": "premium",
        "gradient": ["#8b1a1a", "#e85d5d"],
    },
    {
        "id": "creed-aventus",
        "brand": "Creed",
        "name": "Aventus",
        "gender": "male",
        "notes": ["pineapple", "birch", "musk"],
        "concentration": "EDP",
        "base_price_per_ml": 650,
        "badge": "icon",
        "gradient": ["#2c2c2c", "#c0a060"],
    },
    {
        "id": "creed-silver",
        "brand": "Creed",
        "name": "Silver Mountain Water",
        "gender": "unisex",
        "notes": ["bergamot", "green tea", "musk"],
        "concentration": "EDP",
        "base_price_per_ml": 620,
        "gradient": ["#a8d8ea", "#6bb3d9"],
    },
    {
        "id": "mfk-baccarat",
        "brand": "Maison Francis Kurkdjian",
        "name": "Baccarat Rouge 540",
        "gender": "unisex",
        "notes": ["saffron", "jasmine", "ambergris"],
        "concentration": "EDP",
        "base_price_per_ml": 720,
        "badge": "icon",
        "gradient": ["#c41e3a", "#ffd700"],
    },
    {
        "id": "byredo-gypsy",
        "brand": "Byredo",
        "name": "Gypsy Water",
        "gender": "unisex",
        "notes": ["juniper", "incense", "vanilla"],
        "concentration": "EDP",
        "base_price_per_ml": 480,
        "gradient": ["#d4a574", "#8b6914"],
    },
    {
        "id": "amouage-reflection",
        "brand": "Amouage",
        "name": "Reflection Man",
        "gender": "male",
        "notes": ["rosemary", "iris", "sandalwood"],
        "concentration": "EDP",
        "base_price_per_ml": 540,
        "badge": "premium",
        "gradient": ["#4a6741", "#8fbc8f"],
    },
    {
        "id": "xerjoff-naxos",
        "brand": "Xerjoff",
        "name": "Naxos",
        "gender": "unisex",
        "notes": ["lavender", "honey", "tobacco"],
        "concentration": "EDP",
        "base_price_per_ml": 490,
        "badge": "bestseller",
        "gradient": ["#d4a017", "#8b4513"],
    },
    {
        "id": "lv-imagination",
        "brand": "Louis Vuitton",
        "name": "Imagination",
        "gender": "male",
        "notes": ["bergamot", "black tea", "ambroxan"],
        "concentration": "EDP",
        "base_price_per_ml": 560,
        "gradient": ["#1a1a2e", "#e94560"],
    },
    {
        "id": "hermes-terre",
        "brand": "Hermès",
        "name": "Terre d'Hermès",
        "gender": "male",
        "notes": ["orange", "flint", "vetiver"],
        "concentration": "EDT",
        "base_price_per_ml": 360,
        "badge": "bestseller",
        "gradient": ["#c17817", "#8b4513"],
    },
]


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
    return p

