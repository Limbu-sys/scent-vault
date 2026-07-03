import { formatPrice, getLang, t } from "./i18n.js";

let estimateTimer = null;

export async function fetchDeliveryMethods(city, region, itemsCount = 1) {
  const res = await fetch("/api/delivery/methods", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ city, region, items_count: itemsCount }),
  });
  if (!res.ok) throw new Error("delivery methods failed");
  const data = await res.json();
  return data.methods;
}

export async function fetchDeliveryEstimate(city, region, method, itemsCount) {
  const res = await fetch("/api/delivery/estimate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ city, region, method, items_count: itemsCount }),
  });
  if (!res.ok) throw new Error("delivery estimate failed");
  return res.json();
}

export function renderDeliveryMethods(container, methods, selectedId, onSelect) {
  const lang = getLang();
  container.innerHTML = methods
    .map(
      (m) => `
    <label class="delivery-option ${m.id === selectedId ? "delivery-option--active" : ""} ${!m.available ? "delivery-option--disabled" : ""}">
      <input type="radio" name="delivery" value="${m.id}" ${m.id === selectedId ? "checked" : ""} ${!m.available ? "disabled" : ""}>
      <div class="delivery-option__info">
        <div class="delivery-option__name">${lang === "en" ? m.name_en : m.name_ru}</div>
        <div class="delivery-option__meta">${m.days_min}–${m.days_max} ${t("days")}</div>
      </div>
      <div class="delivery-option__price">${
        !m.available
          ? t("unavailable")
          : m.cost_rub === 0
            ? t("free")
            : formatPrice(m.cost_rub)
      }</div>
    </label>`
    )
    .join("");

  container.querySelectorAll(".delivery-option").forEach((label) => {
    if (label.classList.contains("delivery-option--disabled")) return;
    label.addEventListener("click", () => {
      const input = label.querySelector("input");
      onSelect(input.value);
    });
  });
}

export function scheduleDeliveryUpdate({ city, region, method, itemsCount, onResult }) {
  clearTimeout(estimateTimer);
  estimateTimer = setTimeout(async () => {
    if (!city.trim()) return;
    try {
      const [methods, estimate] = await Promise.all([
        fetchDeliveryMethods(city, region, itemsCount),
        fetchDeliveryEstimate(city, region, method, itemsCount),
      ]);
      onResult({ methods, estimate });
    } catch {
      onResult(null);
    }
  }, 400);
}

export function formatDeliveryCost(estimate) {
  if (!estimate) return "—";
  if (!estimate.available) return t("unavailable");
  if (estimate.cost_rub === 0) return t("free");
  return formatPrice(estimate.cost_rub);
}
