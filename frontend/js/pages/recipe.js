import { api } from "../api.js";
import { el, fmt, toast, errorMessage, parseSteps, guessMinutes } from "../util.js";
import { macroRingCluster } from "../rings.js";

// Timers live outside the render cycle so they survive re-renders while a
// session's ingredients/macros are edited. One shared ticking interval
// drives every timer's countdown and re-renders just the tray.
const timers = [];
let timerTick = null;
let trayEl = null;

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
    osc.onended = () => ctx.close();
  } catch {
    /* audio not available -- visual pulse on the chip is the fallback */
  }
}

function startTimer(label, minutes) {
  const id = Math.random().toString(36).slice(2);
  timers.push({
    id,
    label,
    totalSeconds: Math.round(minutes * 60),
    remaining: Math.round(minutes * 60),
    done: false,
  });
  renderTray();
  ensureTicking();
}

function dismissTimer(id) {
  const idx = timers.findIndex((t) => t.id === id);
  if (idx >= 0) timers.splice(idx, 1);
  renderTray();
}

function ensureTicking() {
  if (timerTick) return;
  timerTick = setInterval(() => {
    let anyDone = false;
    for (const t of timers) {
      if (t.done) continue;
      t.remaining -= 1;
      if (t.remaining <= 0) {
        t.remaining = 0;
        t.done = true;
        anyDone = true;
      }
    }
    if (anyDone) beep();
    renderTray();
    if (!timers.length) {
      clearInterval(timerTick);
      timerTick = null;
    }
  }, 1000);
}

function formatClock(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function renderTray() {
  if (!trayEl) return;
  trayEl.innerHTML = "";
  for (const t of timers) {
    trayEl.appendChild(
      el("div", { class: "timer-chip" + (t.done ? " done" : "") }, [
        el("span", { class: "t-label" }, t.label),
        el("span", { class: "t-time" }, t.done ? "Done!" : formatClock(t.remaining)),
        el("button", { onclick: () => dismissTimer(t.id) }, "✕"),
      ])
    );
  }
}

function modal(contentBuilder) {
  const backdrop = el("div", { class: "modal-backdrop" });
  const box = el("div", { class: "modal" });
  backdrop.appendChild(box);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.remove();
  });
  document.body.appendChild(backdrop);
  contentBuilder(box, () => backdrop.remove());
  return () => backdrop.remove();
}

async function computeDailyContext(recipeMacros) {
  // kitchen_ai_spec.md §8: remaining = daily_target - meal_log so far
  // today - planned_meals not yet logged. Target (calories + protein/fat/
  // carbs) comes from /profile/targets: TDEE minus the goal's deficit,
  // with macros auto-split for muscle preservation -- not manually
  // entered (app/services/tdee.py).
  const [mealLog, planned, targets] = await Promise.all([
    api.listMealLog().catch(() => []),
    api.listPlannedMeals().catch(() => []),
    api.getDailyTargets().catch(() => null),
  ]);

  const today = new Date().toDateString();
  const loggedToday = mealLog.filter((m) => new Date(m.timestamp).toDateString() === today);

  const sumField = (rows, field) => rows.reduce((acc, r) => acc + Number((r.macros && r.macros[field]) || r[field] || 0), 0);

  const loggedSoFar = {
    calories: sumField(loggedToday, "calories"),
    protein_g: sumField(loggedToday, "protein_g"),
    carbs_g: sumField(loggedToday, "carbs_g"),
    fat_g: sumField(loggedToday, "fat_g"),
  };
  const plannedNotLogged = {
    calories: sumField(planned, "estimated_calories"),
    protein_g: sumField(planned, "estimated_protein_g"),
    carbs_g: sumField(planned, "estimated_carbs_g"),
    fat_g: sumField(planned, "estimated_fat_g"),
  };

  const target = targets
    ? {
        calories: Number(targets.calorie_target),
        protein_g: Number(targets.protein_g),
        carbs_g: Number(targets.carbs_g),
        fat_g: Number(targets.fat_g),
      }
    : null;

  const projected = {
    calories: loggedSoFar.calories + plannedNotLogged.calories + Number(recipeMacros.calories || 0),
    protein_g: loggedSoFar.protein_g + plannedNotLogged.protein_g + Number(recipeMacros.protein_g || 0),
    carbs_g: loggedSoFar.carbs_g + plannedNotLogged.carbs_g + Number(recipeMacros.carbs_g || 0),
    fat_g: loggedSoFar.fat_g + plannedNotLogged.fat_g + Number(recipeMacros.fat_g || 0),
  };

  return { target, projected, hasTarget: !!target };
}

