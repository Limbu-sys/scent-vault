import {
  addToCart,
  cartItemsForOrder,
  clearCart,
  getCartCount,
  getCartSubtotal,
  loadCart,
  removeFromCart,
  updateQty,
} from "./cart.js";
import {
  filterProducts,
  getCatalogMap,
  loadCatalog,
  renderBrandFilters,
  renderCatalogGrid,
  renderProductDetail,
  setBrandFilterActive,
  showCatalogSkeleton,
} from "./catalog.js";
import {
  formatDeliveryCost,
  renderDeliveryMethods,
  scheduleDeliveryUpdate,
} from "./delivery.js";
import { toggleFavorite, loadFavorites } from "./favorites.js";
import { applyI18n, formatPrice, setLang, t } from "./i18n.js";

const tg = window.Telegram?.WebApp;

function authHeaders(extra = {}) {
  const h = { ...extra };
  if (tg?.initData) h["X-Telegram-Init-Data"] = tg.initData;
  return h;
}

async function apiFetch(url, opts = {}) {
  return fetch(url, {
    ...opts,
    headers: { ...authHeaders(), ...opts.headers },
  });
}

let currentView = "catalog";
let selectedBrand = null;
let selectedGender = "all";
let searchQuery = "";
let currentProduct = null;
let productState = { selectedVolume: 1, qty: 1 };
let deliveryMethod = "cdek_pvz";
let appConfig = {};
let favoriteIds = loadFavorites();

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.enableClosingConfirmation();
  const scheme = tg.colorScheme;
  if (scheme === "light" && !localStorage.getItem("sv_theme")) {
    setTheme("light");
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("sv_theme", theme);
  const label = $("#themeLabel");
  if (label) label.textContent = theme === "dark" ? t("themeDark") : t("themeLight");
  if (tg) {
    try {
      tg.setHeaderColor(theme === "dark" ? "#0a0908" : "#faf7f2");
      tg.setBackgroundColor(theme === "dark" ? "#0a0908" : "#faf7f2");
    } catch { /* ignore */ }
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme || "dark";
  setTheme(current === "dark" ? "light" : "dark");
}

function showView(name) {
  currentView = name;
  $$(".view").forEach((v) => v.classList.toggle("view--active", v.dataset.view === name));
  $$(".tabbar__btn").forEach((btn) => {
    btn.classList.toggle("tabbar__btn--active", btn.dataset.tab === name && ["catalog", "cart", "settings"].includes(name));
  });
  const tabbar = $("#tabbar");
  if (tabbar) {
    tabbar.classList.toggle("hidden", ["product", "checkout", "success", "orders"].includes(name));
  }
  if (tg?.MainButton) {
    if (name === "checkout") {
      tg.MainButton.setText(t("placeOrder"));
      tg.MainButton.show();
    } else {
      tg.MainButton.hide();
    }
  }
  $("#mainScroll")?.scrollTo(0, 0);
}

function showToast(msg) {
  const toast = $("#toast");
  toast.textContent = msg;
  toast.classList.add("toast--visible");
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove("toast--visible"), 2200);
}

function updateCartBadge() {
  const count = getCartCount();
  const badge = $("#cartBadge");
  badge.textContent = count;
  badge.classList.toggle("hidden", count === 0);
}

function selectBrand(brand) {
  selectedBrand = brand;
  const filtersEl = $("#brandFilters");
  setBrandFilterActive(filtersEl, selectedBrand);
  refreshCatalog();
}

function refreshCatalog() {
  const list = filterProducts({
    brand: selectedBrand,
    gender: selectedGender,
    query: searchQuery,
    favoriteIds,
  });
  const emptyMsg = selectedBrand === "__fav__" ? t("noFavorites") : t("noResults");
  if (!list.length) {
    $("#catalogGrid").innerHTML = `<p class="cart-empty">${emptyMsg}</p>`;
    return;
  }
  renderCatalogGrid($("#catalogGrid"), list, openProduct, handleFavoriteToggle);
}

function handleFavoriteToggle(productId, btn) {
  const added = toggleFavorite(productId);
  favoriteIds = loadFavorites();
  btn?.classList.toggle("product-card__fav--active", added);
  if (currentProduct?.id === productId) {
    const favBtn = $("#productFavBtn");
    favBtn?.classList.toggle("product-fav-btn--active", added);
    favBtn.textContent = `♥ ${t("favorite")}`;
  }
  showToast(added ? t("favoriteAdded") : t("favoriteRemoved"));
  if (selectedBrand === "__fav__") refreshCatalog();
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
}

