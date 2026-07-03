const tg = window.Telegram?.WebApp;

function authHeaders(extra = {}) {
  const h = { ...extra };
  if (tg?.initData) h["X-Telegram-Init-Data"] = tg.initData;
  return h;
}

async function api(path, opts = {}) {
  const isForm = opts.body instanceof FormData;
  const headers = authHeaders(isForm ? {} : { "Content-Type": "application/json" });
  const res = await fetch(path, { ...opts, headers: { ...headers, ...opts.headers } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "error");
  return data;
}

const $ = (s) => document.querySelector(s);
const toast = $("#toast");
let products = [];

const STATUS_LABELS = {
  pending_payment: "⏳ Ожидает",
  paid: "✅ Оплачен",
  processing: "📦 Сборка",
  shipped: "🚚 Отправлен",
  delivered: "🎉 Доставлен",
  cancelled: "❌ Отменён",
};

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("toast--visible");
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.remove("toast--visible"), 2500);
}

async function checkAccess() {
  try {
    const me = await api("/api/me");
    if (!me.is_admin) {
      $("#accessDenied").classList.remove("hidden");
      return false;
    }
    $("#adminPanel").classList.remove("hidden");
    return true;
  } catch {
    $("#accessDenied").classList.remove("hidden");
    return false;
  }
}

function renderProducts() {
  const list = $("#productList");
  if (!products.length) {
    list.innerHTML = "<p class='admin-card__hint'>Нет товаров</p>";
    return;
  }
  list.innerHTML = products
    .map(
      (p) => `
    <div class="admin-item" data-id="${p.id}">
      <div class="admin-item__info">
        <div class="admin-item__sku">${p.sku} ${!p.active ? "· скрыт" : ""}</div>
        <div class="admin-item__title">${p.brand} — ${p.name}</div>
        <div class="admin-item__meta">${p.concentration} · ${p.base_price_per_ml} ₽/мл · ${p.stock_ml} мл</div>
      </div>
      <div class="admin-item__actions">
        <button type="button" class="btn-edit" data-id="${p.id}">Изм.</button>
        <button type="button" class="btn-del" data-id="${p.id}">Удал.</button>
      </div>
    </div>`
    )
    .join("");
  list.querySelectorAll(".btn-edit").forEach((b) => b.addEventListener("click", () => openEdit(b.dataset.id)));
  list.querySelectorAll(".btn-del").forEach((b) => b.addEventListener("click", () => deleteProduct(b.dataset.id)));
}

async function loadProducts() {
  const data = await api("/api/admin/products");
  products = data.items || [];
  renderProducts();
}

async function uploadImage(file) {
  const fd = new FormData();
  fd.append("file", file);
  return api("/api/admin/upload", { method: "POST", body: fd });
}

function openModal(create = true, product = null) {
  $("#modalTitle").textContent = create ? "Новый товар" : "Редактировать";
  $("#editProductId").value = product?.id || "";
  $("#skuDisplay").classList.toggle("hidden", create);
  $("#skuDisplay").textContent = product?.sku ? `Артикул: ${product.sku}` : "";
  $("#fBrand").value = product?.brand || "";
  $("#fName").value = product?.name || "";
  $("#fDesc").value = product?.description || "";
  $("#fGender").value = product?.gender || "unisex";
  $("#fConc").value = product?.concentration || "EDP";
  $("#fPrice").value = product?.base_price_per_ml || "";
  $("#fStock").value = product?.stock_ml ?? 100;
  $("#fNotes").value = (product?.notes || []).join(", ");
  $("#fBadge").value = product?.badge || "";
  $("#fGrad1").value = product?.gradient?.[0] || "#3d2914";
  $("#fGrad2").value = product?.gradient?.[1] || "#8b5a2b";
  $("#fImageUrl").value = product?.image_url || "";
  $("#fActive").checked = product?.active !== false;
  const prev = $("#fImagePreview");
  if (product?.image_url) {
    prev.src = product.image_url;
    prev.classList.remove("hidden");
  } else {
    prev.classList.add("hidden");
  }
  $("#productModal").showModal();
}

function openEdit(id) {
  const p = products.find((x) => x.id === id);
  if (p) openModal(false, p);
}

async function deleteProduct(id) {
  if (!confirm("Удалить товар?")) return;
  try {
    await api(`/api/admin/products/${id}`, { method: "DELETE" });
    showToast("Удалено");
    await loadProducts();
  } catch (e) {
    showToast(e.message);
  }
}

$("#fImage").addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  try {
    const { url } = await uploadImage(file);
    $("#fImageUrl").value = url;
    $("#fImagePreview").src = url;
    $("#fImagePreview").classList.remove("hidden");
    showToast("Фото загружено");
  } catch (err) {
    showToast(err.message);
  }
});

