import { formatPrice, t } from "./i18n.js";
import { isFavorite } from "./favorites.js";

let products = [];
let brands = [];
const catalogMap = new Map();

export function getCatalogMap() {
  return catalogMap;
}

export function getProducts() {
  return products;
}

export async function loadCatalog() {
  const res = await fetch("/api/catalog");
  if (!res.ok) throw new Error("catalog failed");
  const data = await res.json();
  products = data.items || [];
  products.forEach((p) => catalogMap.set(p.id, p));
  const configRes = await fetch("/api/config");
  if (!configRes.ok) throw new Error("config failed");
  const config = await configRes.json();
  brands = config.brands || [];
  return { products, brands, config };
}

function gradientStyle(gradient) {
  if (!gradient?.length) return "background: linear-gradient(160deg, #3d2914, #8b5a2b)";
  return `background: linear-gradient(160deg, ${gradient[0]}, ${gradient[1]})`;
}

function badgeLabel(badge) {
  if (!badge) return "";
  return t(`badge_${badge}`);
}

function minPrice(product) {
  return Math.min(...product.volumes.map((v) => v.price));
}

function visualHtml(p, large = false) {
  if (p.image_url) {
    const cls = large ? "product-hero__img" : "product-card__img";
    return `<img class="${cls}" src="${p.image_url}" alt="${p.name}" loading="lazy">`;
  }
  const cls = large ? "product-hero__bottle" : "product-card__bottle";
  return `<div class="${cls}" style="${gradientStyle(p.gradient)}"></div>`;
}

function stockLabel(p) {
  const ml = p.stock_ml ?? 0;
  if (ml <= 0) return `<span class="stock-badge stock-badge--out">${t("outOfStock")}</span>`;
  if (ml < 20) return `<span class="stock-badge stock-badge--low">${t("lowStock")}</span>`;
  return "";
}

function canAdd(product, volumeMl, qty) {
  return (product.stock_ml ?? 0) >= volumeMl * qty;
}

export function renderBrandFilters(container, selectedBrand) {
  const items = [
    { brand: "", label: t("allBrands") },
    { brand: "__fav__", label: `♥ ${t("favorites")}` },
    ...brands.map((b) => ({ brand: b, label: b })),
  ];
  container.innerHTML = items
    .map(({ brand, label }) => {
      const isActive = selectedBrand == null ? brand === "" : brand === selectedBrand;
      return `<button type="button" class="filter-chip ${isActive ? "filter-chip--active" : ""}" data-brand="${escapeAttr(brand)}">${label}</button>`;
    })
    .join("");
  const active = container.querySelector(".filter-chip--active");
  active?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
}

function escapeAttr(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

export function setBrandFilterActive(container, selectedBrand) {
  container.querySelectorAll(".filter-chip").forEach((chip) => {
    const raw = chip.getAttribute("data-brand") ?? "";
    const isActive = selectedBrand == null ? raw === "" : raw === selectedBrand;
    chip.classList.toggle("filter-chip--active", isActive);
  });
  const active = container.querySelector(".filter-chip--active");
  active?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
}

export function filterProducts({ brand, gender, query, favoriteIds }) {
  let list = [...products];
  if (brand === "__fav__" && favoriteIds?.size) {
    list = list.filter((p) => favoriteIds.has(p.id));
  } else if (brand && brand !== "__fav__") {
    list = list.filter((p) => p.brand === brand);
  }
  if (gender && gender !== "all") {
    list = list.filter((p) => p.gender === gender || p.gender === "unisex");
  }
  if (query) {
    const q = query.toLowerCase();
    list = list.filter(
      (p) => p.name.toLowerCase().includes(q) || p.brand.toLowerCase().includes(q)
    );
  }
  return list;
}

export function showCatalogSkeleton(container) {
  container.innerHTML = Array.from({ length: 6 }, () => `
    <article class="product-card product-card--skeleton">
      <div class="skeleton skeleton--visual"></div>
      <div class="product-card__body">
        <div class="skeleton skeleton--line skeleton--sm"></div>
        <div class="skeleton skeleton--line skeleton--lg"></div>
        <div class="skeleton skeleton--line skeleton--md"></div>
      </div>
    </article>`).join("");
}

export function renderCatalogGrid(container, list, onProductClick, onFavoriteToggle) {
  if (!list.length) {
    container.innerHTML = `<p class="cart-empty">${t("noResults")}</p>`;
    return;
  }
  container.innerHTML = list
    .map(
      (p) => `
    <article class="product-card" data-id="${p.id}">
      <button type="button" class="product-card__fav ${isFavorite(p.id) ? "product-card__fav--active" : ""}" data-fav="${p.id}" aria-label="${t("favorite")}">♥</button>
      <div class="product-card__visual">
        ${p.badge ? `<span class="product-card__badge">${badgeLabel(p.badge)}</span>` : ""}
        ${stockLabel(p)}
        ${visualHtml(p)}
      </div>
      <div class="product-card__body">
        <p class="product-card__sku">${p.sku || ""}</p>
        <p class="product-card__brand">${p.brand}</p>
        <h3 class="product-card__name">${p.name}</h3>
        ${p.fragrance_family ? `<p class="product-card__family">${p.fragrance_family}</p>` : ""}
        <div class="product-card__meta">
          <span class="product-card__conc">${p.concentration}</span>
          <span class="product-card__price">${t("from")} ${formatPrice(minPrice(p))} <small>/ 1${t("perMl")}</small></span>
        </div>
      </div>
    </article>`
    )
    .join("");

  container.querySelectorAll(".product-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".product-card__fav")) return;
      onProductClick(card.dataset.id);
    });
  });
  container.querySelectorAll(".product-card__fav").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      onFavoriteToggle?.(btn.dataset.fav, btn);
    });
  });
}

