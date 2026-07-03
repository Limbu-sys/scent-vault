"""2GIS Catalog API — поиск поставщиков парфюмерии."""

from __future__ import annotations

from typing import Any

import httpx

from config import DGIS_API_KEY

API_BASE = "https://catalog.api.2gis.com/3.0"

# lat, lon — центр поиска
CITY_PRESETS: dict[str, dict[str, float | str]] = {
    "krasnodar": {"lat": 45.035470, "lon": 38.975313, "label": "Краснодар"},
    "moscow": {"lat": 55.7558, "lon": 37.6173, "label": "Москва"},
    "spb": {"lat": 59.9343, "lon": 30.3351, "label": "Санкт-Петербург"},
}

DEFAULT_QUERIES = (
    "парфюмерия опт",
    "арomatovary",
    "отдушки",
    "парфюмерное сырье",
)


class DgisError(Exception):
    pass


def _client() -> httpx.Client:
    return httpx.Client(timeout=30.0)


def _require_key() -> str:
    key = (DGIS_API_KEY or "").strip()
    if not key:
        raise DgisError("dgis_key_missing")
    return key


def search_branches(
    query: str,
    *,
    lat: float,
    lon: float,
    page_size: int = 20,
    page: int = 1,
) -> dict[str, Any]:
    """Поиск филиалов (type=branch) в радиусе от точки."""
    key = _require_key()
    fields = "items.contact_groups,items.rubrics,items.address_name,items.address,items.links"
    params = {
        "q": query,
        "location": f"{lon},{lat}",
        "type": "branch",
        "page_size": min(page_size, 10),
        "page": page,
        "fields": fields,
        "key": key,
    }
    with _client() as client:
        resp = client.get(f"{API_BASE}/items", params=params)
    data = resp.json()
    meta = data.get("meta", {})
    if meta.get("error"):
        err = meta["error"]
        raise DgisError(f"2gis_{err.get('type', 'error')}: {err.get('message', '')}")
    if resp.status_code >= 400:
        raise DgisError(f"2gis_http_{resp.status_code}")
    return data.get("result") or {}


def _first_contacts(contact_groups: list[dict] | None) -> dict[str, str]:
    phones: list[str] = []
    emails: list[str] = []
    sites: list[str] = []
    for group in contact_groups or []:
        for c in group.get("contacts") or []:
            val = (c.get("text") or c.get("value") or "").strip()
            if not val:
                continue
            ctype = (c.get("type") or "").lower()
            if ctype == "phone":
                phones.append(val)
            elif ctype == "email":
                emails.append(val)
            elif ctype in {"website", "url"}:
                sites.append(val)
    return {
        "phone": phones[0] if phones else "",
        "phones_extra": ", ".join(phones[1:3]),
        "contact_email": emails[0] if emails else "",
        "website": sites[0] if sites else "",
    }


def _rubrics_text(rubrics: list[dict] | None) -> str:
    names = [(r.get("name") or "").strip() for r in (rubrics or [])]
    return ", ".join(n for n in names if n)


def _address_text(item: dict) -> str:
    if item.get("address_name"):
        return str(item["address_name"]).strip()
    addr = item.get("address") or {}
    parts = [addr.get("building_name"), addr.get("name")]
    return ", ".join(p for p in parts if p)


def item_to_supplier_draft(item: dict, *, city_label: str = "") -> dict[str, Any]:
    """Преобразует объект 2GIS в черновик поставщика для CRM."""
    dgis_id = str(item.get("id") or "")
    contacts = _first_contacts(item.get("contact_groups"))
    rubrics = _rubrics_text(item.get("rubrics"))
    address = _address_text(item)
    link = f"https://2gis.ru/firm/{dgis_id}" if dgis_id else ""

    notes_parts = [f"2GIS: {link}"]
    if rubrics:
        notes_parts.append(f"Рубрики: {rubrics}")
    if contacts.get("phones_extra"):
        notes_parts.append(f"Доп. тел.: {contacts['phones_extra']}")
    if not contacts.get("phone") and not contacts.get("contact_email"):
        notes_parts.append(
            "Телефон/e-mail: откройте карточку в 2GIS или запросите расширенный доступ API (contact_groups)."
        )

    region = city_label or ""
    return {
        "id": f"dgis-{dgis_id}" if dgis_id else "",
        "dgis_id": dgis_id,
        "name": (item.get("name") or "").strip(),
        "country": "Россия",
        "region": region,
        "address": address,
        "phone": contacts["phone"],
        "contact_email": contacts["contact_email"],
        "website": contacts["website"],
        "notes": "\n".join(notes_parts),
        "fragrances_offered": rubrics,
        "origin_type": "oil_concentrate",
        "origin_note": "",
        "active": True,
        "_2gis_link": link,
        "_has_contacts": bool(contacts["phone"] or contacts["contact_email"] or contacts["website"]),
    }


def collect_leads(
    queries: list[str] | None = None,
    *,
    lat: float,
    lon: float,
    city_label: str = "",
    page_size: int = 20,
) -> list[dict[str, Any]]:
    """Ищет по нескольким запросам, дедуплицирует по id 2GIS."""
    qlist = [q.strip() for q in (queries or DEFAULT_QUERIES) if q.strip()]
    seen: set[str] = set()
    leads: list[dict[str, Any]] = []
    for query in qlist:
        try:
            result = search_branches(query, lat=lat, lon=lon, page_size=page_size)
        except DgisError:
            continue
        for item in result.get("items") or []:
            iid = str(item.get("id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            draft = item_to_supplier_draft(item, city_label=city_label)
            draft["_query"] = query
            leads.append(draft)
    return leads
