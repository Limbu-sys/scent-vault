const STORAGE_KEY = "sv_cart";

export function loadCart() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveCart(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  document.dispatchEvent(new CustomEvent("cartchange", { detail: items }));
}

export function getCartCount() {
  return loadCart().reduce((sum, i) => sum + i.qty, 0);
}

export function getCartSubtotal(catalogMap) {
  return loadCart().reduce((sum, item) => {
    const product = catalogMap.get(item.product_id);
    if (!product) return sum;
    const vol = product.volumes.find((v) => v.ml === item.volume_ml);
    return sum + (vol?.price || 0) * item.qty;
  }, 0);
}

export function addToCart(productId, volumeMl, qty = 1) {
  const items = loadCart();
  const existing = items.find((i) => i.product_id === productId && i.volume_ml === volumeMl);
  if (existing) {
    existing.qty += qty;
  } else {
    items.push({ product_id: productId, volume_ml: volumeMl, qty });
  }
  saveCart(items);
}

export function updateQty(productId, volumeMl, qty) {
  let items = loadCart();
  if (qty <= 0) {
    items = items.filter((i) => !(i.product_id === productId && i.volume_ml === volumeMl));
  } else {
    const item = items.find((i) => i.product_id === productId && i.volume_ml === volumeMl);
    if (item) item.qty = qty;
  }
  saveCart(items);
}

export function removeFromCart(productId, volumeMl) {
  updateQty(productId, volumeMl, 0);
}

export function clearCart() {
  saveCart([]);
}

export function cartItemsForOrder() {
  return loadCart().map(({ product_id, volume_ml, qty }) => ({
    product_id,
    volume_ml,
    qty,
  }));
}