export function renderProductDetail(container, product, state, handlers) {
  const { selectedVolume, qty } = state;
  const vol = product.volumes.find((v) => v.ml === selectedVolume) || product.volumes[0];
  const favActive = isFavorite(product.id);
  const canBuy = canAdd(product, selectedVolume, qty);

  container.innerHTML = `
    <button type="button" class="product-fav-btn ${favActive ? "product-fav-btn--active" : ""}" id="productFavBtn">♥ ${t("favorite")}</button>
    <div class="product-hero">
      <div class="product-hero__visual">
        ${visualHtml(product, true)}
      </div>
      <p class="product-hero__sku">${product.sku || ""}</p>
      <p class="product-hero__brand">${product.brand}</p>
      <h2 class="product-hero__name">${product.name}</h2>
      <p class="product-hero__conc">${product.concentration} · ${t(`gender_${product.gender}`)}${product.fragrance_family ? ` · ${product.fragrance_family}` : ""}</p>
      <p class="product-hero__conc product-hero__stock">${product.stock_ml ?? 0} ${t("perMl")} ${t("inStock")}</p>
      ${product.supplier?.honest_sign ? `<p class="product-hero__cert">✓ ${t("honestSign")} · ${product.supplier.country}</p>` : ""}
      ${product.description ? `<p class="product-hero__desc">${product.description}</p>` : ""}
      <div class="notes-row">
        ${product.notes.map((n) => `<span class="note-tag">${n}</span>`).join("")}
      </div>
    </div>

    <div class="volume-picker">
      <p class="volume-picker__label">${t("volume")}</p>
      <div class="volume-picker__grid" id="volumeGrid">
        ${product.volumes
          .map(
            (v) => `
          <button type="button" class="volume-btn ${v.ml === selectedVolume ? "volume-btn--active" : ""}" data-ml="${v.ml}">
            <span class="volume-btn__ml">${v.ml} ${t("perMl")}</span>
            <span class="volume-btn__price">${formatPrice(v.price)}</span>
          </button>`
          )
          .join("")}
      </div>
    </div>

    <div class="qty-row">
      <button type="button" class="qty-btn" id="qtyMinus">−</button>
      <span class="qty-value" id="qtyDisplay">${qty}</span>
      <button type="button" class="qty-btn" id="qtyPlus">+</button>
    </div>

    <button type="button" class="btn btn--primary btn--full" id="addToCartBtn" ${canBuy ? "" : "disabled"}>
      ${canBuy ? `${t("addToCart")} · ${formatPrice(vol.price * qty)}` : t("outOfStock")}
    </button>
  `;

  container.querySelector("#productFavBtn")?.addEventListener("click", handlers.onFavorite);
  container.querySelectorAll(".volume-btn").forEach((btn) => {
    btn.addEventListener("click", () => handlers.onVolume(Number(btn.dataset.ml)));
  });
  container.querySelector("#qtyMinus").addEventListener("click", () => handlers.onQty(Math.max(1, qty - 1)));
  container.querySelector("#qtyPlus").addEventListener("click", () => handlers.onQty(qty + 1));
  container.querySelector("#addToCartBtn")?.addEventListener("click", () => {
    if (canAdd(product, selectedVolume, qty)) handlers.onAdd();
  });
}
