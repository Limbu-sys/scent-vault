const STORAGE_KEY = "sv_favorites";

export function loadFavorites() {
  try {
    return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function saveFavorites(set) {
  const arr = [...set];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
  document.dispatchEvent(new CustomEvent("favoriteschange", { detail: arr }));
}

export function isFavorite(productId) {
  return loadFavorites().has(productId);
}

export function toggleFavorite(productId) {
  const set = loadFavorites();
  if (set.has(productId)) set.delete(productId);
  else set.add(productId);
  saveFavorites(set);
  return set.has(productId);
}
