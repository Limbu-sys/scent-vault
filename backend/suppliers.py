"""Каталог ароматов «по мотивам» — без вымышленных поставщиков.

Реальных поставщиков добавляйте в админке: Поставщики → + Новый.
"""

from __future__ import annotations

CATALOG_SEED_VERSION = 3

# Реальных поставщиков в коде нет — только через админку / API
SEED_SUPPLIERS: list[dict] = []


def _desc(brand: str, name: str, family: str) -> str:
    return (
        f"По мотивам {brand} {name}. {family}. "
        "Масляный концентрат с заводов-производителей (Швейцария / ОАЭ). "
        "Поставщик с сертификатом и маркировкой «Честный знак» — указывается после привязки."
    )


def _item(
    pid: str,
    brand: str,
    name: str,
    gender: str,
    family: str,
    price: int,
    notes: list[str],
    *,
    concentration: str = "Extrait Oil",
    badge: str | None = None,
    gradient: list[str] | None = None,
    stock_ml: int = 150,
) -> dict:
    return {
        "id": pid,
        "brand": brand,
        "name": name,
        "gender": gender,
        "fragrance_family": family,
        "supplier_id": None,
        "notes": notes,
        "concentration": concentration,
        "base_price_per_ml": price,
        "badge": badge,
        "gradient": gradient or ["#3d2914", "#8b5a2b"],
        "description": _desc(brand, name, family),
        "stock_ml": stock_ml,
        "active": True,
        "reference_brand": brand,
        "reference_name": name,
    }


