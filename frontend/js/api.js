// Thin fetch wrapper around the Kitchen AI FastAPI backend. The frontend is
// served by the same FastAPI app (see backend/app/main.py), so plain
// relative paths work with no CORS setup needed.

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }
  if (!res.ok) {
    const detail = data && data.detail !== undefined ? data.detail : data;
    throw new ApiError(res.status, detail);
  }
  return data;
}

const get = (path) => request("GET", path);
const post = (path, body) => request("POST", path, body ?? {});
const patch = (path, body) => request("PATCH", path, body ?? {});
const put = (path, body) => request("PUT", path, body ?? {});
const del = (path) => request("DELETE", path);

export const api = {
  ApiError,

  // Recipes
  listRecipes: () => get("/recipes"),
  getRecipe: (id) => get(`/recipes/${id}`),
  getRecipeMacros: (id) => get(`/recipes/${id}/macros`),
  getDownscaleSuggestion: (id) => get(`/recipes/${id}/downscale-suggestion`),
  listCategories: () => get("/categories").catch(() => []),
  createCategory: (name) => post("/categories", { name }),

  // Ingredients (catalog) / nutrition & barcode lookup
  listIngredients: (q) => get(`/ingredients${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  createIngredient: (body) => post("/ingredients", body),
  lookupBarcodeLocal: (upc) => get(`/ingredients/barcode/${upc}`),
  lookupBarcodeExternal: (upc) => get(`/ingredients/barcode/${upc}/external`),
  createIngredientFromBarcode: (upc, categoryId) =>
    post("/ingredients/from-barcode", { upc, category_id: categoryId }),
  searchNutrition: (q) => get(`/ingredients/nutrition-search?q=${encodeURIComponent(q)}`),

  // Inventory (ingredient stock)
  listInventory: (ingredientId) =>
    get(`/inventory${ingredientId ? `?ingredient_id=${ingredientId}` : ""}`),
  addInventoryItem: (body) => post("/inventory", body),
  updateInventoryItem: (id, body) => patch(`/inventory/${id}`, body),
  deleteInventoryItem: (id) => del(`/inventory/${id}`),

  // Cookware ("parts")
  listCookware: () => get("/cookware"),
  createCookware: (body) => post("/cookware", body),
  updateCookware: (id, body) => patch(`/cookware/${id}`, body),
  deleteCookware: (id) => del(`/cookware/${id}`),

  // Recommendations
  getRecommendations: (maxMinutes) =>
    get(`/recommendations${maxMinutes ? `?max_minutes=${maxMinutes}` : ""}`),

  // Activity / tracking
  listActivityLog: () => get("/activity-log"),
  listWeighIns: () => get("/weigh-ins"),
  createWeighIn: (body) => post("/weigh-ins", body),
  deleteWeighIn: (id) => del(`/weigh-ins/${id}`),
  listGoals: () => get("/goals"),
  getCurrentGoal: () => get("/goals/current").catch((e) => (e.status === 404 ? null : Promise.reject(e))),
  createGoal: (body) => post("/goals", body),
  getRecommendationSettings: () => get("/recommendation-settings"),
  updateRecommendationSettings: (body) => patch("/recommendation-settings", body),
  listPlannedMeals: () => get("/planned-meals"),

  // Profile / TDEE / calendar
  getProfile: () => get("/profile").catch((e) => (e.status === 404 ? null : Promise.reject(e))),
  updateProfile: (body) => put("/profile", body),
  getTdee: () => get("/profile/tdee").catch((e) => (e.status === 409 ? null : Promise.reject(e))),
  getDailyTargets: () => get("/profile/targets").catch((e) => (e.status === 409 ? null : Promise.reject(e))),
  getCalendar: (start, end) => get(`/calendar?start=${start}&end=${end}`),
  exportSettings: () => get("/settings/export"),
  importSettings: (body) => post("/settings/import", body),

  // Meal log
  listMealLog: () => get("/meal-log"),

  // Garmin
  syncGarmin: (days) => post(`/garmin/sync?days=${days ?? 7}`),

  // Sessions (cook mode)
  startSession: (recipeId) => post("/sessions/start", { recipe_id: recipeId }),
  getActiveSession: () => get("/sessions/active").catch((e) => (e.status === 404 ? null : Promise.reject(e))),
  finishSession: (id) => post(`/sessions/${id}/finish`),
  deltaEdit: (sessionId, riId, amount) =>
    patch(`/sessions/${sessionId}/ingredients/${riId}/delta`, { amount }),
  absoluteEdit: (sessionId, riId, quantity) =>
    patch(`/sessions/${sessionId}/ingredients/${riId}/absolute`, { quantity }),
  scaleSession: (sessionId, body) => post(`/sessions/${sessionId}/scale`, body),
  commitPermanent: (sessionId) => post(`/sessions/${sessionId}/commit-permanent`),
  listVersions: (sessionId) => get(`/sessions/${sessionId}/versions`),
  revertSession: (sessionId, body) => post(`/sessions/${sessionId}/revert`, body),
  finishCooking: (sessionId, body) => post(`/sessions/${sessionId}/finish-cooking`, body),

  // Meal prep batches
  listBatches: (pendingOnly) => get(`/meal-prep-batches${pendingOnly ? "?pending_only=true" : ""}`),
  eatBatch: (id, percent) => post(`/meal-prep-batches/${id}/eat`, { percent }),
  disposeBatch: (id, percent) => post(`/meal-prep-batches/${id}/dispose`, { percent }),

  // Behavior settings
  listBehaviorSettings: () => get("/behavior-settings"),
  setBehaviorSetting: (key, mode) => put(`/behavior-settings/${key}`, { mode }),

  // Allergens
  listAllergenRestrictions: () => get("/allergen-restrictions"),
  addAllergenRestriction: (allergenId) => post("/allergen-restrictions", { allergen_id: allergenId }),
  removeAllergenRestriction: (allergenId) => del(`/allergen-restrictions/${allergenId}`),

  // System log
  listSystemLog: (params) => {
    const q = new URLSearchParams(params || {}).toString();
    return get(`/system-log${q ? `?${q}` : ""}`);
  },
  markCorrected: (id) => patch(`/system-log/${id}/mark-corrected`),

  // Notifications
  testNotification: (message) => post("/notifications/test", { message }),

  // Shopping list
  listShoppingList: () => get("/shopping-list"),
  addShoppingListItem: (body) => post("/shopping-list", body),
  removeShoppingListItem: (id) => del(`/shopping-list/${id}`),

  // Ingredients (for shopping list / display names)
  getIngredient: (id) => get(`/ingredients/${id}`),
};
