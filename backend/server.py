"""FastAPI: Scent Vault Telegram Mini App."""

from __future__ import annotations

import json
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from admin_auth import is_admin_user, require_admin
from auth import parse_telegram_user, require_telegram_auth
from catalog import VOLUMES_ML
from config import (
    APP_PUBLIC_URL,
    DATA_DIR,
    LEGAL_ADDRESS,
    LEGAL_CONTACT_EMAIL,
    LEGAL_INN,
    LEGAL_PHONE,
    LEGAL_SELF_EMPLOYED_NAME,
    ROOT,
    TRIBUTE_SHOP_URL,
    UPLOADS_DIR,
    WAREHOUSE_CITY,
)
from db import ORDER_STATUSES, get_db
from delivery import DELIVERY_METHODS, estimate_delivery, list_methods
from notify import notify_admins_new_order, notify_user_order_status
from tribute import process_tribute_webhook, verify_tribute_signature

WEBAPP_DIR = ROOT / "webapp"
LEGAL_DIR = WEBAPP_DIR / "legal"
ALLOWED_UPLOAD = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
LEGAL_PAGES = {"privacy", "terms", "offer"}
LEGAL_PUBLISHED = "3 июля 2026 г."


def _legal_context() -> dict[str, str]:
    return {
        "{{LEGAL_NAME}}": LEGAL_SELF_EMPLOYED_NAME or "самозанятый продавец Scent Vault",
        "{{LEGAL_INN}}": LEGAL_INN or "указан по запросу",
        "{{LEGAL_EMAIL}}": LEGAL_CONTACT_EMAIL or "dvetochkiinfo@gmail.com",
        "{{LEGAL_PHONE}}": LEGAL_PHONE or "по e-mail",
        "{{LEGAL_ADDRESS}}": LEGAL_ADDRESS or f"г. {WAREHOUSE_CITY}, Россия",
        "{{WAREHOUSE}}": WAREHOUSE_CITY,
        "{{DATE}}": LEGAL_PUBLISHED,
    }


def _render_legal(page: str) -> str:
    path = LEGAL_DIR / f"{page}.html"
    if not path.is_file():
        raise HTTPException(status_code=404)
    html = path.read_text(encoding="utf-8")
    for key, value in _legal_context().items():
        html = html.replace(key, value)
    return html


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_db()
    yield


