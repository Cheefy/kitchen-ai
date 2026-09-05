// Reusable SVG progress ring, per kitchen_ai_spec.md §11: a large ring for
// calories, smaller ones underneath for protein/carbs/fat, consistent
// color-coding reused everywhere macros are shown.

import { el, fmt } from "./util.js";

export function ring({ size = 120, stroke = 12, pct, color, label, caption, overCaption }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = pct === null || pct === undefined ? 0 : Math.max(0, Math.min(1, pct));
  const dash = clamped * c;
  const isOver = pct !== null && pct !== undefined && pct > 1;

  const svgNs = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNs, "svg");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);

  const bg = document.createElementNS(svgNs, "circle");
  bg.setAttribute("cx", size / 2);
  bg.setAttribute("cy", size / 2);
  bg.setAttribute("r", r);
  bg.setAttribute("fill", "none");
  bg.setAttribute("stroke", "#e9e7dd");
  bg.setAttribute("stroke-width", stroke);
  svg.appendChild(bg);

  if (pct !== null && pct !== undefined) {
    const fg = document.createElementNS(svgNs, "circle");
    fg.setAttribute("cx", size / 2);
    fg.setAttribute("cy", size / 2);
    fg.setAttribute("r", r);
    fg.setAttribute("fill", "none");
    fg.setAttribute("stroke", isOver ? "#c94f6d" : color);
    fg.setAttribute("stroke-width", stroke);
    fg.setAttribute("stroke-linecap", "round");
    fg.setAttribute("stroke-dasharray", `${dash} ${c}`);
    fg.setAttribute("transform", `rotate(-90 ${size / 2} ${size / 2})`);
    svg.appendChild(fg);
  }

  const wrap = el("div", { class: "ring-wrap" });
  const box = el("div", { style: "position:relative; width:" + size + "px; height:" + size + "px;" });
  box.appendChild(svg);
  const valueEl = el("div", {
    class: "ring-value",
    style: `position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:${size / 5.2}px;`,
  }, label);
  box.appendChild(valueEl);
  wrap.appendChild(box);
  wrap.appendChild(el("div", { class: "ring-caption" }, isOver && overCaption ? overCaption : caption));
  return wrap;
}

// Builds the full calorie + protein/carb/fat ring cluster from a macro
// totals object and an optional target object (same shape). Falls back to
// value-only rendering (no percentage) when no target is available.
export function macroRingCluster(totals, target) {
  const wrap = el("div", { class: "macro-panel" });

  const cal = Number(totals.calories || 0);
  const calTarget = target ? Number(target.calories || 0) : null;
  const calPct = calTarget ? cal / calTarget : null;

  wrap.appendChild(
    ring({
      size: 148,
      stroke: 14,
      pct: calPct,
      color: "#1f6f4f",
      label: fmt(cal),
      caption: calTarget ? `of ${fmt(calTarget)} kcal` : "calories",
      overCaption: `${fmt(cal - (calTarget || 0))} over`,
    })
  );

  const small = el("div", { class: "small-rings" });
  const macroDefs = [
    { key: "protein_g", color: "#3d6fd9", label: "Protein" },
    { key: "carbs_g", color: "#d98a3d", label: "Carbs" },
    { key: "fat_g", color: "#c94f6d", label: "Fat" },
  ];
  for (const m of macroDefs) {
    const v = Number(totals[m.key] || 0);
    const t = target ? Number(target[m.key] || 0) : null;
    const pct = t ? v / t : null;
    small.appendChild(
      ring({
        size: 84,
        stroke: 9,
        pct,
        color: m.color,
        label: `${fmt(v)}g`,
        caption: t ? `/${fmt(t)}g` : m.label,
      })
    );
  }
  wrap.appendChild(small);
  return wrap;
}
