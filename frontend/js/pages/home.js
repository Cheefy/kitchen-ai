import { api } from "../api.js";
import { el, fmt, errorMessage } from "../util.js";

function recipeCard(candidate, onOpen) {
  const macros = candidate.macros || {};
  const card = el(
    "div",
    { class: "recipe-card", onclick: () => onOpen(candidate.recipe_id) },
    [
      el("div", { class: "name" }, candidate.name),
      el("div", { class: "macro-line" }, [
        el("span", {}, [el("b", {}, fmt(macros.calories)), " kcal"]),
        el("span", {}, [el("b", {}, fmt(macros.protein_g)), "g protein"]),
      ]),
    ]
  );
  return card;
}

function recipeCardFromFull(recipe, onOpen) {
  const totalMin = (recipe.prep_minutes || 0) + (recipe.active_minutes || 0);
  return el(
    "div",
    { class: "recipe-card", onclick: () => onOpen(recipe.id) },
    [
      el("div", { class: "name" }, recipe.name),
      el("div", { class: "meta" }, [
        totalMin ? el("span", { class: "pill" }, `${totalMin} min`) : null,
        recipe.passive_minutes ? el("span", { class: "pill" }, `+${recipe.passive_minutes} passive`) : null,
        el("span", { class: "pill" }, `serves ${recipe.base_servings}`),
      ]),
    ]
  );
}

export async function renderHome(container, navigate) {
  container.innerHTML = "";
  const wrap = el("div", {});

  const searchWrap = el("div", { class: "search-bar" });
  const searchInput = el("input", {
    type: "text",
    placeholder: "Search recipes or meals…",
  });
  searchWrap.appendChild(searchInput);
  wrap.appendChild(searchWrap);

  const results = el("div", {});
  wrap.appendChild(results);
  container.appendChild(wrap);

  results.appendChild(el("div", { class: "loading" }, "Loading recipes…"));

  let allRecipes = [];
  let recommendations = null;

  try {
    [allRecipes, recommendations] = await Promise.all([
      api.listRecipes(),
      api.getRecommendations().catch(() => null),
    ]);
  } catch (err) {
    results.innerHTML = "";
    results.appendChild(el("div", { class: "empty-state" }, errorMessage(err)));
    return;
  }

  function openRecipe(id) {
    window.location.hash = `#/recipe/${id}`;
  }

  function renderSearch(query) {
    results.innerHTML = "";
    const q = query.trim().toLowerCase();
    const matches = allRecipes.filter((r) => r.name.toLowerCase().includes(q));
    results.appendChild(el("div", { class: "section-title" }, `Results for “${query}”`));
    if (!matches.length) {
      results.appendChild(el("div", { class: "empty-state" }, "No recipes match that search."));
      return;
    }
    const grid = el("div", { class: "recipe-grid" });
    matches.forEach((r) => grid.appendChild(recipeCardFromFull(r, openRecipe)));
    results.appendChild(grid);
  }

  function renderRecommended() {
    results.innerHTML = "";

    if (recommendations && recommendations.expiring_unused_ingredients?.length) {
      const n = recommendations.expiring_unused_ingredients.length;
      results.appendChild(
        el(
          "div",
          { class: "banner" },
          `${n} ingredient${n > 1 ? "s" : ""} expiring soon aren't used in any full-stock recipe — check the shopping list / inventory.`
        )
      );
    }

    if (!recommendations) {
      results.appendChild(el("div", { class: "section-title" }, "All recipes"));
      const grid = el("div", { class: "recipe-grid" });
      allRecipes.forEach((r) => grid.appendChild(recipeCardFromFull(r, openRecipe)));
      results.appendChild(grid);
      return;
    }

    const { full_stock, shopping_required } = recommendations;

    results.appendChild(el("div", { class: "section-title" }, "Ready to cook now"));
    if (full_stock.length) {
      const grid = el("div", { class: "recipe-grid" });
      full_stock.forEach((c) => grid.appendChild(recipeCard(c, openRecipe)));
      results.appendChild(grid);
    } else {
      results.appendChild(el("div", { class: "empty-state" }, "Nothing fully in stock right now."));
    }

    results.appendChild(el("div", { class: "section-title" }, "Need a shopping trip"));
    if (shopping_required.length) {
      const grid = el("div", { class: "recipe-grid" });
      shopping_required.forEach((c) => grid.appendChild(recipeCard(c, openRecipe)));
      results.appendChild(grid);
    } else {
      results.appendChild(el("div", { class: "empty-state" }, "Nothing waiting on a shopping trip."));
    }

    if (!full_stock.length && !shopping_required.length && allRecipes.length) {
      results.appendChild(el("div", { class: "section-title" }, "All recipes"));
      const grid = el("div", { class: "recipe-grid" });
      allRecipes.forEach((r) => grid.appendChild(recipeCardFromFull(r, openRecipe)));
      results.appendChild(grid);
    }

    if (!allRecipes.length) {
      results.appendChild(
        el("div", { class: "empty-state" }, "No recipes yet — seed some via the API to get recommendations.")
      );
    }
  }

  searchInput.addEventListener("input", () => {
    const q = searchInput.value;
    if (q.trim()) renderSearch(q);
    else renderRecommended();
  });

  renderRecommended();
}
