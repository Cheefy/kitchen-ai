import { api } from "../api.js";
import { el, fmt, toast, errorMessage, startOfWeek, addDays, isoDate, sameDay, shortDayName, niceDate } from "../util.js";

let weekStart = startOfWeek(new Date());

function timeOf(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function entryRow(entry) {
  if (entry.kind === "meal") {
    return el("div", { class: "cal-entry meal" }, [
      el("span", { class: "cal-time" }, timeOf(entry.timestamp)),
      el("span", { class: "cal-icon" }, "🍽"),
      el("span", { class: "cal-label" }, entry.label + (entry.is_estimate ? " (est.)" : "")),
      el("span", { class: "cal-cal" }, `${fmt(entry.calories)} kcal`),
    ]);
  }
  return el("div", { class: "cal-entry exercise" }, [
    el("span", { class: "cal-time" }, timeOf(entry.timestamp)),
    el("span", { class: "cal-icon" }, "🏃"),
    el("span", { class: "cal-label" }, entry.activity_type || "activity"),
    el("span", { class: "cal-cal" }, entry.calories_burned ? `−${fmt(entry.calories_burned)} kcal` : ""),
  ]);
}

function dayCard(day, isToday) {
  const entries = [
    ...day.meals.map((m) => ({ ...m, kind: "meal" })),
    ...day.exercises.map((a) => ({ ...a, kind: "exercise" })),
  ].sort((a, b) => new Date(a.timestamp || 0) - new Date(b.timestamp || 0));

  const card = el("div", { class: "day-card" + (isToday ? " today" : "") });

  card.appendChild(
    el("div", { class: "day-card-header" }, [
      el("div", { class: "day-card-date" }, [
        el("span", { class: "dow" }, shortDayName(day.date).toUpperCase()),
        el("span", { class: "dnum" }, String(new Date(day.date).getDate())),
      ]),
      el("div", { class: "day-card-totals" }, [
        el("span", {}, `${fmt(day.calories_eaten)} kcal in`),
        el("span", {}, `${fmt(day.calories_burned_exercise)} kcal exercise`),
      ]),
    ])
  );

  const list = el("div", { class: "day-card-entries" });
  if (entries.length) {
    entries.forEach((e) => list.appendChild(entryRow(e)));
  } else {
    list.appendChild(el("div", { class: "muted", style: "padding: 8px 0;" }, "Nothing logged."));
  }
  card.appendChild(list);

  const footer = el("div", { class: "day-card-footer" });
  if (day.deficit !== null && day.deficit !== undefined) {
    const isDeficit = Number(day.deficit) >= 0;
    const change = Number(day.expected_weight_change_lb);
    footer.appendChild(
      el(
        "span",
        { class: "deficit-badge" + (isDeficit ? " good" : " over") },
        `${isDeficit ? "Deficit" : "Surplus"}: ${fmt(Math.abs(day.deficit))} kcal`
      )
    );
    footer.appendChild(
      el(
        "span",
        { class: "muted" },
        `Expected: ${change > 0 ? "+" : ""}${fmt(change, 2)} lb${day.calibrating ? " (still calibrating)" : ""}`
      )
    );
  } else {
    footer.appendChild(
      el("div", { class: "muted", style: "font-size:0.8rem;" }, day.note || "Set a profile to see deficit.")
    );
  }
  card.appendChild(footer);

  return card;
}

export async function renderCalendar(container) {
  container.innerHTML = "";

  const header = el("div", { class: "week-header" }, [
    el("button", { class: "btn secondary", onclick: () => shift(-1) }, "← Prev"),
    el("div", { class: "label", id: "week-label" }, ""),
    el("div", { class: "row" }, [
      el(
        "button",
        {
          class: "btn secondary small",
          onclick: () => {
            weekStart = startOfWeek(new Date());
            load();
          },
        },
        "This week"
      ),
      el("button", { class: "btn small", id: "sync-btn" }, "Sync Garmin"),
      el("button", { class: "btn secondary", onclick: () => shift(1) }, "Next →"),
    ]),
  ]);
  container.appendChild(header);

  const summary = el("div", { class: "week-summary" });
  container.appendChild(summary);

  const daysWrap = el("div", { class: "week-days" });
  container.appendChild(daysWrap);

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

    daysWrap.innerHTML = "";
    summary.innerHTML = "";
    daysWrap.appendChild(el("div", { class: "loading" }, "Loading calendar…"));

    let data;
    try {
      data = await api.getCalendar(isoDate(weekStart), isoDate(weekEnd));
    } catch (err) {
      daysWrap.innerHTML = "";
      daysWrap.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
      return;
    }

    daysWrap.innerHTML = "";
    const days = data.days;

    let totalCal = 0;
    let totalBurned = 0;
    let totalDeficit = 0;
    let exerciseCount = 0;
    let hasDeficit = false;

    days.forEach((d) => {
      totalCal += Number(d.calories_eaten || 0);
      totalBurned += Number(d.calories_burned_exercise || 0);
      exerciseCount += d.exercises.length;
      if (d.deficit !== null && d.deficit !== undefined) {
        totalDeficit += Number(d.deficit);
        hasDeficit = true;
      }
    });

    summary.appendChild(statBox(exerciseCount, "Activities"));
    summary.appendChild(statBox(fmt(totalCal), "Calories eaten"));
    summary.appendChild(statBox(fmt(totalBurned), "Exercise burned"));
    if (hasDeficit) {
      const weekChange = -totalDeficit / 3500;
      summary.appendChild(
        statBox(`${weekChange > 0 ? "+" : ""}${fmt(weekChange, 2)} lb`, "Week's expected change")
      );
    }

    const today = new Date();
    days.forEach((d) => daysWrap.appendChild(dayCard(d, sameDay(d.date, today))));
  }

  function statBox(value, label) {
    return el("div", { class: "stat-box" }, [
      el("div", { class: "value" }, String(value)),
      el("div", { class: "label" }, label),
    ]);
  }

  await load();
}
