import { api } from "../api.js";
import { el, fmt, toast, errorMessage, startOfWeek, addDays, isoDate, sameDay, shortDayName, niceDate } from "../util.js";

let weekStart = startOfWeek(new Date());

function activityChip(a) {
  return el("div", { class: "activity-chip" }, [
    el("div", { class: "type" }, a.activity_type || "activity"),
    el("div", {}, [
      a.duration_minutes ? `${fmt(a.duration_minutes)} min` : null,
      a.distance ? ` · ${fmt(a.distance / 1000, 1)} km` : null,
    ].filter(Boolean).join("")),
    a.calories_burned ? el("div", {}, `${fmt(a.calories_burned)} kcal`) : null,
  ]);
}

export async function renderCalendar(container) {
  container.innerHTML = "";

  const header = el("div", { class: "week-header" }, [
    el("button", { class: "btn secondary", onclick: () => shift(-1) }, "← Prev"),
    el("div", { class: "label", id: "week-label" }, ""),
    el("div", { class: "row" }, [
      el("button", { class: "btn secondary small", onclick: () => { weekStart = startOfWeek(new Date()); load(); } }, "This week"),
      el("button", { class: "btn small", id: "sync-btn" }, "Sync Garmin"),
      el("button", { class: "btn secondary", onclick: () => shift(1) }, "Next →"),
    ]),
  ]);
  container.appendChild(header);

  const summary = el("div", { class: "week-summary" });
  container.appendChild(summary);

  const grid = el("div", { class: "week-grid" });
  container.appendChild(grid);

  header.querySelector("#sync-btn").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = "Syncing…";
    try {
      const result = await api.syncGarmin(30);
      toast(`Synced: ${result.added} new, ${result.skipped_duplicates} already had.`);
      await load();
    } catch (err) {
      toast(errorMessage(err), { error: true });
    } finally {
      btn.disabled = false;
      btn.textContent = "Sync Garmin";
    }
  });

  function shift(n) {
    weekStart = addDays(weekStart, n * 7);
    load();
  }

  async function load() {
    const label = container.querySelector("#week-label");
    const weekEnd = addDays(weekStart, 6);
    label.textContent = `${niceDate(weekStart)} – ${niceDate(weekEnd)}`;

    grid.innerHTML = "";
    summary.innerHTML = "";
    grid.appendChild(el("div", { class: "loading" }, "Loading activity…"));

    let activities = [];
    try {
      activities = await api.listActivityLog();
    } catch (err) {
      grid.innerHTML = "";
      grid.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
      return;
    }

    grid.innerHTML = "";
    const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
    const byDay = days.map((d) => activities.filter((a) => sameDay(a.date, d)));

    let totalCal = 0;
    let totalMin = 0;
    let count = 0;
    byDay.flat().forEach((a) => {
      totalCal += Number(a.calories_burned || 0);
      totalMin += Number(a.duration_minutes || 0);
      count += 1;
    });

    summary.appendChild(statBox(count, "Activities"));
    summary.appendChild(statBox(fmt(totalMin), "Minutes"));
    summary.appendChild(statBox(fmt(totalCal), "Calories burned"));

    days.forEach((d, i) => {
      const isToday = sameDay(d, new Date());
      const col = el("div", { class: "day-col" + (isToday ? " today" : "") }, [
        el("div", { class: "day-name" }, shortDayName(d)),
        el("div", { class: "day-date" }, String(d.getDate())),
      ]);
      if (byDay[i].length) {
        byDay[i].forEach((a) => col.appendChild(activityChip(a)));
      } else {
        col.appendChild(el("div", { class: "muted", style: "font-size:0.8rem;" }, "No activity"));
      }
      grid.appendChild(col);
    });
  }

  function statBox(value, label) {
    return el("div", { class: "stat-box" }, [
      el("div", { class: "value" }, String(value)),
      el("div", { class: "label" }, label),
    ]);
  }

  await load();
}