export async function renderRecipe(container, recipeId) {
  container.innerHTML = "";
  container.appendChild(el("div", { class: "loading" }, "Loading recipe…"));

  let recipe, activeSession, categories;
  try {
    [recipe, activeSession, categories] = await Promise.all([
      api.getRecipe(recipeId),
      api.getActiveSession(),
      api.listCategories(),
    ]);
  } catch (err) {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
    return;
  }

  const categoryName = (id) => categories.find((c) => c.id === id)?.name || `category #${id}`;

  container.innerHTML = "";

  const isMySessionActive = activeSession && Number(activeSession.recipe_id) === Number(recipeId);
  const someoneElseCooking = activeSession && !isMySessionActive;

  if (isMySessionActive) {
    await renderCookMode(container, recipe, activeSession, categoryName);
  } else {
    await renderPreview(container, recipe, categoryName, someoneElseCooking ? activeSession : null);
  }
}

async function renderPreview(container, recipe, categoryName, blockingSession) {
  const header = el("div", { class: "recipe-header" }, [
    el("div", {}, [
      el("h1", {}, recipe.name),
      el("div", { class: "meta" }, [
        recipe.prep_minutes ? el("span", { class: "pill" }, `${recipe.prep_minutes}m prep`) : null,
        recipe.active_minutes ? el("span", { class: "pill" }, `${recipe.active_minutes}m active`) : null,
        recipe.passive_minutes ? el("span", { class: "pill" }, `${recipe.passive_minutes}m passive`) : null,
        el("span", { class: "pill" }, `serves ${recipe.base_servings}`),
      ]),
    ]),
  ]);
  container.appendChild(header);

  if (blockingSession) {
    container.appendChild(
      el(
        "div",
        { class: "banner" },
        `A cooking session is already active for another recipe. Finish or end it before starting this one.`
      )
    );
  }

  const startBtn = el(
    "button",
    { class: "btn", disabled: !!blockingSession, onclick: async () => {
        startBtn.disabled = true;
        startBtn.textContent = "Starting…";
        try {
          await api.startSession(recipe.id);
          window.location.reload();
        } catch (err) {
          toast(errorMessage(err), { error: true });
          startBtn.disabled = false;
          startBtn.textContent = "Let's cook";
        }
      } },
    "Let's cook"
  );
  container.appendChild(el("div", { style: "margin: 14px 0;" }, startBtn));

  const layout = el("div", { class: "cook-layout" });

  const ingCol = el("div", {}, [el("div", { class: "col-title" }, "Ingredients")]);
  recipe.ingredients.forEach((ri) => {
    ingCol.appendChild(
      el("div", { class: "ingredient-row" }, [
        el("div", { class: "ing-name" }, categoryName(ri.category_id)),
        el("div", { class: "ing-qty" }, `${fmt(ri.quantity, 2)} ${ri.unit}`),
      ])
    );
  });
  layout.appendChild(ingCol);

  const midCol = el("div", {}, [el("div", { class: "col-title" }, "Instructions")]);
  parseSteps(recipe.instructions).forEach((step, i) => {
    midCol.appendChild(
      el("div", { class: "step-card" }, [
        el("div", { class: "step-num" }, String(i + 1)),
        el("div", { class: "step-text" }, step),
      ])
    );
  });
  if (!recipe.instructions) midCol.appendChild(el("div", { class: "muted" }, "No instructions yet."));
  layout.appendChild(midCol);

  const rightCol = el("div", {}, [el("div", { class: "col-title" }, "Macros (full recipe)")]);
  try {
    const macros = await api.getRecipeMacros(recipe.id);
    rightCol.appendChild(macroRingCluster(macros.totals, null));
    if (!macros.fully_resolved) {
      rightCol.appendChild(
        el("div", { class: "banner" }, "Some ingredients aren't resolved from current inventory yet — macros may be incomplete.")
      );
    }
  } catch (err) {
    rightCol.appendChild(el("div", { class: "muted" }, "Macros unavailable."));
  }
  layout.appendChild(rightCol);

  container.appendChild(layout);
}

