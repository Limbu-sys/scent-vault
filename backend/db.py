"""SQLite storage for Scent Vault."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from catalog import enrich_product
from suppliers import (
    CATALOG_SEED,
    CATALOG_SEED_VERSION,
    PLACEHOLDER_SUPPLIER_IDS,
    SEED_PRODUCTS,
    SEED_SUPPLIERS,
)
from config import ADMIN_TELEGRAM_IDS, DATA_DIR, DB_PATH, TRIBUTE_SHOP_URL

PRODUCTS_JSON = DATA_DIR / "products.json"
SUPPLIERS_SEED_FILE = Path(__file__).resolve().parent / "suppliers_seed.json"
SUPPLIERS_SEED_VERSION = "1"
ORDER_STATUSES = ("pending_payment", "paid", "processing", "shipped", "delivered", "cancelled")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s)
    return s[:48] or str(uuid.uuid4())[:8]


def _next_sku(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT sku FROM products WHERE sku LIKE 'SV-%'"
    ).fetchall()
    nums = []
    for (sku,) in rows:
        try:
            nums.append(int(str(sku)[3:]))
        except ValueError:
            pass
    return f"SV-{(max(nums, default=0) + 1):05d}"


def _row_to_product(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["notes"] = json.loads(d.pop("notes_json") or "[]")
    d["gradient"] = json.loads(d.pop("gradient_json") or '["#3d2914","#8b5a2b"]')
    d["active"] = bool(d.get("active", 1))
    return d


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init_schema()
        self._ensure_product_columns()
        self._ensure_supplier_columns()
        self._seed_suppliers()
        self._seed_dgis_suppliers()
        self._remove_placeholder_suppliers()
        self._migrate_json_if_needed()
        self._sync_catalog_seed_if_needed()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    telegram_id TEXT PRIMARY KEY,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    sku TEXT UNIQUE NOT NULL,
                    brand TEXT NOT NULL,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL DEFAULT 'unisex',
                    notes_json TEXT NOT NULL DEFAULT '[]',
                    concentration TEXT NOT NULL DEFAULT 'EDP',
                    base_price_per_ml REAL NOT NULL,
                    badge TEXT,
                    gradient_json TEXT NOT NULL DEFAULT '["#3d2914","#8b5a2b"]',
                    image_url TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    stock_ml INTEGER NOT NULL DEFAULT 100,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    telegram_user_id TEXT,
                    telegram_username TEXT,
                    status TEXT NOT NULL DEFAULT 'pending_payment',
                    subtotal_rub INTEGER NOT NULL DEFAULT 0,
                    delivery_estimate_rub INTEGER NOT NULL DEFAULT 0,
                    delivery_method TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    region TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    postal_code TEXT NOT NULL DEFAULT '',
                    comment TEXT NOT NULL DEFAULT '',
                    payment_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_id TEXT NOT NULL,
                    sku TEXT NOT NULL DEFAULT '',
                    brand TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    volume_ml INTEGER NOT NULL,
                    qty INTEGER NOT NULL,
                    unit_price INTEGER NOT NULL,
                    line_total INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(telegram_user_id);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

                CREATE TABLE IF NOT EXISTS suppliers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country TEXT NOT NULL DEFAULT '',
                    region TEXT NOT NULL DEFAULT '',
                    origin_type TEXT NOT NULL DEFAULT 'oil_concentrate',
                    origin_note TEXT NOT NULL DEFAULT '',
                    has_quality_certificate INTEGER NOT NULL DEFAULT 0,
                    certificate_label TEXT NOT NULL DEFAULT '',
                    honest_sign INTEGER NOT NULL DEFAULT 0,
                    honest_sign_note TEXT NOT NULL DEFAULT '',
                    contact_email TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            for aid in ADMIN_TELEGRAM_IDS:
                conn.execute(
                    "INSERT OR IGNORE INTO admins (telegram_id, added_at) VALUES (?, ?)",
                    (aid, _utc_now()),
                )

    def _ensure_product_columns(self) -> None:
        with self._conn() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
            if "supplier_id" not in cols:
                conn.execute("ALTER TABLE products ADD COLUMN supplier_id TEXT")
            if "fragrance_family" not in cols:
                conn.execute("ALTER TABLE products ADD COLUMN fragrance_family TEXT NOT NULL DEFAULT ''")

    def _ensure_supplier_columns(self) -> None:
        with self._conn() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(suppliers)")}
            extra = {
                "contact_person": "TEXT NOT NULL DEFAULT ''",
                "phone": "TEXT NOT NULL DEFAULT ''",
                "telegram": "TEXT NOT NULL DEFAULT ''",
                "whatsapp": "TEXT NOT NULL DEFAULT ''",
                "website": "TEXT NOT NULL DEFAULT ''",
                "inn": "TEXT NOT NULL DEFAULT ''",
                "address": "TEXT NOT NULL DEFAULT ''",
                "notes": "TEXT NOT NULL DEFAULT ''",
                "fragrances_offered": "TEXT NOT NULL DEFAULT ''",
                "dgis_id": "TEXT NOT NULL DEFAULT ''",
            }
            for col, typedef in extra.items():
                if col not in cols:
                    conn.execute(f"ALTER TABLE suppliers ADD COLUMN {col} {typedef}")

    def _remove_placeholder_suppliers(self) -> None:
        if not PLACEHOLDER_SUPPLIER_IDS:
            return
        placeholders = list(PLACEHOLDER_SUPPLIER_IDS)
        qs = ",".join("?" * len(placeholders))
        with self._conn() as conn:
            conn.execute(
                f"UPDATE products SET supplier_id = NULL WHERE supplier_id IN ({qs})",
                placeholders,
            )
            conn.execute(f"DELETE FROM suppliers WHERE id IN ({qs})", placeholders)

    def _seed_suppliers(self) -> None:
        if not SEED_SUPPLIERS:
            return
        now = _utc_now()
        with self._conn() as conn:
            for s in SEED_SUPPLIERS:
                self._insert_supplier_row(conn, s, now)

    def _seed_dgis_suppliers(self) -> None:
        """Загружает поставщиков из suppliers_seed.json (2GIS, Краснодар)."""
        if not SUPPLIERS_SEED_FILE.is_file():
            return
        with self._conn() as conn:
            if self._meta_get(conn, "suppliers_seed_version") == SUPPLIERS_SEED_VERSION:
                return
        try:
            data = json.loads(SUPPLIERS_SEED_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        items = data.get("items") or []
        if items:
            self.import_dgis_leads(items, skip_existing=True)
        with self._conn() as conn:
            self._meta_set(conn, "suppliers_seed_version", SUPPLIERS_SEED_VERSION)

    def _insert_supplier_row(self, conn: sqlite3.Connection, s: dict, now: str) -> None:
        conn.execute(
            """
            INSERT INTO suppliers (
                id, name, country, region, origin_type, origin_note,
                has_quality_certificate, certificate_label,
                honest_sign, honest_sign_note, contact_email,
                contact_person, phone, telegram, whatsapp, website,
                inn, address, notes, fragrances_offered, dgis_id,
                active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, country=excluded.country, region=excluded.region,
                origin_type=excluded.origin_type, origin_note=excluded.origin_note,
                has_quality_certificate=excluded.has_quality_certificate,
                certificate_label=excluded.certificate_label,
                honest_sign=excluded.honest_sign, honest_sign_note=excluded.honest_sign_note,
                contact_email=excluded.contact_email, contact_person=excluded.contact_person,
                phone=excluded.phone, telegram=excluded.telegram, whatsapp=excluded.whatsapp,
                website=excluded.website, inn=excluded.inn, address=excluded.address,
                notes=excluded.notes, fragrances_offered=excluded.fragrances_offered,
                dgis_id=excluded.dgis_id,
                active=excluded.active, updated_at=excluded.updated_at
            """,
            (
                s["id"],
                s["name"],
                s.get("country", ""),
                s.get("region", ""),
                s.get("origin_type", "oil_concentrate"),
                s.get("origin_note", ""),
                1 if s.get("has_quality_certificate") else 0,
                s.get("certificate_label", ""),
                1 if s.get("honest_sign") else 0,
                s.get("honest_sign_note", ""),
                s.get("contact_email", ""),
                s.get("contact_person", ""),
                s.get("phone", ""),
                s.get("telegram", ""),
                s.get("whatsapp", ""),
                s.get("website", ""),
                s.get("inn", ""),
                s.get("address", ""),
                s.get("notes", ""),
                s.get("fragrances_offered", ""),
                s.get("dgis_id", ""),
                1 if s.get("active", True) else 0,
                now,
                now,
            ),
        )

    def _meta_get(self, conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _meta_set(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def _upsert_catalog_item(self, conn: sqlite3.Connection, raw: dict, now: str) -> None:
        existing = conn.execute("SELECT sku FROM products WHERE id = ?", (raw["id"],)).fetchone()
        sku = existing[0] if existing else (raw.get("sku") or _next_sku(conn))
        conn.execute(
            """
            INSERT INTO products (
                id, sku, brand, name, gender, notes_json, concentration,
                base_price_per_ml, badge, gradient_json, image_url, description,
                stock_ml, active, supplier_id, fragrance_family, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                brand=excluded.brand, name=excluded.name, gender=excluded.gender,
                notes_json=excluded.notes_json, concentration=excluded.concentration,
                base_price_per_ml=excluded.base_price_per_ml, badge=excluded.badge,
                gradient_json=excluded.gradient_json, description=excluded.description,
                fragrance_family=excluded.fragrance_family,
                active=1, updated_at=excluded.updated_at
            """,
            (
                raw["id"],
                sku,
                raw["brand"],
                raw["name"],
                raw.get("gender", "unisex"),
                json.dumps(raw.get("notes", []), ensure_ascii=False),
                raw.get("concentration", "Extrait Oil"),
                raw["base_price_per_ml"],
                raw.get("badge"),
                json.dumps(raw.get("gradient", ["#3d2914", "#8b5a2b"])),
                raw.get("image_url", ""),
                raw.get("description", ""),
                raw.get("stock_ml", 150),
                raw.get("supplier_id"),
                raw.get("fragrance_family", ""),
                now,
                now,
            ),
        )
        if raw.get("supplier_id"):
            conn.execute(
                "UPDATE products SET supplier_id = ? WHERE id = ?",
                (raw["supplier_id"], raw["id"]),
            )

    def _sync_catalog_seed_if_needed(self) -> None:
        with self._conn() as conn:
            ver = self._meta_get(conn, "catalog_seed_version")
            if ver and int(ver) >= CATALOG_SEED_VERSION:
                return
            now = _utc_now()
            seed_ids = {p["id"] for p in CATALOG_SEED}
            for raw in CATALOG_SEED:
                self._upsert_catalog_item(conn, raw, now)
            conn.execute(
                "UPDATE products SET active = 0 WHERE id NOT IN ({})".format(
                    ",".join("?" * len(seed_ids))
                ),
                list(seed_ids),
            )
            self._meta_set(conn, "catalog_seed_version", str(CATALOG_SEED_VERSION))

    def import_catalog_seed(self, deactivate_others: bool = True) -> dict:
        now = _utc_now()
        with self._conn() as conn:
            for raw in CATALOG_SEED:
                self._upsert_catalog_item(conn, raw, now)
            if deactivate_others:
                seed_ids = {p["id"] for p in CATALOG_SEED}
                conn.execute(
                    "UPDATE products SET active = 0 WHERE id NOT IN ({})".format(
                        ",".join("?" * len(seed_ids))
                    ),
                    list(seed_ids),
                )
            self._meta_set(conn, "catalog_seed_version", str(CATALOG_SEED_VERSION))
        return {"ok": True, "count": len(CATALOG_SEED), "version": CATALOG_SEED_VERSION}

    def _migrate_json_if_needed(self) -> None:
        with self._conn() as conn:
            count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count > 0:
                return
            items: list[dict] = []
            if PRODUCTS_JSON.exists():
                try:
                    items = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8")).get("items", [])
                except json.JSONDecodeError:
                    items = []
            if not items:
                items = [dict(p) for p in SEED_PRODUCTS]
            now = _utc_now()
            for raw in items:
                self._upsert_catalog_item(conn, dict(raw), now)
            self._meta_set(conn, "catalog_seed_version", str(CATALOG_SEED_VERSION))

    # --- Admins ---

    def is_admin(self, user_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM admins WHERE telegram_id = ?", (str(user_id),)
            ).fetchone()
            return row is not None

    def list_admins(self) -> list[str]:
        with self._conn() as conn:
            return [r[0] for r in conn.execute("SELECT telegram_id FROM admins ORDER BY telegram_id")]

    def add_admin(self, telegram_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO admins (telegram_id, added_at) VALUES (?, ?)",
                (str(telegram_id), _utc_now()),
            )

    def remove_admin(self, telegram_id: str) -> None:
        tid = str(telegram_id)
        with self._conn() as conn:
            n = conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
            if n <= 1:
                raise ValueError("cannot_remove_last_admin")
            cur = conn.execute("DELETE FROM admins WHERE telegram_id = ?", (tid,))
            if cur.rowcount == 0:
                raise ValueError("not_admin")

    # --- Suppliers ---

    def _enrich_row(self, row: sqlite3.Row) -> dict:
        product = _row_to_product(row)
        sid = product.get("supplier_id")
        supplier = self.get_supplier(sid) if sid else None
        return enrich_product(product, supplier)

    def list_suppliers(self, active_only: bool = True) -> list[dict]:
        sql = "SELECT * FROM suppliers"
        if active_only:
            sql += " WHERE active = 1"
        sql += " ORDER BY country, name"
        with self._conn() as conn:
            rows = conn.execute(sql).fetchall()
        return [self._row_to_supplier(r) for r in rows]

    def get_supplier(self, supplier_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
        return self._row_to_supplier(row) if row else None

    @staticmethod
    def _row_to_supplier(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["has_quality_certificate"] = bool(d.get("has_quality_certificate"))
        d["honest_sign"] = bool(d.get("honest_sign"))
        d["active"] = bool(d.get("active", 1))
        return d

    def create_supplier(self, data: dict) -> dict:
        name = str(data.get("name", "")).strip()
        if not name:
            raise ValueError("name_required")
        sid = data.get("id") or _slugify(name)
        now = _utc_now()
        with self._conn() as conn:
            if conn.execute("SELECT 1 FROM suppliers WHERE id = ?", (sid,)).fetchone():
                sid = f"{sid}-{uuid.uuid4().hex[:4]}"
            payload = {"id": sid, "name": name, **data}
            self._insert_supplier_row(conn, payload, now)
        return self.get_supplier(sid)  # type: ignore

    def update_supplier(self, supplier_id: str, data: dict) -> dict:
        existing = self.get_supplier(supplier_id)
        if not existing:
            raise ValueError("supplier_not_found")
        merged = {**existing, **data, "id": supplier_id}
        now = _utc_now()
        with self._conn() as conn:
            self._insert_supplier_row(conn, merged, now)
        return self.get_supplier(supplier_id)  # type: ignore

    def delete_supplier(self, supplier_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET supplier_id = NULL WHERE supplier_id = ?",
                (supplier_id,),
            )
            cur = conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
            if cur.rowcount == 0:
                raise ValueError("supplier_not_found")

    def get_supplier_by_dgis_id(self, dgis_id: str) -> dict | None:
        if not dgis_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM suppliers WHERE dgis_id = ? LIMIT 1",
                (dgis_id,),
            ).fetchone()
        return self._row_to_supplier(row) if row else None

    def import_dgis_leads(
        self,
        leads: list[dict],
        *,
        skip_existing: bool = True,
    ) -> dict[str, Any]:
        """Импорт черновиков из 2GIS в таблицу suppliers."""
        created: list[str] = []
        updated: list[str] = []
        skipped: list[str] = []
        for lead in leads:
            dgis_id = str(lead.get("dgis_id") or "").strip()
            name = str(lead.get("name") or "").strip()
            if not name:
                continue
            existing = self.get_supplier_by_dgis_id(dgis_id) if dgis_id else None
            if existing and skip_existing:
                skipped.append(existing["id"])
                continue
            payload = {
                k: v
                for k, v in lead.items()
                if not k.startswith("_") and k in {
                    "id",
                    "name",
                    "country",
                    "region",
                    "origin_type",
                    "origin_note",
                    "has_quality_certificate",
                    "certificate_label",
                    "honest_sign",
                    "honest_sign_note",
                    "contact_email",
                    "contact_person",
                    "phone",
                    "telegram",
                    "whatsapp",
                    "website",
                    "inn",
                    "address",
                    "notes",
                    "fragrances_offered",
                    "dgis_id",
                    "active",
                }
            }
            if existing:
                payload["id"] = existing["id"]
                self.update_supplier(existing["id"], payload)
                updated.append(existing["id"])
            else:
                sid = payload.get("id") or f"dgis-{dgis_id}" if dgis_id else None
                if sid:
                    payload["id"] = sid
                row = self.create_supplier(payload)
                created.append(row["id"])
        return {"created": created, "updated": updated, "skipped": skipped}

    def list_products_for_supplier(self, supplier_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE supplier_id = ? ORDER BY brand, name",
                (supplier_id,),
            ).fetchall()
        return [self._enrich_row(r) for r in rows]

    # --- Products ---

    def get_brands(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT brand FROM products WHERE active = 1 ORDER BY brand"
            ).fetchall()
            return [r[0] for r in rows]

    def list_products(
        self,
        brand: str | None = None,
        gender: str | None = None,
        q: str | None = None,
        active_only: bool = True,
    ) -> list[dict]:
        sql = "SELECT * FROM products WHERE 1=1"
        params: list[Any] = []
        if active_only:
            sql += " AND active = 1"
        if brand:
            sql += " AND LOWER(brand) = LOWER(?)"
            params.append(brand)
        if gender and gender != "all":
            sql += " AND (gender = ? OR gender = 'unisex')"
            params.append(gender)
        if q:
            sql += " AND (LOWER(name) LIKE ? OR LOWER(brand) LIKE ? OR LOWER(sku) LIKE ?)"
            needle = f"%{q.lower()}%"
            params.extend([needle, needle, needle])
        sql += " ORDER BY brand, name"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._enrich_row(r) for r in rows]

    def list_products_admin(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM products ORDER BY brand, name").fetchall()
        return [self._enrich_row(r) for r in rows]

    def get_product(self, product_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return None
        return self._enrich_row(row)

    def create_product(self, data: dict) -> dict:
        brand = str(data.get("brand", "")).strip()
        name = str(data.get("name", "")).strip()
        if not brand or not name:
            raise ValueError("brand_and_name_required")
        pid = data.get("id") or _slugify(f"{brand}-{name}")
        now = _utc_now()
        with self._conn() as conn:
            if conn.execute("SELECT 1 FROM products WHERE id = ?", (pid,)).fetchone():
                pid = f"{pid}-{uuid.uuid4().hex[:4]}"
            sku = _next_sku(conn)
            conn.execute(
                """
                INSERT INTO products (
                    id, sku, brand, name, gender, notes_json, concentration,
                    base_price_per_ml, badge, gradient_json, image_url, description,
                    stock_ml, active, supplier_id, fragrance_family, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    sku,
                    brand,
                    name,
                    data.get("gender", "unisex"),
                    json.dumps(data.get("notes", []), ensure_ascii=False),
                    data.get("concentration", "Extrait Oil"),
                    float(data["base_price_per_ml"]),
                    data.get("badge"),
                    json.dumps(data.get("gradient", ["#3d2914", "#8b5a2b"])),
                    data.get("image_url", ""),
                    data.get("description", ""),
                    int(data.get("stock_ml", 100)),
                    1 if data.get("active", True) else 0,
                    data.get("supplier_id"),
                    data.get("fragrance_family", ""),
                    now,
                    now,
                ),
            )
        return self.get_product(pid)  # type: ignore

    def update_product(self, product_id: str, data: dict) -> dict:
        existing = self.get_product(product_id)
        if not existing:
            raise ValueError("product_not_found")
        merged = {**existing, **data}
        now = _utc_now()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE products SET
                    brand=?, name=?, gender=?, notes_json=?, concentration=?,
                    base_price_per_ml=?, badge=?, gradient_json=?, image_url=?,
                    description=?, stock_ml=?, active=?, supplier_id=?,
                    fragrance_family=?, updated_at=?
                WHERE id=?
                """,
                (
                    merged["brand"],
                    merged["name"],
                    merged["gender"],
                    json.dumps(merged.get("notes", []), ensure_ascii=False),
                    merged.get("concentration", "Extrait Oil"),
                    float(merged["base_price_per_ml"]),
                    merged.get("badge"),
                    json.dumps(merged.get("gradient", ["#3d2914", "#8b5a2b"])),
                    merged.get("image_url", ""),
                    merged.get("description", ""),
                    int(merged.get("stock_ml", 100)),
                    1 if merged.get("active", True) else 0,
                    merged.get("supplier_id"),
                    merged.get("fragrance_family", ""),
                    now,
                    product_id,
                ),
            )
        return self.get_product(product_id)  # type: ignore

    def delete_product(self, product_id: str) -> None:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            if cur.rowcount == 0:
                raise ValueError("product_not_found")

    def check_stock(self, product_id: str, volume_ml: int, qty: int) -> bool:
        p = self.get_product(product_id)
        if not p:
            return False
        needed = volume_ml * qty
        return int(p.get("stock_ml", 0)) >= needed

    def deduct_stock(self, product_id: str, volume_ml: int, qty: int) -> None:
        needed = volume_ml * qty
        with self._conn() as conn:
            conn.execute(
                "UPDATE products SET stock_ml = MAX(0, stock_ml - ?), updated_at = ? WHERE id = ?",
                (needed, _utc_now(), product_id),
            )

    # --- Orders ---

    def _payment_url(self, order_id: str, amount: int) -> str | None:
        if not TRIBUTE_SHOP_URL:
            return None
        sep = "&" if "?" in TRIBUTE_SHOP_URL else "?"
        return f"{TRIBUTE_SHOP_URL}{sep}order={order_id}&amount={amount}"

    def create_order(self, data: dict) -> dict:
        items_in = data["items"]
        items_detail = []
        subtotal = 0
        for line in items_in:
            product = self.get_product(line["product_id"])
            if not product or not product.get("active", True):
                raise ValueError(f"unknown_product:{line['product_id']}")
            vol = next((v for v in product["volumes"] if v["ml"] == line["volume_ml"]), None)
            if not vol:
                raise ValueError(f"invalid_volume:{line['volume_ml']}")
            if not self.check_stock(line["product_id"], line["volume_ml"], line["qty"]):
                raise ValueError(f"insufficient_stock:{product.get('sku')}")
            line_total = vol["price"] * line["qty"]
            subtotal += line_total
            items_detail.append({
                "product_id": line["product_id"],
                "sku": product.get("sku", ""),
                "brand": product["brand"],
                "name": product["name"],
                "volume_ml": line["volume_ml"],
                "qty": line["qty"],
                "unit_price": vol["price"],
                "line_total": line_total,
            })

        order_id = str(uuid.uuid4())[:8].upper()
        now = _utc_now()
        payment_url = self._payment_url(order_id, subtotal)

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO orders (
                    id, telegram_user_id, telegram_username, status,
                    subtotal_rub, delivery_estimate_rub, delivery_method,
                    city, region, address, postal_code, comment,
                    payment_url, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending_payment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order_id,
                    str(data.get("telegram_user_id", "")),
                    data.get("telegram_username") or "",
                    subtotal,
                    int(data.get("delivery_estimate_rub", 0)),
                    data.get("delivery_method", ""),
                    data.get("city", ""),
                    data.get("region", ""),
                    data.get("address", ""),
                    data.get("postal_code", ""),
                    data.get("comment", ""),
                    payment_url,
                    now,
                    now,
                ),
            )
            for it in items_detail:
                conn.execute(
                    """
                    INSERT INTO order_items (
                        order_id, product_id, sku, brand, name,
                        volume_ml, qty, unit_price, line_total
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        it["product_id"],
                        it["sku"],
                        it["brand"],
                        it["name"],
                        it["volume_ml"],
                        it["qty"],
                        it["unit_price"],
                        it["line_total"],
                    ),
                )
        return self.get_order(order_id)  # type: ignore

    def _order_row(self, row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
        d = dict(row)
        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (d["id"],)
        ).fetchall()
        d["items"] = [dict(i) for i in items]
        return d

    def get_order(self, order_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not row:
                return None
            return self._order_row(row, conn)

    def list_orders(self, status: str | None = None, limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM orders"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._order_row(r, conn) for r in rows]

    def list_user_orders(self, telegram_user_id: str, limit: int = 50) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE telegram_user_id = ? ORDER BY created_at DESC LIMIT ?",
                (str(telegram_user_id), limit),
            ).fetchall()
            return [self._order_row(r, conn) for r in rows]

    def update_order_status(self, order_id: str, status: str) -> dict:
        if status not in ORDER_STATUSES:
            raise ValueError("invalid_status")
        now = _utc_now()
        with self._conn() as conn:
            order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                raise ValueError("order_not_found")
            old_status = order["status"]
            conn.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, order_id),
            )
            if status == "paid" and old_status == "pending_payment":
                items = conn.execute(
                    "SELECT product_id, volume_ml, qty FROM order_items WHERE order_id = ?",
                    (order_id,),
                ).fetchall()
                for it in items:
                    needed = it["volume_ml"] * it["qty"]
                    conn.execute(
                        "UPDATE products SET stock_ml = MAX(0, stock_ml - ?), updated_at = ? WHERE id = ?",
                        (needed, now, it["product_id"]),
                    )
        return self.get_order(order_id)  # type: ignore

    def mark_order_paid(self, order_id: str) -> dict | None:
        order = self.get_order(order_id)
        if not order:
            return None
        if order["status"] != "pending_payment":
            return order
        return self.update_order_status(order_id, "paid")


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