function openProduct(id) {
  const product = getCatalogMap().get(id);
  if (!product) return;
  currentProduct = product;
  productState = { selectedVolume: product.volumes[0]?.ml || 1, qty: 1 };
  renderProduct();
  showView("product");
}

function renderProduct() {
  if (!currentProduct) return;
  renderProductDetail($("#productDetail"), currentProduct, productState, {
    onVolume: (ml) => {
      productState.selectedVolume = ml;
      renderProduct();
    },
    onQty: (qty) => {
      productState.qty = qty;
      renderProduct();
    },
    onAdd: () => {
      const vol = productState.selectedVolume;
      const needed = vol * productState.qty;
      if ((currentProduct.stock_ml ?? 0) < needed) {
        showToast(t("outOfStock"));
        return;
      }
      addToCart(currentProduct.id, productState.selectedVolume, productState.qty);
      showToast(t("addedToCart"));
      updateCartBadge();
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    },
    onFavorite: () => handleFavoriteToggle(currentProduct.id),
  });
}

function renderCart() {
  const items = loadCart();
  const map = getCatalogMap();
  const container = $("#cartContent");
  const summary = $("#cartSummary");

  if (!items.length) {
    container.innerHTML = `
      <div class="cart-empty anim-rise">
        <div class="cart-empty__icon">🛍</div>
        <p>${t("cartEmpty")}</p>
        <p style="margin-top:8px;font-size:13px">${t("cartEmptyHint")}</p>
        <button type="button" class="btn btn--ghost" style="margin-top:20px" id="emptyGoCatalog">${t("goCatalog")}</button>
      </div>`;
    summary.classList.add("hidden");
    $("#emptyGoCatalog")?.addEventListener("click", () => showView("catalog"));
    return;
  }

  container.innerHTML = items
    .map((item) => {
      const p = map.get(item.product_id);
      if (!p) return "";
      const vol = p.volumes.find((v) => v.ml === item.volume_ml);
      const lineTotal = (vol?.price || 0) * item.qty;
      return `
      <div class="cart-item" data-pid="${item.product_id}" data-vol="${item.volume_ml}">
        <div class="cart-item__swatch" style="background: linear-gradient(160deg, ${p.gradient[0]}, ${p.gradient[1]})"></div>
        <div class="cart-item__info">
          <p class="cart-item__brand">${p.brand}</p>
          <p class="cart-item__name">${p.name}</p>
          <p class="cart-item__vol">${item.volume_ml} ${t("perMl")} · ${p.sku || ""}</p>
          <div class="cart-item__bottom">
            <span class="cart-item__price">${formatPrice(lineTotal)}</span>
            <div class="cart-item__qty">
              <button type="button" class="qty-dec">−</button>
              <span>${item.qty}</span>
              <button type="button" class="qty-inc">+</button>
            </div>
          </div>
          <button type="button" class="cart-item__remove">${t("remove")}</button>
        </div>
      </div>`;
    })
    .join("");

  const subtotal = getCartSubtotal(map);
  $("#cartSubtotal").textContent = formatPrice(subtotal);
  summary.classList.remove("hidden");

  container.querySelectorAll(".cart-item").forEach((row) => {
    const pid = row.dataset.pid;
    const vol = Number(row.dataset.vol);
    row.querySelector(".qty-dec").addEventListener("click", () => {
      const item = loadCart().find((i) => i.product_id === pid && i.volume_ml === vol);
      updateQty(pid, vol, (item?.qty || 1) - 1);
      renderCart();
      updateCartBadge();
    });
    row.querySelector(".qty-inc").addEventListener("click", () => {
      const item = loadCart().find((i) => i.product_id === pid && i.volume_ml === vol);
      updateQty(pid, vol, (item?.qty || 0) + 1);
      renderCart();
      updateCartBadge();
    });
    row.querySelector(".cart-item__remove").addEventListener("click", () => {
      removeFromCart(pid, vol);
      renderCart();
      updateCartBadge();
    });
  });
}

function openCheckout() {
  if (!loadCart().length) return;
  showView("checkout");
  const map = getCatalogMap();
  $("#checkoutSubtotal").textContent = formatPrice(getCartSubtotal(map));
  updateDeliveryUI();
}

