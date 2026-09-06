import { api } from "../api.js";
import { el, fmt, toast, errorMessage } from "../util.js";

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

export async function renderInventory(container) {
  container.innerHTML = "";
  container.appendChild(el("div", { class: "loading" }, "Loading inventory…"));

  let cookwareList, inventoryList, ingredientsList, categories, batches, recipes;
  try {
    [cookwareList, inventoryList, ingredientsList, categories, batches, recipes] = await Promise.all([
      api.listCookware(),
      api.listInventory(),
      api.listIngredients(),
      api.listCategories(),
      api.listBatches(true),
      api.listRecipes(),
    ]);
  } catch (err) {
    container.innerHTML = "";
    container.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
    return;
  }

  container.innerHTML = "";

  const ingredientName = (id) => ingredientsList.find((i) => i.id === id)?.name || `ingredient #${id}`;
  const recipeName = (id) => recipes.find((r) => r.id === id)?.name || `recipe #${id}`;

  function categorySelect() {
    const s = el("select", {});
    categories.forEach((c) => s.appendChild(el("option", { value: c.id }, c.name)));
    return s;
  }

  async function reload() {
    await renderInventory(container);
  }

  container.appendChild(el("h1", { style: "margin: 0 0 16px;" }, "Inventory"));

  const tabDefs = [
    { key: "parts", label: "Parts" },
    { key: "ingredients", label: "Ingredients" },
    { key: "mealpreps", label: "Meal Preps" },
  ];
  let active = "parts";

  const tabBar = el("div", { class: "segmented" });
  const body = el("div", { style: "margin-top:16px;" });
  container.appendChild(tabBar);
  container.appendChild(body);

  function renderTabBar() {
    tabBar.innerHTML = "";
    tabDefs.forEach((t) => {
      tabBar.appendChild(
        el(
          "button",
          {
            class: t.key === active ? "active" : "",
            onclick: () => {
              active = t.key;
              renderTabBar();
              renderBody();
            },
          },
          t.label
        )
      );
    });
  }

  function renderBody() {
    body.innerHTML = "";
    if (active === "parts") renderParts();
    else if (active === "ingredients") renderIngredients();
    else renderMealPreps();
  }

  // ---------------------------------------------------------------- Parts
  function renderParts() {
    body.appendChild(
      el("div", { class: "row", style: "justify-content:space-between; margin-bottom:14px;" }, [
        el("div", { class: "muted" }, `${cookwareList.length} item${cookwareList.length === 1 ? "" : "s"}`),
        el("button", { class: "btn", onclick: () => openCookwareModal(null) }, "+ Add cookware"),
      ])
    );
    if (!cookwareList.length) {
      body.appendChild(el("div", { class: "empty-state" }, "No cookware on file yet."));
      return;
    }
    cookwareList.forEach((c) => {
      const meta = [c.type, c.tare_weight ? `tare ${fmt(c.tare_weight, 1)}g` : null, c.label_number ? `label ${c.label_number}` : null]
        .filter(Boolean)
        .join(" · ");
      body.appendChild(
        el("div", { class: "log-entry" }, [
          el("div", { class: "desc" }, [
            el("div", { style: "font-weight:600;" }, c.name),
            meta ? el("div", { class: "muted", style: "font-size:0.8rem;" }, meta) : null,
          ]),
          el("div", { class: "row" }, [
            el("button", { class: "btn secondary small", onclick: () => openCookwareModal(c) }, "Edit"),
            el("button", { class: "btn danger small", onclick: () => deleteCookware(c) }, "Delete"),
          ]),
        ])
      );
    });
  }

  function openCookwareModal(existing) {
    modal((box, close) => {
      box.appendChild(el("h3", {}, existing ? "Edit cookware" : "Add cookware"));
      const nameInput = el("input", { type: "text", value: existing?.name || "", placeholder: "e.g. 10in cast iron skillet" });
      const typeInput = el("input", { type: "text", value: existing?.type || "", placeholder: "e.g. pan, pot, sheet" });
      const tareInput = el("input", { type: "number", step: "any", value: existing?.tare_weight ?? "", placeholder: "grams" });
      const labelInput = el("input", { type: "text", value: existing?.label_number || "", placeholder: "optional physical label" });
      box.appendChild(el("label", { class: "field" }, ["Name", nameInput]));
      box.appendChild(el("label", { class: "field" }, ["Type", typeInput]));
      box.appendChild(el("label", { class: "field" }, ["Tare weight (g)", tareInput]));
      box.appendChild(el("label", { class: "field" }, ["Label number", labelInput]));
      box.appendChild(
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              const name = nameInput.value.trim();
              if (!name) return toast("Enter a name", { error: true });
              const payload = {
                name,
                type: typeInput.value.trim() || null,
                tare_weight: tareInput.value ? Number(tareInput.value) : null,
                label_number: labelInput.value.trim() || null,
              };
              try {
                if (existing) await api.updateCookware(existing.id, payload);
                else await api.createCookware(payload);
                toast(existing ? "Cookware updated." : "Cookware added.");
                close();
                await reload();
              } catch (err) {
                toast(errorMessage(err), { error: true });
              }
            },
          },
          existing ? "Save" : "Add"
        )
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  async function deleteCookware(c) {
    if (!window.confirm(`Delete "${c.name}"?`)) return;
    try {
      await api.deleteCookware(c.id);
      toast("Cookware deleted.");
      await reload();
    } catch (err) {
      toast(errorMessage(err), { error: true });
    }
  }

  // ----------------------------------------------------------- Ingredients
  function renderIngredients() {
    body.appendChild(
      el("div", { class: "row", style: "justify-content:space-between; margin-bottom:14px;" }, [
        el("div", { class: "muted" }, `${inventoryList.length} item${inventoryList.length === 1 ? "" : "s"} in stock`),
        el("button", { class: "btn", onclick: openAddInventoryModal }, "+ Add to inventory"),
      ])
    );
    if (!inventoryList.length) {
      body.appendChild(el("div", { class: "empty-state" }, "Nothing in stock yet."));
      return;
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    inventoryList.forEach((item) => {
      let expBadge = null;
      if (item.expiration_date) {
        const exp = new Date(item.expiration_date);
        const days = Math.round((exp - today) / 86400000);
        if (days < 0) expBadge = el("span", { class: "pill warn" }, "expired");
        else if (days <= 3) expBadge = el("span", { class: "pill warn" }, `expires in ${days}d`);
        else expBadge = el("span", { class: "pill" }, `expires ${item.expiration_date}`);
      }
      body.appendChild(
        el("div", { class: "log-entry" }, [
          el("div", { class: "desc" }, [
            el("div", { style: "font-weight:600;" }, ingredientName(item.ingredient_id)),
            el("div", { class: "row wrap", style: "margin-top:4px; gap:6px;" }, [
              el("span", { class: "pill" }, `${fmt(item.quantity, 2)} ${item.unit}`),
              item.location ? el("span", { class: "pill" }, item.location) : null,
              expBadge,
            ]),
          ]),
          el("div", { class: "row" }, [
            el("button", { class: "btn secondary small", onclick: () => openEditInventoryModal(item) }, "Edit"),
            el("button", { class: "btn danger small", onclick: () => deleteInventoryItem(item) }, "Delete"),
          ]),
        ])
      );
    });
  }

  function openEditInventoryModal(item) {
    modal((box, close) => {
      box.appendChild(el("h3", {}, `Edit ${ingredientName(item.ingredient_id)}`));
      const qtyInput = el("input", { type: "number", step: "any", value: item.quantity });
      const expInput = el("input", { type: "date", value: item.expiration_date || "" });
      const locInput = el("input", { type: "text", value: item.location || "", placeholder: "e.g. fridge, pantry" });
      box.appendChild(el("label", { class: "field" }, [`Quantity (${item.unit})`, qtyInput]));
      box.appendChild(el("label", { class: "field" }, ["Expiration date", expInput]));
      box.appendChild(el("label", { class: "field" }, ["Location", locInput]));
      box.appendChild(
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              const qty = Number(qtyInput.value);
              if (!qty && qty !== 0) return toast("Enter a quantity", { error: true });
              try {
                await api.updateInventoryItem(item.id, {
                  quantity: qty,
                  expiration_date: expInput.value || null,
                  location: locInput.value.trim() || null,
                });
                toast("Inventory updated.");
                close();
                await reload();
              } catch (err) {
                toast(errorMessage(err), { error: true });
              }
            },
          },
          "Save"
        )
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  async function deleteInventoryItem(item) {
    if (!window.confirm(`Remove ${ingredientName(item.ingredient_id)} from inventory?`)) return;
    try {
      await api.deleteInventoryItem(item.id);
      toast("Removed from inventory.");
      await reload();
    } catch (err) {
      toast(errorMessage(err), { error: true });
    }
  }

  function openAddInventoryModal() {
    modal((box, close) => {
      box.appendChild(el("h3", {}, "Add to inventory"));

      const modeSelect = el("select", {}, [
        el("option", { value: "existing" }, "Pick an ingredient I already have on file"),
        el("option", { value: "barcode" }, "Scan / enter a barcode"),
        el("option", { value: "search" }, "Search by name (USDA database)"),
        el("option", { value: "manual" }, "Enter nutrition facts manually"),
      ]);
      box.appendChild(el("label", { class: "field" }, ["How do you want to add it?", modeSelect]));

      const dynamicArea = el("div", {});
      box.appendChild(dynamicArea);

      let resolvedIngredientId = null;

      function renderExisting() {
        dynamicArea.innerHTML = "";
        resolvedIngredientId = ingredientsList[0]?.id ?? null;
        if (!ingredientsList.length) {
          dynamicArea.appendChild(el("div", { class: "muted" }, "No ingredients on file yet — try another option above."));
          return;
        }
        const select = el(
          "select",
          {},
          ingredientsList.map((i) => el("option", { value: i.id }, i.name))
        );
        select.addEventListener("change", () => {
          resolvedIngredientId = Number(select.value);
        });
        dynamicArea.appendChild(el("label", { class: "field" }, ["Ingredient", select]));
      }

      function renderBarcode() {
        dynamicArea.innerHTML = "";
        resolvedIngredientId = null;
        const upcInput = el("input", { type: "text", placeholder: "UPC/EAN barcode" });
        const preview = el("div", { style: "margin-top:10px;" });
        const lookupBtn = el(
          "button",
          {
            class: "btn small secondary",
            onclick: async () => {
              const upc = upcInput.value.trim();
              if (!upc) return toast("Enter a barcode", { error: true });
              lookupBtn.disabled = true;
              lookupBtn.textContent = "Looking up…";
              preview.innerHTML = "";
              try {
                let match = null;
                try {
                  match = await api.lookupBarcodeLocal(upc);
                } catch {
                  /* not in our own catalog yet -- fall through to external */
                }
                if (match) {
                  resolvedIngredientId = match.id;
                  preview.appendChild(el("div", { class: "banner" }, `Already on file: ${match.name}`));
                } else {
                  const ext = await api.lookupBarcodeExternal(upc);
                  preview.appendChild(
                    el("div", { class: "card" }, [
                      el("div", { style: "font-weight:700;" }, ext.name),
                      el(
                        "div",
                        { class: "muted", style: "font-size:0.8rem; margin:4px 0 10px;" },
                        `via ${ext.source} · per ${fmt(ext.serving_size)}${ext.serving_size_unit}`
                      ),
                      el("div", { class: "row wrap" }, [
                        el("span", { class: "pill" }, `${fmt(ext.calories)} kcal`),
                        el("span", { class: "pill" }, `${fmt(ext.protein_g, 1)}g protein`),
                        el("span", { class: "pill" }, `${fmt(ext.carbs_g, 1)}g carbs`),
                        el("span", { class: "pill" }, `${fmt(ext.fat_g, 1)}g fat`),
                      ]),
                    ])
                  );
                  const catSelect = categorySelect();
                  const confirmBtn = el(
                    "button",
                    {
                      class: "btn small",
                      style: "margin-top:8px;",
                      onclick: async () => {
                        try {
                          const created = await api.createIngredientFromBarcode(upc, Number(catSelect.value));
                          resolvedIngredientId = created.id;
                          ingredientsList.push(created);
                          toast(`Added "${created.name}" to your ingredient catalog.`);
                          preview.appendChild(el("div", { class: "muted", style: "margin-top:6px;" }, "Saved — fill in quantity below."));
                          confirmBtn.disabled = true;
                        } catch (err) {
                          toast(errorMessage(err), { error: true });
                        }
                      },
                    },
                    "Save this to my ingredients"
                  );
                  preview.appendChild(el("label", { class: "field", style: "margin-top:10px;" }, ["Category", catSelect]));
                  preview.appendChild(confirmBtn);
                }
              } catch {
                preview.appendChild(
                  el("div", { class: "empty-state" }, "No match locally or externally — try \"Enter nutrition facts manually\" instead.")
                );
              } finally {
                lookupBtn.disabled = false;
                lookupBtn.textContent = "Look up";
              }
            },
          },
          "Look up"
        );
        dynamicArea.appendChild(el("label", { class: "field" }, ["Barcode", upcInput]));
        dynamicArea.appendChild(lookupBtn);
        dynamicArea.appendChild(preview);
      }

      function renderSearch() {
        dynamicArea.innerHTML = "";
        resolvedIngredientId = null;
        const qInput = el("input", { type: "text", placeholder: "e.g. chicken breast" });
        const results = el("div", { style: "margin-top:10px; display:flex; flex-direction:column; gap:8px;" });
        const searchBtn = el(
          "button",
          {
            class: "btn small secondary",
            onclick: async () => {
              const q = qInput.value.trim();
              if (!q) return toast("Enter something to search for", { error: true });
              searchBtn.disabled = true;
              searchBtn.textContent = "Searching…";
              results.innerHTML = "";
              try {
                const candidates = await api.searchNutrition(q);
                if (!candidates.length) {
                  results.appendChild(el("div", { class: "muted" }, "No matches — try \"Enter nutrition facts manually\" instead."));
                }
                candidates.forEach((c) => {
                  results.appendChild(
                    el(
                      "button",
                      {
                        class: "btn small secondary",
                        style: "text-align:left; justify-content:flex-start;",
                        onclick: () => pickCandidate(c, results),
                      },
                      `${c.name} — ${fmt(c.calories)} kcal, ${fmt(c.protein_g, 1)}g protein (${c.source})`
                    )
                  );
                });
              } catch (err) {
                toast(errorMessage(err), { error: true });
              } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = "Search";
              }
            },
          },
          "Search"
        );
        dynamicArea.appendChild(el("label", { class: "field" }, ["Search USDA FoodData Central", qInput]));
        dynamicArea.appendChild(searchBtn);
        dynamicArea.appendChild(results);
      }

      function pickCandidate(c, resultsEl) {
        const catSelect = categorySelect();
        resultsEl.innerHTML = "";
        resultsEl.appendChild(el("div", { style: "font-weight:600;" }, c.name));
        resultsEl.appendChild(el("label", { class: "field", style: "margin-top:6px;" }, ["Category", catSelect]));
        const saveBtn = el(
          "button",
          {
            class: "btn small",
            style: "margin-top:8px;",
            onclick: async () => {
              try {
                const created = await api.createIngredient({
                  name: c.name,
                  category_id: Number(catSelect.value),
                  calories: c.calories,
                  protein_g: c.protein_g,
                  carbs_g: c.carbs_g,
                  fat_g: c.fat_g,
                  fiber_g: c.fiber_g,
                  sugars_g: c.sugars_g,
                  sodium_mg: c.sodium_mg,
                  saturated_fat_g: c.saturated_fat_g,
                  serving_size: c.serving_size,
                  serving_size_unit: c.serving_size_unit,
                  source: c.source,
                });
                resolvedIngredientId = created.id;
                ingredientsList.push(created);
                toast(`Added "${created.name}" to your ingredient catalog.`);
                saveBtn.disabled = true;
              } catch (err) {
                toast(errorMessage(err), { error: true });
              }
            },
          },
          "Save this to my ingredients"
        );
        resultsEl.appendChild(saveBtn);
      }

      function renderManual() {
        dynamicArea.innerHTML = "";
        resolvedIngredientId = null;
        const nameInput = el("input", { type: "text", placeholder: "Name" });
        const catSelect = categorySelect();
        const calInput = el("input", { type: "number", step: "any", placeholder: "kcal per 100g" });
        const proInput = el("input", { type: "number", step: "any", placeholder: "protein g per 100g" });
        const carbInput = el("input", { type: "number", step: "any", placeholder: "carbs g per 100g" });
        const fatInput = el("input", { type: "number", step: "any", placeholder: "fat g per 100g" });
        dynamicArea.appendChild(el("label", { class: "field" }, ["Name", nameInput]));
        dynamicArea.appendChild(el("label", { class: "field" }, ["Category", catSelect]));
        dynamicArea.appendChild(el("label", { class: "field" }, ["Calories / 100g", calInput]));
        dynamicArea.appendChild(el("label", { class: "field" }, ["Protein g / 100g", proInput]));
        dynamicArea.appendChild(el("label", { class: "field" }, ["Carbs g / 100g", carbInput]));
        dynamicArea.appendChild(el("label", { class: "field" }, ["Fat g / 100g", fatInput]));
        const saveBtn = el(
          "button",
          {
            class: "btn small secondary",
            style: "margin-top:8px;",
            onclick: async () => {
              const name = nameInput.value.trim();
              if (!name) return toast("Enter a name", { error: true });
              try {
                const created = await api.createIngredient({
                  name,
                  category_id: Number(catSelect.value),
                  calories: Number(calInput.value) || null,
                  protein_g: Number(proInput.value) || null,
                  carbs_g: Number(carbInput.value) || null,
                  fat_g: Number(fatInput.value) || null,
                  serving_size: 100,
                  serving_size_unit: "g",
                  source: "user-entered",
                });
                resolvedIngredientId = created.id;
                ingredientsList.push(created);
                toast(`Added "${created.name}" to your ingredient catalog.`);
                saveBtn.disabled = true;
              } catch (err) {
                toast(errorMessage(err), { error: true });
              }
            },
          },
          "Save this to my ingredients"
        );
        dynamicArea.appendChild(saveBtn);
      }

      const modeRenderers = { existing: renderExisting, barcode: renderBarcode, search: renderSearch, manual: renderManual };
      modeSelect.addEventListener("change", () => modeRenderers[modeSelect.value]());
      renderExisting();

      box.appendChild(el("hr", { style: "border:none; border-top:1px solid var(--border); margin:6px 0;" }));

      const qtyInput = el("input", { type: "number", step: "any", placeholder: "amount" });
      const unitInput = el("input", { type: "text", placeholder: "g, ml, count, etc." });
      const expInput = el("input", { type: "date" });
      const locInput = el("input", { type: "text", placeholder: "e.g. fridge, pantry" });
      box.appendChild(el("label", { class: "field" }, ["Quantity", qtyInput]));
      box.appendChild(el("label", { class: "field" }, ["Unit", unitInput]));
      box.appendChild(el("label", { class: "field" }, ["Expiration date (optional)", expInput]));
      box.appendChild(el("label", { class: "field" }, ["Location (optional)", locInput]));

      box.appendChild(
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              if (!resolvedIngredientId) return toast("Pick or save an ingredient first", { error: true });
              const qty = Number(qtyInput.value);
              if (!qty) return toast("Enter a quantity", { error: true });
              if (!unitInput.value.trim()) return toast("Enter a unit", { error: true });
              try {
                await api.addInventoryItem({
                  ingredient_id: resolvedIngredientId,
                  quantity: qty,
                  unit: unitInput.value.trim(),
                  expiration_date: expInput.value || null,
                  location: locInput.value.trim() || null,
                });
                toast("Added to inventory.");
                close();
                await reload();
              } catch (err) {
                toast(errorMessage(err), { error: true });
              }
            },
          },
          "Add to inventory"
        )
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  // ----------------------------------------------------------- Meal preps
  function renderMealPreps() {
    body.appendChild(
      el("div", { class: "muted", style: "margin-bottom:14px;" }, `${batches.length} pending batch${batches.length === 1 ? "" : "es"}`)
    );
    if (!batches.length) {
      body.appendChild(el("div", { class: "empty-state" }, "No meal-prep batches waiting to be eaten."));
      return;
    }
    batches.forEach((b) => {
      const pctRemaining = Math.round(Number(b.units_remaining) * 100);
      body.appendChild(
        el("div", { class: "log-entry" }, [
          el("div", { class: "desc" }, [
            el("div", { style: "font-weight:600;" }, recipeName(b.recipe_id)),
            el(
              "div",
              { class: "muted", style: "font-size:0.8rem;" },
              `Prepped ${new Date(b.date_prepared).toLocaleDateString()} · ${pctRemaining}% remaining`
            ),
            el("div", { class: "row wrap", style: "margin-top:4px; gap:6px;" }, [
              el("span", { class: "pill" }, `${fmt(b.macros_per_unit.calories)} kcal/unit`),
              el("span", { class: "pill" }, `${fmt(b.macros_per_unit.protein_g, 1)}g protein`),
            ]),
          ]),
          el("div", { class: "row" }, [
            el("button", { class: "btn secondary small", onclick: () => openBatchActionModal(b, "eat") }, "Eat"),
            el("button", { class: "btn danger small", onclick: () => openBatchActionModal(b, "dispose") }, "Dispose"),
          ]),
        ])
      );
    });
  }

  function openBatchActionModal(batch, action) {
    modal((box, close) => {
      box.appendChild(el("h3", {}, action === "eat" ? "Eat from this batch" : "Dispose of this batch"));
      const pctInput = el("input", { type: "number", value: "100", min: "0", max: "100" });
      box.appendChild(el("label", { class: "field" }, ["Percent of the batch", pctInput]));
      box.appendChild(
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              const pct = Number(pctInput.value) || 0;
              if (!pct) return toast("Enter a percent", { error: true });
              try {
                if (action === "eat") await api.eatBatch(batch.id, pct);
                else await api.disposeBatch(batch.id, pct);
                toast(action === "eat" ? "Logged as eaten." : "Disposed.");
                close();
                await reload();
              } catch (err) {
                toast(errorMessage(err), { error: true });
              }
            },
          },
          "Confirm"
        )
      );
      box.appendChild(el("button", { class: "btn ghost", onclick: close }, "Cancel"));
    });
  }

  renderTabBar();
  renderBody();
}