async function renderCookMode(container, recipe, session, categoryName) {
  trayEl = el("div", { class: "timer-tray" });
  renderTray();

  const header = el("div", { class: "recipe-header" }, [
    el("div", {}, [
      el("h1", {}, recipe.name),
      el("div", { class: "meta" }, [el("span", { class: "pill brand" }, "Cooking now")]),
    ]),
    el("div", { class: "row" }, [
      el("button", { class: "btn secondary small", id: "history-btn" }, "History / Revert"),
    ]),
  ]);
  container.appendChild(header);
  container.appendChild(trayEl);

  const layout = el("div", { class: "cook-layout" });
  container.appendChild(layout);

  const checkedSet = new Set();

  async function refresh(newSession) {
    session = newSession;
    layout.innerHTML = "";

    // --- Left: ingredient checklist ---
    const ingCol = el("div", {}, [el("div", { class: "col-title" }, "Ingredients")]);
    session.ingredients.forEach((ing) => {
      const rowChecked = checkedSet.has(ing.recipe_ingredient_id);
      const row = el("div", { class: "ingredient-row" + (rowChecked ? " checked" : "") }, [
        el("input", {
          type: "checkbox",
          checked: rowChecked ? "checked" : null,
          onchange: (e) => {
            if (e.target.checked) checkedSet.add(ing.recipe_ingredient_id);
            else checkedSet.delete(ing.recipe_ingredient_id);
            row.classList.toggle("checked", e.target.checked);
          },
        }),
        el("div", { class: "ing-name" }, categoryName(ing.category_id)),
        el("div", { class: "ing-qty" }, `${fmt(ing.quantity, 2)} ${ing.unit}`),
        el("button", { class: "qty-edit-btn", title: "Edit amount", onclick: () => openEditModal(ing) }, "✎"),
      ]);
      ingCol.appendChild(row);
    });
    ingCol.appendChild(
      el("button", { class: "btn secondary small", style: "margin-top:10px;", onclick: openScaleModal }, "Scale recipe")
    );
    layout.appendChild(ingCol);

    // --- Middle: steps ---
    const midCol = el("div", {});
    midCol.appendChild(el("div", { class: "col-title" }, "Instructions"));
    const steps = parseSteps(recipe.instructions);
    steps.forEach((step, i) => {
      const guess = guessMinutes(step);
      midCol.appendChild(
        el("div", { class: "step-card" }, [
          el("div", { class: "step-num" }, String(i + 1)),
          el("div", { class: "step-text" }, step),
          el("div", { class: "step-actions" }, [
            el(
              "button",
              {
                class: "btn small secondary",
                onclick: () => {
                  const mins = guess || Number(window.prompt("Timer length in minutes?", "5")) || null;
                  if (mins) startTimer(`Step ${i + 1}`, mins);
                },
              },
              guess ? `Start ${guess}m timer` : "Start timer"
            ),
          ]),
        ])
      );
    });
    if (!steps.length) midCol.appendChild(el("div", { class: "muted" }, "No instructions yet."));
    layout.appendChild(midCol);

    // --- Right: macros + actions ---
    const rightCol = el("div", { class: "macro-panel" });
    rightCol.appendChild(el("div", { class: "col-title" }, "Today, including this recipe"));
    try {
      const ctx = await computeDailyContext(session.macros.totals);
      rightCol.appendChild(macroRingCluster(ctx.projected, ctx.target));
      if (!ctx.hasTarget) {
        rightCol.appendChild(el("div", { class: "muted", style: "font-size:0.8rem;" }, "Set your profile (age/sex/height) and log a weigh-in in Settings to see progress toward a target."));
      }
    } catch {
      rightCol.appendChild(macroRingCluster(session.macros.totals, null));
    }

    const actions = el("div", { class: "cook-actions" }, [
      el("button", { class: "btn", onclick: () => openFinishModal() }, "Finish cooking"),
      el("button", { class: "btn secondary", onclick: () => openEndModal() }, "End without deducting"),
    ]);
    rightCol.appendChild(actions);
    layout.appendChild(rightCol);
  }

  function openEditModal(ing) {
    modal((box, close) => {
      box.appendChild(el("h3", {}, `Edit ${categoryName(ing.category_id)}`));
      const deltaInput = el("input", { type: "number", step: "any", placeholder: "e.g. -10 or 5" });
      const absInput = el("input", { type: "number", step: "any", placeholder: `current: ${ing.quantity}` });
      box.appendChild(el("label", { class: "field" }, ["Adjust by amount (+/-), " + ing.unit, deltaInput]));
      box.appendChild(
        el("button", {
          class: "btn small",
          onclick: async () => {
            const amount = Number(deltaInput.value);
            if (!amount) return toast("Enter a non-zero amount", { error: true });
            try {
              const updated = await api.deltaEdit(session.id, ing.recipe_ingredient_id, amount);
              toast(`Adjusted by ${amount > 0 ? "+" : ""}${amount} ${ing.unit} (this time only)`);
              close();
              await refresh(updated);
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Apply delta")
      );
      box.appendChild(el("hr", { style: "border:none; border-top:1px solid var(--border); margin:6px 0;" }));
      box.appendChild(el("label", { class: "field" }, [`Set exact amount, ${ing.unit}`, absInput]));
      box.appendChild(
        el("button", {
          class: "btn small",
          onclick: async () => {
            const qty = Number(absInput.value);
            if (!qty && qty !== 0) return toast("Enter an amount", { error: true });
            try {
              const updated = await api.absoluteEdit(session.id, ing.recipe_ingredient_id, qty);
              toast(`Set to ${qty} ${ing.unit} (this time only)`);
              close();
              await refresh(updated);
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Set amount")
      );
      box.appendChild(
        el("button", {
          class: "btn secondary small",
          onclick: async () => {
            try {
              const updated = await api.commitPermanent(session.id);
              toast("Saved as a permanent recipe change.");
              close();
              await refresh(updated);
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Make current edits permanent")
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  function openScaleModal() {
    modal((box, close) => {
      box.appendChild(el("h3", {}, "Scale recipe"));
      box.appendChild(el("div", { class: "muted" }, `Currently serves ${recipe.base_servings}.`));
      const servingsInput = el("input", { type: "number", step: "any", placeholder: "target servings" });
      box.appendChild(el("label", { class: "field" }, ["Target servings", servingsInput]));
      box.appendChild(
        el("button", {
          class: "btn small",
          onclick: async () => {
            const target = Number(servingsInput.value);
            if (!target) return toast("Enter a target servings amount", { error: true });
            try {
              const updated = await api.scaleSession(session.id, { target_servings: target });
              toast(`Scaled to ${target} servings.`);
              close();
              await refresh(updated);
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Scale by servings")
      );

      box.appendChild(el("hr", { style: "border:none; border-top:1px solid var(--border); margin:6px 0;" }));
      box.appendChild(el("div", { class: "muted" }, "Or scale to match one ingredient's amount:"));
      const ingSelect = el("select", {});
      session.ingredients.forEach((ing) => {
        ingSelect.appendChild(el("option", { value: ing.recipe_ingredient_id }, `${categoryName(ing.category_id)} (${ing.quantity} ${ing.unit})`));
      });
      const qtyInput = el("input", { type: "number", step: "any", placeholder: "new amount" });
      const moreServings = el("select", {}, [
        el("option", { value: "false" }, "Still one meal (batch is just bigger)"),
        el("option", { value: "true" }, "Makes more servings"),
      ]);
      box.appendChild(el("label", { class: "field" }, ["Ingredient", ingSelect]));
      box.appendChild(el("label", { class: "field" }, ["New amount", qtyInput]));
      box.appendChild(el("label", { class: "field" }, ["This changes:", moreServings]));
      box.appendChild(
        el("button", {
          class: "btn small secondary",
          onclick: async () => {
            const qty = Number(qtyInput.value);
            if (!qty) return toast("Enter the new amount", { error: true });
            try {
              const updated = await api.scaleSession(session.id, {
                target_recipe_ingredient_id: Number(ingSelect.value),
                target_quantity: qty,
                more_servings: moreServings.value === "true",
              });
              toast("Recipe scaled.");
              close();
              await refresh(updated);
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Scale by ingredient")
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  function openFinishModal() {
    modal((box, close) => {
      box.appendChild(el("h3", {}, "Finish cooking"));
      const modeSelect = el("select", {}, [
        el("option", { value: "deduct_and_eaten" }, "Deduct ingredients and count as eaten"),
        el("option", { value: "deduct_only" }, "Just deduct ingredients (eat/log later)"),
      ]);
      const percentInput = el("input", { type: "number", value: "100", min: "0", max: "100" });
      box.appendChild(el("label", { class: "field" }, ["What happened?", modeSelect]));
      box.appendChild(el("label", { class: "field" }, ["Percent of the recipe eaten", percentInput]));
      box.appendChild(
        el("button", {
          class: "btn",
          onclick: async () => {
            try {
              const result = await api.finishCooking(session.id, {
                mode: modeSelect.value,
                percent_eaten: Number(percentInput.value) || 100,
              });
              toast("Cooking session finished.");
              close();
              clearTimersAndReload();
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Confirm")
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  function openEndModal() {
    modal((box, close) => {
      box.appendChild(el("h3", {}, "End session without deducting?"));
      box.appendChild(el("div", { class: "muted" }, "Nothing will be deducted from inventory and nothing will be logged as eaten."));
      box.appendChild(
        el("button", {
          class: "btn danger",
          onclick: async () => {
            try {
              await api.finishSession(session.id);
              close();
              clearTimersAndReload();
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "End session")
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  function clearTimersAndReload() {
    timers.length = 0;
    if (timerTick) { clearInterval(timerTick); timerTick = null; }
    window.location.reload();
  }

  header.querySelector("#history-btn").addEventListener("click", () => {
    modal(async (box, close) => {
      box.appendChild(el("h3", {}, "History / Revert"));
      box.appendChild(
        el("button", {
          class: "btn secondary small",
          onclick: async () => {
            try {
              const updated = await api.revertSession(session.id, { mode: "discard_session_edits" });
              toast("Discarded this session's edits.");
              close();
              await refresh(updated);
            } catch (err) {
              toast(errorMessage(err), { error: true });
            }
          },
        }, "Discard this session's edits")
      );
      const list = el("div", { class: "loading" }, "Loading versions…");
      box.appendChild(list);
      try {
        const versions = await api.listVersions(session.id);
        list.innerHTML = "";
        if (!versions.length) list.appendChild(el("div", { class: "muted" }, "No saved versions yet."));
        versions.forEach((v) => {
          list.appendChild(
            el("div", { class: "log-entry" }, [
              el("div", { class: "desc" }, `Version ${v.version_number} — ${new Date(v.changed_at).toLocaleString()}`),
              el("button", {
                class: "btn small secondary",
                onclick: async () => {
                  try {
                    const updated = await api.revertSession(session.id, { mode: "restore_version", version_id: v.id });
                    toast(`Restored version ${v.version_number}.`);
                    close();
                    await refresh(updated);
                  } catch (err) {
                    toast(errorMessage(err), { error: true });
                  }
                },
              }, "Restore"),
            ])
          );
        });
      } catch (err) {
        list.innerHTML = "";
        list.appendChild(el("div", { class: "muted" }, errorMessage(err)));
      }
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Close"));
    });
  });

  await refresh(session);
}