async function updateDeliveryUI() {
  const city = $("#cityInput").value.trim();
  const region = $("#regionInput").value.trim();
  const itemsCount = getCartCount();

  scheduleDeliveryUpdate({
    city,
    region,
    method: deliveryMethod,
    itemsCount,
    onResult: (data) => {
      if (!data) return;
      const available = data.methods.filter((m) => m.available);
      if (!available.find((m) => m.id === deliveryMethod)) {
        deliveryMethod = available[0]?.id || "cdek_pvz";
      }
      renderDeliveryMethods($("#deliveryMethods"), data.methods, deliveryMethod, (id) => {
        deliveryMethod = id;
        updateDeliveryUI();
      });
      $("#deliveryCost").textContent = formatDeliveryCost(data.estimate);
    },
  });
}

async function placeOrder(e) {
  e.preventDefault();
  const city = $("#cityInput").value.trim();
  const address = $("#addressInput").value.trim();
  if (!city || !address) {
    showToast(t("fillAddress"));
    return;
  }

  const btn = $("#placeOrderBtn");
  btn.disabled = true;

  const payload = {
    items: cartItemsForOrder(),
    city,
    region: $("#regionInput").value.trim(),
    address,
    postal_code: $("#postalInput").value.trim(),
    delivery_method: deliveryMethod,
    comment: $("#commentInput").value.trim(),
    telegram_user_id: tg?.initDataUnsafe?.user?.id || null,
    telegram_username: tg?.initDataUnsafe?.user?.username || null,
  };

  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      const detail = data.detail;
      const msg = Array.isArray(detail)
        ? detail.map((d) => d.msg).join(", ")
        : typeof detail === "string"
          ? detail
          : t("orderError");
      throw new Error(msg);
    }

    $("#successOrderId").textContent = data.order_id;
    clearCart();
    updateCartBadge();

    const payBtn = $("#successPayBtn");
    const payHint = $("#successPayHint");
    if (data.payment_url) {
      payBtn.href = data.payment_url;
      payBtn.classList.remove("hidden");
      $("#successHomeBtn").classList.remove("btn--primary");
      $("#successHomeBtn").classList.add("btn--ghost");
      if (tg?.openLink) {
        payBtn.addEventListener("click", (ev) => {
          ev.preventDefault();
          tg.openLink(data.payment_url);
        }, { once: true });
      }
    } else {
      payBtn.classList.add("hidden");
    }
    if (payHint) {
      payHint.textContent = t("payHint").replace("НОМЕР_ЗАКАЗА", data.order_id).replace("ORDER_ID", data.order_id);
    }

    if (data.payment_url && tg?.openLink) {
      tg.openLink(data.payment_url);
    } else if (data.payment_url) {
      window.open(data.payment_url, "_blank");
    }

    showView("success");
  } catch (err) {
    showToast(err.message || t("orderError"));
    console.error(err);
  } finally {
    btn.disabled = false;
  }
}

function renderOrders() {
  const container = $("#ordersContent");
  container.innerHTML = `<p class="cart-empty">${t("loading")}</p>`;
  apiFetch("/api/orders/my")
    .then((r) => r.json())
    .then((data) => {
      const items = data.items || [];
      if (!items.length) {
        container.innerHTML = `<p class="cart-empty">${t("noOrders")}</p>`;
        return;
      }
      const statusMap = {
        pending_payment: t("statusPending"),
        paid: t("statusPaid"),
        processing: t("statusProcessing"),
        shipped: t("statusShipped"),
        delivered: t("statusDelivered"),
        cancelled: t("statusCancelled"),
      };
      container.innerHTML = items
        .map(
          (o) => `
        <div class="order-card">
          <div class="order-card__head">
            <span class="order-card__id">#${o.id}</span>
            <span class="order-card__status">${statusMap[o.status] || o.status}</span>
          </div>
          <p class="order-card__sum">${formatPrice(o.subtotal_rub)}</p>
          <ul class="order-card__items">
            ${(o.items || []).map((it) => `<li>${it.sku} ${it.brand} ${it.name} — ${it.volume_ml}мл ×${it.qty}</li>`).join("")}
          </ul>
          ${o.payment_url && o.status === "pending_payment" ? `<a class="btn btn--primary btn--full" href="${o.payment_url}" target="_blank">${t("payNow")}</a>` : ""}
        </div>`
        )
        .join("");
    })
    .catch(() => {
      container.innerHTML = `<p class="cart-empty">${t("loadError")}</p>`;
    });
}