app = FastAPI(title="Scent Vault API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class CartItem(BaseModel):
    product_id: str
    volume_ml: int = Field(ge=1)
    qty: int = Field(ge=1, default=1)


class DeliveryEstimateIn(BaseModel):
    city: str = Field(min_length=1)
    region: str = ""
    method: str = "cdek_pvz"
    items_count: int = Field(ge=1, default=1)


class OrderIn(BaseModel):
    items: list[CartItem] = Field(min_length=1)
    city: str = Field(min_length=1)
    region: str = ""
    address: str = Field(min_length=3)
    postal_code: str = ""
    delivery_method: str = "cdek_pvz"
    comment: str = ""


class ProductIn(BaseModel):
    brand: str = Field(min_length=1)
    name: str = Field(min_length=1)
    gender: str = Field(default="unisex", pattern="^(female|male|unisex)$")
    notes: list[str] = Field(default_factory=list)
    concentration: str = Field(default="EDP", max_length=16)
    base_price_per_ml: float = Field(gt=0)
    badge: str | None = None
    gradient: list[str] = Field(default_factory=lambda: ["#3d2914", "#8b5a2b"])
    image_url: str = ""
    description: str = ""
    stock_ml: int = Field(default=100, ge=0)
    active: bool = True


class ProductUpdate(BaseModel):
    brand: str | None = None
    name: str | None = None
    gender: str | None = Field(default=None, pattern="^(female|male|unisex)$")
    notes: list[str] | None = None
    concentration: str | None = None
    base_price_per_ml: float | None = Field(default=None, gt=0)
    badge: str | None = None
    gradient: list[str] | None = None
    image_url: str | None = None
    description: str | None = None
    stock_ml: int | None = Field(default=None, ge=0)
    active: bool | None = None


class AdminIn(BaseModel):
    telegram_id: str = Field(min_length=1)


class OrderStatusIn(BaseModel):
    status: str = Field(pattern="^(paid|processing|shipped|delivered|cancelled)$")


@app.get("/api/health")
def health():
    return {"ok": True, "warehouse": WAREHOUSE_CITY, "version": "2.0.0"}


@app.get("/api/me")
def me(request: Request):
    require_telegram_auth(request)
    uid, name = parse_telegram_user(request)
    return {"telegram_user_id": uid, "name": name, "is_admin": is_admin_user(uid)}


@app.get("/api/config")
def app_config():
    db = get_db()
    return {
        "warehouse_city": WAREHOUSE_CITY,
        "tribute_shop_url": TRIBUTE_SHOP_URL,
        "app_url": APP_PUBLIC_URL,
        "volumes_ml": VOLUMES_ML,
        "brands": db.get_brands(),
        "legal": {
            "name": LEGAL_SELF_EMPLOYED_NAME,
            "inn": LEGAL_INN,
            "email": LEGAL_CONTACT_EMAIL,
            "phone": LEGAL_PHONE,
            "address": LEGAL_ADDRESS or WAREHOUSE_CITY,
            "privacy_url": "/legal/privacy",
            "terms_url": "/legal/terms",
            "offer_url": "/legal/offer",
        },
        "delivery_methods": [
            {"id": k, "name_ru": v["name_ru"], "name_en": v["name_en"]}
            for k, v in DELIVERY_METHODS.items()
        ],
    }


@app.get("/api/legal")
def legal_api():
    return {
        "published": LEGAL_PUBLISHED,
        "seller": {
            "name": LEGAL_SELF_EMPLOYED_NAME,
            "inn": LEGAL_INN,
            "email": LEGAL_CONTACT_EMAIL,
            "phone": LEGAL_PHONE,
            "address": LEGAL_ADDRESS or WAREHOUSE_CITY,
            "tax_status": "self_employed",
        },
        "urls": {
            "privacy": "/legal/privacy",
            "terms": "/legal/terms",
            "offer": "/legal/offer",
        },
    }


def catalog(brand: str | None = None, gender: str | None = None, q: str | None = None):
    return {"items": get_db().list_products(brand=brand, gender=gender, q=q)}


@app.get("/api/catalog/{product_id}")
def product_detail(product_id: str):
    item = get_db().get_product(product_id)
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return item


@app.get("/api/orders/my")
def my_orders(request: Request):
    require_telegram_auth(request)
    uid, _ = parse_telegram_user(request)
    return {"items": get_db().list_user_orders(uid)}


@app.post("/api/delivery/estimate")
def delivery_estimate(body: DeliveryEstimateIn):
    return estimate_delivery(
        city=body.city, region=body.region, method=body.method, items_count=body.items_count,
    )


@app.post("/api/delivery/methods")
def delivery_methods(body: DeliveryEstimateIn):
    return {
        "methods": list_methods(city=body.city, region=body.region, items_count=body.items_count),
        "warehouse": WAREHOUSE_CITY,
    }


@app.post("/api/orders")
async def create_order(body: OrderIn, request: Request):
    require_telegram_auth(request)
    uid, name = parse_telegram_user(request)

    delivery = estimate_delivery(
        city=body.city,
        region=body.region,
        method=body.delivery_method,
        items_count=sum(i.qty for i in body.items),
    )
    if not delivery["available"]:
        raise HTTPException(status_code=400, detail="Delivery method not available")

    try:
        order = get_db().create_order({
            "items": [i.model_dump() for i in body.items],
            "telegram_user_id": uid,
            "telegram_username": name,
            "city": body.city,
            "region": body.region,
            "address": body.address,
            "postal_code": body.postal_code,
            "delivery_method": body.delivery_method,
            "comment": body.comment,
            "delivery_estimate_rub": delivery["cost_rub"],
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await notify_admins_new_order(order)

    return {
        "order_id": order["id"],
        "subtotal_rub": order["subtotal_rub"],
        "delivery_estimate_rub": order["delivery_estimate_rub"],
        "total_goods_rub": order["subtotal_rub"],
        "delivery_note_ru": delivery["note_ru"],
        "delivery_note_en": delivery["note_en"],
        "payment_url": order.get("payment_url"),
        "status": order["status"],
    }


# --- Admin ---

@app.get("/api/admin/products")
def admin_list_products(request: Request):
    require_admin(request)
    return {"items": get_db().list_products_admin()}


@app.post("/api/admin/products")
def admin_create_product(body: ProductIn, request: Request):
    require_admin(request)
    try:
        return get_db().create_product(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/admin/products/{product_id}")
def admin_update_product(product_id: str, body: ProductUpdate, request: Request):
    require_admin(request)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return get_db().update_product(product_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/admin/products/{product_id}")
def admin_delete_product(product_id: str, request: Request):
    require_admin(request)
    try:
        get_db().delete_product(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/admin/upload")
async def admin_upload(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD:
        raise HTTPException(status_code=400, detail="invalid_file_type")
    name = f"{uuid.uuid4().hex}{suffix}"
    dest = UPLOADS_DIR / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/uploads/{name}"}


@app.get("/api/admin/orders")
def admin_list_orders(request: Request, status: str | None = None):
    require_admin(request)
    return {"items": get_db().list_orders(status=status)}


@app.patch("/api/admin/orders/{order_id}")
async def admin_update_order(order_id: str, body: OrderStatusIn, request: Request):
    require_admin(request)
    try:
        order = get_db().update_order_status(order_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if order.get("telegram_user_id"):
        await notify_user_order_status(order, order["telegram_user_id"])
    return order


@app.get("/api/admin/admins")
def admin_list_admins(request: Request):
    require_admin(request)
    return {"ids": get_db().list_admins()}


@app.post("/api/admin/admins")
def admin_add_admin(body: AdminIn, request: Request):
    require_admin(request)
    tid = body.telegram_id.strip()
    if not tid.isdigit():
        raise HTTPException(status_code=400, detail="invalid_telegram_id")
    get_db().add_admin(tid)
    return {"ok": True, "ids": get_db().list_admins()}


@app.delete("/api/admin/admins/{telegram_id}")
def admin_remove_admin(telegram_id: str, request: Request):
    require_admin(request)
    try:
        get_db().remove_admin(telegram_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "ids": get_db().list_admins()}


@app.post("/api/webhooks/tribute")
@app.post("/webhook/tribute")
async def tribute_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("trbt-signature") or request.headers.get("x-tribute-signature")
    if not verify_tribute_signature(body, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")
    data = json.loads(body.decode() or "{}")
    return process_tribute_webhook(data)


@app.get("/")
def index():
    return FileResponse(WEBAPP_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(WEBAPP_DIR / "admin.html")


@app.get("/legal/{page}")
def legal_page(page: str):
    if page not in LEGAL_PAGES:
        raise HTTPException(status_code=404)
    return HTMLResponse(_render_legal(page))


def _safe_webapp_path(*parts: str) -> Path:
    target = (WEBAPP_DIR.joinpath(*parts)).resolve()
    root = WEBAPP_DIR.resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=404)
    return target


@app.get("/assets/{file_path:path}")
def serve_asset(file_path: str):
    target = _safe_webapp_path("assets", file_path)
    if not target.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(target)


if UPLOADS_DIR.is_dir():
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

for sub in ("css", "js"):
    subdir = WEBAPP_DIR / sub
    if subdir.is_dir():
        app.mount(f"/{sub}", StaticFiles(directory=str(subdir)), name=f"static_{sub}")
