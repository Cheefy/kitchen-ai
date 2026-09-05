import { api } from "../api.js";
import { el, fmt, toast, errorMessage } from "../util.js";

const SLIDER_DEFS = [
  { key: "calorie_deficit_adherence", label: "Calorie/deficit adherence", hint: "How strictly to chase your calorie target vs. other factors." },
  { key: "protein_adherence", label: "Protein adherence", hint: "How strictly to hit your protein target." },
  { key: "carb_adherence", label: "Carb adherence", hint: "How strictly to hit your carb target." },
  { key: "fat_adherence", label: "Fat adherence", hint: "How strictly to hit your fat target." },
  { key: "diversity", label: "Diversity", hint: "How much to favor variety over repeating recent meals." },
  { key: "expiration_urgency", label: "Expiration urgency", hint: "How much to prioritize using up soon-to-expire ingredients." },
];

function section(title, ...children) {
  return el("div", { class: "card settings-section" }, [
    el("h2", {}, title),
    ...children,
  ]);
}

function labeled(label, node) {
  return el("div", { class: "setting-row" }, [el("div", { class: "label" }, label), node]);
}

export async function renderSettings(container) {
  container.innerHTML = "";
  const grid = el("div", { class: "settings-grid" });
  container.appendChild(grid);
  grid.appendChild(el("div", { class: "loading" }, "Loading settings…"));

  let behaviorSettings, recSettings, allergens, goal, weighIns;
  try {
    [behaviorSettings, recSettings, allergens, goal, weighIns] = await Promise.all([
      api.listBehaviorSettings(),
      api.getRecommendationSettings(),
      api.listAllergenRestrictions(),
      api.getCurrentGoal(),
      api.listWeighIns(),
    ]);
  } catch (err) {
    grid.innerHTML = "";
    grid.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
    return;
  }

  grid.innerHTML = "";

  // --- Goals & weigh-ins -----------------------------------------------
  const goalSection = section("Goals & weigh-ins");
  if (goal) {
    const impliedCal =
      goal.protein_g != null && goal.carbs_g != null && goal.fat_g != null
        ? Number(goal.protein_g) * 4 + Number(goal.carbs_g) * 4 + Number(goal.fat_g) * 9
        : null;
    goalSection.appendChild(
      el("div", { class: "goal-summary" }, [
        el("div", {}, [el("b", {}, "Current goal"), ` — set ${goal.effective_date}${goal.goal_type ? ` (${goal.goal_type})` : ""}`]),
        el("div", { class: "macro-line" }, [
          goal.goal_weight != null ? el("span", {}, `Target weight: ${fmt(goal.goal_weight, 1)}`) : null,
          goal.target_date ? el("span", {}, `by ${goal.target_date}`) : null,
        ].filter(Boolean)),
        el("div", { class: "macro-line" }, [
          goal.protein_g != null ? el("span", {}, [el("b", {}, fmt(goal.protein_g)), "g protein"]) : null,
          goal.carbs_g != null ? el("span", {}, [el("b", {}, fmt(goal.carbs_g)), "g carbs"]) : null,
          goal.fat_g != null ? el("span", {}, [el("b", {}, fmt(goal.fat_g)), "g fat"]) : null,
          impliedCal != null ? el("span", {}, [el("b", {}, fmt(impliedCal)), " kcal (implied)"]) : null,
        ].filter(Boolean)),
      ])
    );
  } else {
    goalSection.appendChild(el("div", { class: "empty-state" }, "No goal set yet — add one below."));
  }

  if (weighIns.length) {
    goalSection.appendChild(
      el("div", { class: "muted", style: "font-size:0.85rem; margin-top:0.5rem;" }, `Latest weigh-in: ${fmt(weighIns[0].weight, 1)} on ${weighIns[0].date}`)
    );
  }

  const weighForm = el("div", { class: "inline-form" }, [
    el("input", { type: "number", step: "0.1", placeholder: "Weight", id: "weighin-weight" }),
    el("button", { class: "btn secondary small", id: "weighin-btn" }, "Log weigh-in"),
  ]);
  goalSection.appendChild(weighForm);

  const goalForm = el("div", { class: "goal-form" }, [
    el("div", { class: "field-row" }, [
      el("label", {}, "Goal weight"),
      el("input", { type: "number", step: "0.1", id: "goal-weight" }),
    ]),
    el("div", { class: "field-row" }, [
      el("label", {}, "Goal type (optional)"),
      el("input", { type: "text", placeholder: "e.g. cut, bulk, maintain", id: "goal-type" }),
    ]),
    el("div", { class: "field-row" }, [
      el("label", {}, "Protein (g/day)"),
      el("input", { type: "number", step: "1", id: "goal-protein" }),
    ]),
    el("div", { class: "field-row" }, [
      el("label", {}, "Carbs (g/day)"),
      el("input", { type: "number", step: "1", id: "goal-carbs" }),
    ]),
    el("div", { class: "field-row" }, [
      el("label", {}, "Fat (g/day)"),
      el("input", { type: "number", step: "1", id: "goal-fat" }),
    ]),
    el("div", { class: "field-row" }, [
      el("label", {}, "Target date (optional)"),
      el("input", { type: "date", id: "goal-target-date" }),
    ]),
    el("button", { class: "btn small", id: "goal-btn" }, "Save new goal"),
  ]);
  goalSection.appendChild(el("div", { class: "section-title" }, "Set a new goal"));
  goalSection.appendChild(goalForm);
  grid.appendChild(goalSection);

  weighForm.querySelector("#weighin-btn").addEventListener("click", async () => {
    const weight = Number(weighForm.querySelector("#weighin-weight").value);
    if (!weight) return toast("Enter a weight first", { error: true });
    try {
      await api.createWeighIn({ date: new Date().toISOString().slice(0, 10), weight });
      toast("Weigh-in logged");
      renderSettings(container);
    } catch (err) {
      toast(errorMessage(err), { error: true });
    }
  });

  goalForm.querySelector("#goal-btn").addEventListener("click", async () => {
    const weight = Number(goalForm.querySelector("#goal-weight").value);
    if (!weight) return toast("Enter a goal weight first", { error: true });
    const body = {
      effective_date: new Date().toISOString().slice(0, 10),
      goal_weight: weight,
      goal_type: goalForm.querySelector("#goal-type").value || null,
      protein_g: goalForm.querySelector("#goal-protein").value || null,
      carbs_g: goalForm.querySelector("#goal-carbs").value || null,
      fat_g: goalForm.querySelector("#goal-fat").value || null,
      target_date: goalForm.querySelector("#goal-target-date").value || null,
    };
    try {
      await api.createGoal(body);
      toast("Goal saved");
      renderSettings(container);
    } catch (err) {
      toast(errorMessage(err), { error: true });
    }
  });

  // --- Recommendation sliders --------------------------------------------
  const recSection = section(
    "Recommendation tuning",
    el("div", { class: "muted", style: "font-size:0.85rem; margin-bottom:0.5rem;" }, "0–100 — how much weight each factor gets when ranking recipe suggestions.")
  );
  SLIDER_DEFS.forEach((def) => {
    const value = Number(recSettings[def.key]);
    const valueLabel = el("span", { class: "slider-value" }, String(Math.round(value)));
    const input = el("input", {
      type: "range",
      min: "0",
      max: "100",
      step: "1",
      value: String(value),
    });
    input.addEventListener("input", () => {
      valueLabel.textContent = input.value;
    });
    input.addEventListener("change", async () => {
      try {
        await api.updateRecommendationSettings({ [def.key]: Number(input.value) });
        toast(`${def.label} updated`);
      } catch (err) {
        toast(errorMessage(err), { error: true });
      }
    });
    recSection.appendChild(
      el("div", { class: "slider-row" }, [
        el("div", { class: "sl-label" }, [el("span", {}, def.label), valueLabel]),
        input,
        el("div", { class: "muted", style: "font-size:0.78rem;" }, def.hint),
      ])
    );
  });
  grid.appendChild(recSection);

  // --- Allergen restrictions ---------------------------------------------
  const allergenSection = section("Allergen restrictions");
  const allergenList = el("div", { class: "allergen-list" });
  if (allergens.length) {
    allergens.forEach((a) => {
      const chip = el("div", { class: "allergen-chip" }, [
        el("span", {}, a.name),
        el("button", { class: "chip-remove", title: "Remove" }, "×"),
      ]);
      chip.querySelector(".chip-remove").addEventListener("click", async () => {
        try {
          await api.removeAllergenRestriction(a.id);
          toast(`Removed ${a.name}`);
          renderSettings(container);
        } catch (err) {
          toast(errorMessage(err), { error: true });
        }
      });
      allergenList.appendChild(chip);
    });
  } else {
    allergenList.appendChild(el("div", { class: "empty-state" }, "No allergen restrictions set."));
  }
  allergenSection.appendChild(allergenList);

  const addAllergenRow = el("div", { class: "inline-form" }, [
    el("input", { type: "number", placeholder: "Allergen ID", id: "allergen-id-input" }),
    el("button", { class: "btn secondary small", id: "allergen-add-btn" }, "Add restriction"),
  ]);
  allergenSection.appendChild(addAllergenRow);
  allergenSection.appendChild(
    el(
      "div",
      { class: "muted", style: "font-size:0.78rem; margin-top:0.35rem;" },
      "The backend doesn't have a full allergen catalog endpoint yet, so new restrictions need the allergen's numeric ID for now — ask to look one up in the database if you don't know it."
    )
  );
  addAllergenRow.querySelector("#allergen-add-btn").addEventListener("click", async () => {
    const id = Number(addAllergenRow.querySelector("#allergen-id-input").value);
    if (!id) return toast("Enter an allergen ID", { error: true });
    try {
      await api.addAllergenRestriction(id);
      toast("Restriction added");
      renderSettings(container);
    } catch (err) {
      toast(errorMessage(err), { error: true });
    }
  });
  grid.appendChild(allergenSection);

  // --- Behavior settings ---------------------------------------------------
  const behaviorSection = section(
    "Assumption behavior",
    el("div", { class: "muted", style: "font-size:0.85rem; margin-bottom:0.5rem;" }, "Per-decision: let the kitchen AI assume and tell you, or always ask first.")
  );
  if (behaviorSettings.length) {
    behaviorSettings.forEach((s) => {
      const seg = el("div", { class: "segmented" }, [
        el("button", { class: "seg-btn" + (s.mode === "assume_and_announce" ? " active" : "") }, "Assume & announce"),
        el("button", { class: "seg-btn" + (s.mode === "always_ask" ? " active" : "") }, "Always ask"),
      ]);
      const [assumeBtn, askBtn] = seg.querySelectorAll(".seg-btn");
      const setMode = async (mode) => {
        try {
          await api.setBehaviorSetting(s.key, mode);
          assumeBtn.classList.toggle("active", mode === "assume_and_announce");
          askBtn.classList.toggle("active", mode === "always_ask");
          toast(`${s.key} → ${mode === "assume_and_announce" ? "assume & announce" : "always ask"}`);
        } catch (err) {
          toast(errorMessage(err), { error: true });
        }
      };
      assumeBtn.addEventListener("click", () => setMode("assume_and_announce"));
      askBtn.addEventListener("click", () => setMode("always_ask"));
      behaviorSection.appendChild(labeled(s.key, seg));
    });
  } else {
    behaviorSection.appendChild(
      el("div", { class: "empty-state" }, "No behavior settings recorded yet — they appear here the first time the kitchen AI has to make one of these calls.")
    );
  }
  grid.appendChild(behaviorSection);

  // --- Garmin sync ----------------------------------------------------------
  const garminSection = section("Garmin sync");
  const garminRow = el("div", { class: "inline-form" }, [
    el("input", { type: "number", value: "7", min: "1", style: "width:5rem;", id: "garmin-days" }),
    el("span", { class: "muted", style: "align-self:center;" }, "days back"),
    el("button", { class: "btn secondary small", id: "garmin-sync-btn" }, "Sync now"),
  ]);
  garminSection.appendChild(garminRow);
  garminRow.querySelector("#garmin-sync-btn").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const days = Number(garminRow.querySelector("#garmin-days").value) || 7;
    btn.disabled = true;
    btn.textContent = "Syncing…";
    try {
      const result = await api.syncGarmin(days);
      toast(`Fetched ${result.fetched}, added ${result.added}, skipped ${result.skipped_duplicates} duplicates.`);
    } catch (err) {
      toast(errorMessage(err), { error: true });
    } finally {
      btn.disabled = false;
      btn.textContent = "Sync now";
    }
  });
  grid.appendChild(garminSection);

  // --- Notifications ----------------------------------------------------
  const notifSection = section("Notifications");
  const notifBtn = el("button", { class: "btn secondary small" }, "Send test notification");
  notifSection.appendChild(notifBtn);
  notifBtn.addEventListener("click", async () => {
    notifBtn.disabled = true;
    try {
      const result = await api.testNotification("Kitchen AI test notification");
      toast(result.sent ? "Test notification sent" : "Notifications aren't configured on the backend");
    } catch (err) {
      toast(errorMessage(err), { error: true });
    } finally {
      notifBtn.disabled = false;
    }
  });
  grid.appendChild(notifSection);

  // --- Assumption log -----------------------------------------------------
  const logSection = section("Assumption log");
  const logList = el("div", { class: "log-list" });
  logSection.appendChild(logList);
  grid.appendChild(logSection);

  try {
    const entries = await api.listSystemLog({ limit: 25 });
    logList.innerHTML = "";
    if (!entries.length) {
      logList.appendChild(el("div", { class: "empty-state" }, "No logged assumptions yet."));
    } else {
      entries.forEach((entry) => {
        const row = el("div", { class: "log-entry" + (entry.corrected ? " corrected" : "") }, [
          el("div", {}, entry.description),
          el("div", { class: "muted", style: "font-size:0.78rem;" }, [
            new Date(entry.timestamp).toLocaleString(),
            entry.behavior_key ? ` · ${entry.behavior_key}` : "",
          ].join("")),
        ]);
        if (!entry.corrected) {
          const btn = el("button", { class: "btn secondary small" }, "Mark corrected");
          btn.addEventListener("click", async () => {
            try {
              await api.markCorrected(entry.id);
              row.classList.add("corrected");
              btn.remove();
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          });
          row.appendChild(btn);
        }
        logList.appendChild(row);
      });
    }
  } catch (err) {
    logList.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
  }
}
