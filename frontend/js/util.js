// Small shared helpers used across pages.

export function toast(message, { error = false } = {}) {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = "toast" + (error ? " error" : "");
  el.textContent = message;
  root.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 250);
  }, 3200);
}

export function errorMessage(err) {
  if (err && err.detail) {
    if (typeof err.detail === "string") return err.detail;
    if (err.detail.message) return err.detail.message;
    try { return JSON.stringify(err.detail); } catch { /* fallthrough */ }
  }
  return err && err.message ? err.message : "Something went wrong";
}

export function round(n, places = 0) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return null;
  const f = Math.pow(10, places);
  return Math.round(Number(n) * f) / f;
}

export function fmt(n, places = 0) {
  const r = round(n, places);
  return r === null ? "–" : r.toLocaleString();
}

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}

// Monday-start week containing `d`.
export function startOfWeek(d) {
  const date = new Date(d);
  const day = date.getDay(); // 0 = Sunday
  const diff = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

export function addDays(d, n) {
  const date = new Date(d);
  date.setDate(date.getDate() + n);
  return date;
}

export function isoDate(d) {
  const date = new Date(d);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function sameDay(a, b) {
  return isoDate(a) === isoDate(b);
}

export function shortDayName(d) {
  return new Date(d).toLocaleDateString(undefined, { weekday: "short" });
}

export function niceDate(d) {
  return new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Very small parser for a recipe's free-text `instructions` field: splits
// on explicit numbering ("1.", "2)") when present, otherwise on blank
// lines, otherwise on single newlines. Good enough for cook-mode step
// cards without requiring a structured-steps schema change.
export function parseSteps(instructions) {
  if (!instructions) return [];
  const text = instructions.trim();
  if (!text) return [];

  const numbered = text.split(/\n(?=\s*\d+[.)]\s)/g).map((s) => s.trim()).filter(Boolean);
  if (numbered.length > 1) {
    return numbered.map((s) => s.replace(/^\s*\d+[.)]\s*/, ""));
  }

  const blankSep = text.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
  if (blankSep.length > 1) return blankSep;

  const lines = text.split(/\n/).map((s) => s.trim()).filter(Boolean);
  return lines.length ? lines : [text];
}

// Pulls the first "N minute(s)"/"N min" mention out of step text, to
// prefill a suggested timer duration.
export function guessMinutes(stepText) {
  const m = stepText.match(/(\d+)\s*(?:-|to)?\s*(\d+)?\s*min/i);
  if (!m) return null;
  return Number(m[2] || m[1]);
}
