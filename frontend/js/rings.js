// Reusable SVG progress ring, per kitchen_ai_spec.md §11: a large ring for
// calories, smaller ones underneath for protein/carbs/fat, consistent
// color-coding reused everywhere macros are shown.
//
// Each ring can show two stacked segments: a solid-color "base" arc (what's
// already logged today) and a lighter-tinted "add" arc layered right after
// it (what the recipe being viewed would contribute). If the two combined
// would exceed the target, the whole ring turns solid red instead -- going
// over is going over, regardless of which part pushed it there.

import { el, fmt } from "./util.js";

const OVER_COLOR = "#c94f6d";

function lighten(hex, amount) {
  const clean = hex.replace("#", "");
  const num = parseInt(clean, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  const mix = (channel) => Math.round(channel + (255 - channel) * amount);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

// pct-based (single-segment, no target) or basePct/addPct (two-segment,
// against a target) -- pass one pair or the other. label/caption are the
// text shown when there's no target to compute a percentage against;
// once a target exists the ring always shows a percentage instead.
export function ring({ size = 120, stroke = 12, basePct, addPct, color, label, caption, overCaption }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const hasPct = basePct !== null && basePct !== undefined;
  const base = hasPct ? Math.max(0, basePct) : 0;
  const add = hasPct ? Math.max(0, addPct || 0) : 0;
  const combined = base + add;
  const isOver = hasPct && combined > 1;

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

  const arc = (dasharray, stroke_) => {
    const circle = document.createElementNS(svgNs, "circle");
    circle.setAttribute("cx", size / 2);
    circle.setAttribute("cy", size / 2);
    circle.setAttribute("r", r);
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", stroke_);
    circle.setAttribute("stroke-width", stroke);
    circle.setAttribute("stroke-dasharray", dasharray);
    circle.setAttribute("transform", `rotate(-90 ${size / 2} ${size / 2})`);
    svg.appendChild(circle);
  };

  if (hasPct) {
    if (isOver) {
      arc(`${c} 0`, OVER_COLOR);
    } else {
      const baseLen = base * c;
      const addLen = add * c;
      if (baseLen > 0) arc(`${baseLen} ${c - baseLen}`, color);
      if (addLen > 0) arc(`0 ${baseLen} ${addLen} ${c - baseLen - addLen}`, lighten(color, 0.55));
    }
  }

  const wrap = el("div", { class: "ring-wrap" });
  const box = el("div", { style: "position:relative; width:" + size + "px; height:" + size + "px;" });
  box.appendChild(svg);
  const displayLabel = hasPct ? `${Math.round(combined * 100)}%` : label;
  const valueEl = el("div", {
    class: "ring-value",
    style: `position:absolute; inset:0; display:flex; align-items:center; justify-content:center; font-size:${size / 5.2}px;`,
  }, displayLabel);
  box.appendChild(valueEl);
  wrap.appendChild(box);
  wrap.appendChild(el("div", { class: "ring-caption" }, isOver && overCaption ? overCaption : caption));
  return wrap;
}

// Builds the full calorie + protein/carb/fat ring cluster.
// `base` = macros already accounted for today (logged meals + planned-not-
// logged), `add` = the recipe currently being viewed, `target` = daily
// targets from /profile/targets. Without a target, falls back to showing
// base+add's raw value with an unfilled ring (nothing to measure progress
// against yet).
export function macroRingCluster({ base, add, target }) {
  const wrap = el("div", { class: "macro-panel" });

  const calBase = Number(base.calories || 0);
  const calAdd = Number(add.calories || 0);
  const calTarget = target ? Number(target.calories || 0) : null;
  const calCombined = calBase + calAdd;

  wrap.appendChild(
    ring({
      size: 148,
      stroke: 14,
      basePct: calTarget ? calBase / calTarget : null,
      addPct: calTarget ? calAdd / calTarget : null,
      color: "#1f6f4f",
      label: fmt(calCombined),
      caption: calTarget ? `${fmt(calCombined)} of ${fmt(calTarget)} kcal` : "calories",
      overCaption: calTarget ? `${fmt(calCombined - calTarget)} kcal over` : null,
    })
  );

  const small = el("div", { class: "small-rings" });
  const macroDefs = [
    { key: "protein_g", color: "#3d6fd9", label: "Protein" },
    { key: "carbs_g", color: "#d98a3d", label: "Carbs" },
    { key: "fat_g", color: "#c94f6d", label: "Fat" },
  ];
  for (const m of macroDefs) {
    const vBase = Number(base[m.key] || 0);
    const vAdd = Number(add[m.key] || 0);
    const t = target ? Number(target[m.key] || 0) : null;
    const vCombined = vBase + vAdd;
    small.appendChild(
      ring({
        size: 84,
        stroke: 9,
        basePct: t ? vBase / t : null,
        addPct: t ? vAdd / t : null,
        color: m.color,
        label: `${fmt(vCombined)}g`,
        caption: t ? `${fmt(vCombined)}/${fmt(t)}g` : m.label,
        overCaption: t ? `${fmt(vCombined - t)}g over` : null,
      })
    );
  }
  wrap.appendChild(small);
  return wrap;
}
