/**
 * Theme system — Light / Dark / System
 * Persisted in localStorage. Applied as data-theme on <html>.
 */

export const THEMES = ["light", "dark", "system"];

export function getStoredTheme() {
  try { return localStorage.getItem("vtrader-theme") || "dark"; } catch { return "dark"; }
}

export function setStoredTheme(theme) {
  try { localStorage.setItem("vtrader-theme", theme); } catch {}
}

export function applyTheme(theme) {
  const root = document.documentElement;
  const dark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  root.setAttribute("data-theme", dark ? "dark" : "light");
}

export function initTheme() {
  const t = getStoredTheme();
  applyTheme(t);
  if (t === "system") {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => applyTheme("system"));
  }
  return t;
}