$("#productForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    brand: $("#fBrand").value.trim(),
    name: $("#fName").value.trim(),
    description: $("#fDesc").value.trim(),
    gender: $("#fGender").value,
    concentration: $("#fConc").value.trim(),
    base_price_per_ml: Number($("#fPrice").value),
    stock_ml: Number($("#fStock").value),
    notes: $("#fNotes").value.split(",").map((s) => s.trim()).filter(Boolean),
    badge: $("#fBadge").value || null,
    gradient: [$("#fGrad1").value, $("#fGrad2").value],
    image_url: $("#fImageUrl").value,
    active: $("#fActive").checked,
  };
  const editId = $("#editProductId").value;
  try {
    if (editId) {
      await api(`/api/admin/products/${editId}`, { method: "PUT", body: JSON.stringify(body) });
    } else {
      await api("/api/admin/products", { method: "POST", body: JSON.stringify(body) });
    }
    showToast("Сохранено");
    $("#productModal").close();
    await loadProducts();
  } catch (err) {
    showToast(err.message);
  }
});

$("#modalCancel").addEventListener("click", () => $("#productModal").close());
$("#newProductBtn").addEventListener("click", () => openModal(true));

async function loadOrders(status = "") {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const data = await api(`/api/admin/orders${q}`);
  const list = $("#orderList");
  const items = data.items || [];
  if (!items.length) {
    list.innerHTML = "<p class='admin-card__hint'>Нет заказов</p>";
    return;
  }
  list.innerHTML = items
    .map(
      (o) => `
    <div class="admin-item">
      <div class="admin-item__info">
        <div class="admin-item__sku">#${o.id} · ${STATUS_LABELS[o.status] || o.status}</div>
        <div class="admin-item__title">${o.subtotal_rub} ₽ · ${o.city}</div>
        <div class="admin-item__meta">${(o.items || []).map((i) => `${i.sku} ${i.volume_ml}мл×${i.qty}`).join(", ")}</div>
        <div class="admin-item__meta">${o.address}</div>
      </div>
      <div class="admin-item__actions" style="flex-direction:column">
        <select class="field-input order-status" data-id="${o.id}" style="font-size:11px">
          ${Object.keys(STATUS_LABELS).map((s) => `<option value="${s}" ${s === o.status ? "selected" : ""}>${STATUS_LABELS[s]}</option>`).join("")}
        </select>
      </div>
    </div>`
    )
    .join("");
  list.querySelectorAll(".order-status").forEach((sel) => {
    sel.addEventListener("change", async () => {
      try {
        await api(`/api/admin/orders/${sel.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: sel.value }),
        });
        showToast("Статус обновлён");
      } catch (e) {
        showToast(e.message);
      }
    });
  });
}

$("#orderStatusFilter").addEventListener("change", (e) => loadOrders(e.target.value));

async function loadAdmins() {
  const data = await api("/api/admin/admins");
  $("#adminList").innerHTML = (data.ids || [])
    .map(
      (id) => `
    <div class="admin-item">
      <div class="admin-item__title">ID ${id}</div>
      <button type="button" class="btn-del" data-id="${id}">Удалить</button>
    </div>`
    )
    .join("");
  $("#adminList").querySelectorAll(".btn-del").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm(`Убрать админа ${btn.dataset.id}?`)) return;
      try {
        await api(`/api/admin/admins/${btn.dataset.id}`, { method: "DELETE" });
        showToast("Удалён");
        loadAdmins();
      } catch (e) {
        showToast(e.message);
      }
    });
  });
}

$("#addAdminBtn").addEventListener("click", async () => {
  const id = $("#newAdminId").value.trim();
  if (!id) return;
  try {
    await api("/api/admin/admins", { method: "POST", body: JSON.stringify({ telegram_id: id }) });
    $("#newAdminId").value = "";
    showToast("Добавлен");
    loadAdmins();
  } catch (e) {
    showToast(e.message);
  }
});

document.querySelectorAll(".admin-tabs__btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".admin-tabs__btn").forEach((b) =>
      b.classList.toggle("admin-tabs__btn--active", b === btn)
    );
    ["products", "orders", "admins"].forEach((t) => {
      $(`#tab-${t}`).classList.toggle("hidden", btn.dataset.tab !== t);
    });
    if (btn.dataset.tab === "orders") loadOrders($("#orderStatusFilter").value);
  });
});

async function init() {
  if (tg) { tg.ready(); tg.expand(); }
  document.documentElement.dataset.theme = localStorage.getItem("sv_theme") || "dark";
  if (!(await checkAccess())) return;
  await loadProducts();
  await loadAdmins();
}

init();
