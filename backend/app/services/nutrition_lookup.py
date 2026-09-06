"""External nutrition/barcode lookups (kitchen_ai_spec.md §4). Two sources,
each good at what the other isn't:
  - Open Food Facts: free, no key required, a huge global barcode database
    of packaged/branded products -- the right source for "scan this box".
  - USDA FoodData Central: the actual large nutrition database, strongest
    for raw/generic ingredients (chicken breast, white rice) that a barcode
    database has no reason to carry -- used for name search, not barcodes.
Both are best-effort: any failure (network, no match, rate limit) returns
None/[] rather than raising, so the caller always has a manual-entry
fallback instead of a hard error.
"""

import os

import httpx

USDA_FDC_API_KEY = os.environ.get("USDA_FDC_API_KEY", "DEMO_KEY")

OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product/{upc}.json"
USDA_FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"


def _nutrient(nutriments: dict, *keys: str) -> float | None:
    for key in keys:
        value = nutriments.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


async def lookup_barcode_external(upc: str) -> dict | None:
    """Open Food Facts lookup by UPC/EAN. Returns per-100g macros plus a
    suggested name, or None if there's no match / OFF is unreachable."""
    url = OPEN_FOOD_FACTS_URL.format(upc=upc)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params={"fields": "product_name,brands,nutriments"})
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return None

    if data.get("status") != 1:
        return None

    product = data.get("product", {})
    name = product.get("product_name") or product.get("brands")
    if not name:
        return None

    nutriments = product.get("nutriments", {})
    calories = _nutrient(nutriments, "energy-kcal_100g", "energy-kcal")
    if calories is None:
        kj = _nutrient(nutriments, "energy_100g", "energy")
        calories = kj / 4.184 if kj is not None else None
    sodium_g = _nutrient(nutriments, "sodium_100g")

    return {
        "name": name,
        "upc_barcode": upc,
        "source": "Open Food Facts",
        "serving_size": 100,
        "serving_size_unit": "g",
        "calories": calories,
        "protein_g": _nutrient(nutriments, "proteins_100g"),
        "carbs_g": _nutrient(nutriments, "carbohydrates_100g"),
        "fat_g": _nutrient(nutriments, "fat_100g"),
        "saturated_fat_g": _nutrient(nutriments, "saturated-fat_100g"),
        "sugars_g": _nutrient(nutriments, "sugars_100g"),
        "fiber_g": _nutrient(nutriments, "fiber_100g"),
        "sodium_mg": sodium_g * 1000 if sodium_g is not None else None,
    }


async def search_nutrition_by_name(query: str, limit: int = 5) -> list[dict]:
    """USDA FoodData Central search by name -- the large nutrition database,
    strongest for raw/generic ingredients a barcode lookup won't cover.
    Returns candidate per-100g macro sets for the user to pick from; none
    of these are persisted here."""
    params = {
        "api_key": USDA_FDC_API_KEY,
        "query": query,
        "pageSize": limit,
        "dataType": ["Foundation", "SR Legacy", "Branded"],
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(USDA_FDC_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError:
        return []

    candidates = []
    for food in data.get("foods", [])[:limit]:
        name = food.get("description")
        if not name:
            continue
        nutrients = {n.get("nutrientName"): n.get("value") for n in food.get("foodNutrients", [])}
        candidates.append(
            {
                "name": name.title(),
                "source": f"USDA FoodData Central ({food.get('dataType', 'unknown')})",
                "serving_size": 100,
                "serving_size_unit": "g",
                "calories": nutrients.get("Energy"),
                "protein_g": nutrients.get("Protein"),
                "carbs_g": nutrients.get("Carbohydrate, by difference"),
                "fat_g": nutrients.get("Total lipid (fat)"),
                "fiber_g": nutrients.get("Fiber, total dietary"),
                "sugars_g": nutrients.get("Sugars, total including NLEA") or nutrients.get("Sugars, total"),
                "sodium_mg": nutrients.get("Sodium, Na"),
                "saturated_fat_g": nutrients.get("Fatty acids, total saturated"),
            }
        )
    return candidates