CATALOG_SEED: list[dict] = [
    _item("attar-musk-kashmir", "Attar Collection", "Musk Kashmir", "unisex",
          "Цветочные, древесно-мускусные", 480, ["мускус", "кашмир", "цветы", "древесина"]),
    _item("amouage-guidance", "Amouage", "Guidance", "unisex",
          "Цветочные, фруктовые", 620, ["фрукты", "цветы", "амбра"],
          badge="premium", gradient=["#1a3a2a", "#c9a962"]),
    _item("ajmal-amber-wood", "Ajmal", "Amber Wood", "unisex",
          "Восточные, древесные", 380, ["амбра", "древесина", "специи"]),
    _item("byredo-bal-dafrique", "Byredo", "Bal d'Afrique", "unisex",
          "Восточные, древесные", 520, ["бергамот", "фиалка", "ветiver"]),
    _item("byredo-gypsy-water", "Byredo", "Gypsy Water", "unisex",
          "Древесные, фужерные", 540, ["можжевельник", "лаадан", "ваниль"], badge="bestseller"),
    _item("clive-blonde-amber", "Clive Christian", "Blonde Amber", "unisex",
          "Амбровые", 780, ["амбра", "белые цветы", "ваниль"],
          badge="premium", gradient=["#d4af37", "#3d2914"]),
    _item("clive-matsukita", "Clive Christian", "Matsukita", "unisex",
          "Древесные, шипровые", 760, ["шипр", "зелень", "древесина"], badge="premium"),
    _item("escentric-02", "Escentric Molecules", "Escentric 02", "unisex",
          "Восточные, цветочные", 420, ["амбroxan", "ирис", "роза"]),
    _item("ex-nihilo-narcotique", "Ex Nihilo", "Narcotique Fleur", "unisex",
          "Цветочные, фруктовые", 560, ["нарцисс", "фрукты", "мускус"]),
    _item("ex-nihilo-blue-talisman", "Ex Nihilo", "Blue Talisman", "unisex",
          "Цветочные, фруктовые, сладкие", 550, ["груша", "жасмин", "sandalwood"]),
    _item("jml-wood-sage", "Jo Malone", "Wood Sage & Sea Salt", "unisex",
          "Фужерные", 440, ["шалфей", "морская соль", "амбroxan"]),
    _item("mfk-br540-extrait", "Maison Francis Kurkdjian", "Baccarat Rouge 540 Extrait", "unisex",
          "Восточные, цветочные", 820, ["шаfran", "жасмин", "амбра"],
          badge="icon", gradient=["#c41e3a", "#ffd700"]),
    _item("mab-ganymede", "Marc-Antoine Barrois", "Ganymede", "unisex",
          "Древесные, пряные", 580, ["кожа", "специи", "vetiver"]),
    _item("nasomatto-black-afgano", "Nasomatto", "Black Afgano", "unisex",
          "Древесные, фужерные", 640, ["oud", "табак"], badge="premium"),
    _item("orto-megamare", "Orto Parisi", "Megamare", "unisex",
          "Фужерные, водяные", 600, ["море", "водоросли", "амбroxan"], badge="bestseller"),
    _item("pdm-percival", "Parfums de Marly", "Percival", "unisex",
          "Цитрусовые, фужерные", 520, ["бергамот", "лаванда", "мускус"]),
    _item("pdm-layton", "Parfums de Marly", "Layton", "unisex",
          "Восточные, цветочные", 580, ["яблоко", "ваниль", "guaiac"], badge="bestseller"),
    _item("tt-kirke", "Tiziana Terenzi", "Kirke", "unisex",
          "Шипровые, фруктовые", 540, ["фрукты", "пачuli", "ваниль"]),
    _item("tf-lost-cherry", "Tom Ford", "Lost Cherry", "unisex",
          "Восточные, цветочные", 680, ["вишня", "миндаль", "tonka"],
          badge="icon", gradient=["#8b1a1a", "#e85d5d"]),
    _item("tf-mandarino-amalfi", "Tom Ford", "Mandarino di Amalfi", "unisex",
          "Цитрусовые, фужерные", 620, ["мандарин", "базилик", "мускус"]),
    _item("vilhelm-dear-polly", "Vilhelm Parfumerie", "Dear Polly", "unisex",
          "Фужерные", 500, ["бергamot", "чай", "vetiver"]),
    _item("xerjoff-erba-pura", "Xerjoff", "Erba Pura", "unisex",
          "Восточные", 590, ["фрукты", "мускус", "ваниль"],
          badge="bestseller", gradient=["#d4a017", "#8b4513"]),
    _item("creed-aventus", "Creed", "Aventus", "male",
          "Шипровые, фруктовые", 720, ["анanas", "берёза", "мускус"],
          badge="icon", gradient=["#2c2c2c", "#c0a060"]),
    _item("dior-sauvage", "Christian Dior", "Sauvage", "male",
          "Фужерные", 420, ["бергамот", "перец", "амбroxan"],
          badge="bestseller", gradient=["#1e3a5f", "#4a90d9"]),
    _item("bvlgari-tygar", "Bvlgari", "Tygar", "male",
          "Цитрусовые, фужерные", 580, ["бергamot", "амбroxan", "vetiver"]),
    _item("pdm-altair", "Parfums de Marly", "Althaïr", "male",
          "Восточные, гурманские", 560, ["ваниль", "пряности", "амбра"]),
    _item("shaik-no77", "Shaik", "No. 77", "male",
          "Восточные", 480, ["oud", "кожа", "специи"]),
    _item("versace-eau-fraiche", "Versace", "Man Eau Fraiche", "male",
          "Древесные, водяные", 340, ["лимон", "кедр", "мускус"]),
    _item("gucci-gorgeous-gardenia", "Gucci", "Flora Gorgeous Gardenia", "female",
          "Цветочные, фруктовые", 460, ["gardenia", "груша", "жасмин"],
          gradient=["#f4a6c8", "#d4568a"]),
    _item("haute-devils-intrigue", "Haute Fragrance", "Devil's Intrigue", "female",
          "Цветочные, древесно-мускусные", 520, ["роза", "мускус", "древесина"]),
    _item("lancome-tresor-midnight", "Lancome", "Trésor Midnight Rose", "female",
          "Цветочные, древесно-мускусные", 400, ["роза", "малина", "ваниль"]),
    _item("trussardi-donna", "Trussardi", "Donna", "female",
          "Восточные, цветочные", 360, ["жасмин", "фрукты", "patchouli"]),
]

SEED_PRODUCTS = CATALOG_SEED

# Устаревшие ID вымышленных поставщиков — удаляются при миграции
PLACEHOLDER_SUPPLIER_IDS = ("supplier-ch", "supplier-ae")