function bindEvents() {
  $("#themeToggle").addEventListener("click", toggleTheme);
  $("#settingsThemeToggle").addEventListener("click", toggleTheme);

  document.querySelectorAll("#langSwitch, #settingsLangSwitch").forEach((wrap) => {
    wrap.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-lang]");
      if (btn) setLang(btn.dataset.lang);
    });
  });

  document.addEventListener("langchange", () => {
    applyI18n();
    setTheme(document.documentElement.dataset.theme || "dark");
    renderBrandFilters($("#brandFilters"), selectedBrand);
    refreshCatalog();
    if (currentProduct) renderProduct();
    if (currentView === "cart") renderCart();
  });

  document.addEventListener("cartchange", updateCartBadge);

  document.addEventListener("favoriteschange", () => {
    favoriteIds = loadFavorites();
    if (selectedBrand === "__fav__") refreshCatalog();
  });

  $("#brandFilters").addEventListener("click", (e) => {
    const btn = e.target.closest(".filter-chip");
    if (!btn) return;
    const brand = btn.dataset.brand;
    selectBrand(brand === "" || brand === undefined ? null : brand);
  });

  $("#searchInput").addEventListener("input", (e) => {
    searchQuery = e.target.value.trim();
    refreshCatalog();
  });

  $("#genderTabs").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-gender]");
    if (!btn) return;
    selectedGender = btn.dataset.gender;
    $$("#genderTabs .gender-tabs__btn").forEach((b) =>
      b.classList.toggle("gender-tabs__btn--active", b === btn)
    );
    refreshCatalog();
  });

  $("#productBack").addEventListener("click", () => showView("catalog"));
  $("#checkoutBack").addEventListener("click", () => showView("cart"));
  $("#checkoutBtn").addEventListener("click", openCheckout);
  $("#checkoutForm").addEventListener("submit", placeOrder);
  $("#successHomeBtn").addEventListener("click", () => showView("catalog"));
  $("#ordersLink").addEventListener("click", () => {
    renderOrders();
    showView("orders");
  });
  $("#ordersBack").addEventListener("click", () => showView("settings"));

  if (tg?.MainButton) {
    tg.MainButton.onClick(() => {
      if (currentView === "checkout") $("#checkoutForm").requestSubmit();
    });
  }

  if (!localStorage.getItem("sv_legal_ok")) {
    requestAnimationFrame(() => $("#legalModal")?.showModal());
  }
  $("#legalAccept")?.addEventListener("click", () => {
    localStorage.setItem("sv_legal_ok", "1");
    $("#legalModal")?.close();
  });

  ["cityInput", "regionInput"].forEach((id) => {
    $("#" + id).addEventListener("input", updateDeliveryUI);
  });

  $("#tabbar").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-tab]");
    if (!btn) return;
    const tab = btn.dataset.tab;
    if (tab === "cart") renderCart();
    showView(tab);
  });

  document.querySelectorAll(".topbar__logo img").forEach((img) => {
    img.addEventListener("error", () => {
      const fallback = img.dataset.fallback;
      if (fallback && img.src !== fallback) img.src = fallback;
    });
  });
}

async function init() {
  try {
    const savedTheme = localStorage.getItem("sv_theme") || "dark";
    document.documentElement.dataset.theme = savedTheme;

    applyI18n();
    initTelegram();
    setTheme(savedTheme);
    bindEvents();
    updateCartBadge();

    showCatalogSkeleton($("#catalogGrid"));

    const { config } = await loadCatalog();
    appConfig = config;
    if (config.warehouse_city) $("#warehouseLabel").textContent = config.warehouse_city;

    renderBrandFilters($("#brandFilters"), selectedBrand);
    refreshCatalog();

    try {
      const meRes = await apiFetch("/api/me");
      if (meRes.ok) {
        const me = await meRes.json();
        if (me.is_admin) $("#adminLink")?.classList.remove("hidden");
      }
    } catch { /* ignore */ }

    // fallback: show admin if Telegram user id matches (when /api/me unavailable)
    const tgUid = String(tg?.initDataUnsafe?.user?.id || "");
    if (tgUid === "122429011") $("#adminLink")?.classList.remove("hidden");
  } catch (err) {
    console.error(err);
    $("#catalogGrid").innerHTML = `<p class="cart-empty">${t("loadError")}</p>`;
    showToast(t("loadError"));
  }
}

init();
