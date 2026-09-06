"""Tool definitions and dispatcher for the voice/tool-calling layer
(kitchen_ai_spec.md §12). A curated v1 set covering every example voice
command the spec actually describes -- not all 59+ endpoints at once,
since dumping the whole API into one tool list hurts selection
reliability more than it helps. Easy to extend once this proves out.

Tools call the backend's own REST API internally (loopback HTTP) rather
than duplicating business logic in a second code path -- reuses every
validation rule and error response already built and tested, at the
cost of a negligible in-process HTTP round-trip.
"""

import os

import httpx

BACKEND_BASE_URL = os.environ.get("BACKEND_INTERNAL_URL", "http://localhost:8000")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_recipes",
            "description": "Lists all known recipes with their id, name, and basic timing info.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recipe",
            "description": "Gets full detail for one recipe (ingredients, instructions, servings) by its id.",
            "parameters": {
                "type": "object",
                "properties": {"recipe_id": {"type": "integer"}},
                "required": ["recipe_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Gets recipe recommendations split into full-stock (cookable right now) and shopping-required tiers, based on current inventory, allergens, and cookware.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_minutes": {
                        "type": "integer",
                        "description": "Optional time budget (prep+active minutes) to filter recipes by.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_cooking_session",
            "description": "Starts a cooking session for a recipe, given its recipe id. Only one session can be active at a time; fails if one already is.",
            "parameters": {
                "type": "object",
                "properties": {"recipe_id": {"type": "integer"}},
                "required": ["recipe_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_session",
            "description": "Gets the currently active cooking session, if any, including its live ingredient list and macros.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_ingredient_delta",
            "description": "Adjusts one ingredient's quantity in the active session by a signed amount relative to its current quantity (e.g. '2g more garlic' -> amount=2, 'less' -> negative). This-time-only by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "recipe_ingredient_id": {"type": "integer"},
                    "amount": {"type": "number", "description": "Signed delta, negative for 'less'/'fewer'."},
                },
                "required": ["session_id", "recipe_ingredient_id", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_ingredient_absolute",
            "description": "Sets one ingredient's quantity in the active session to an exact amount (e.g. 'set chicken to 180g'). This-time-only by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "recipe_ingredient_id": {"type": "integer"},
                    "quantity": {"type": "number"},
                },
                "required": ["session_id", "recipe_ingredient_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scale_recipe",
            "description": "Proportionally scales the active session's recipe. Provide either target_servings (scales quantities and servings together), or target_recipe_ingredient_id + target_quantity + more_servings (more_servings distinguishes 'still one meal, bigger cut' from 'this makes more servings' -- ask the user which if not stated).",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "target_servings": {"type": "number"},
                    "target_recipe_ingredient_id": {"type": "integer"},
                    "target_quantity": {"type": "number"},
                    "more_servings": {"type": "boolean"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_cooking",
            "description": "The compound 'finished cooking' command. mode=deduct_and_eaten deducts inventory AND logs it eaten (percent_eaten defaults to 100 if not stated); mode=deduct_only deducts inventory and leaves it as a pending batch to eat/dispose later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "integer"},
                    "mode": {"type": "string", "enum": ["deduct_and_eaten", "deduct_only"]},
                    "percent_eaten": {"type": "number", "description": "0-100, defaults to 100."},
                },
                "required": ["session_id", "mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_session_without_deducting",
            "description": "Ends the active cooking session without deducting inventory or logging anything eaten (e.g. the user changed their mind).",
            "parameters": {
                "type": "object",
                "properties": {"session_id": {"type": "integer"}},
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pending_meal_prep_batches",
            "description": "Lists meal-prep batches that haven't been fully eaten or disposed yet. Use this to find which batch the user means before calling eat_meal_prep_batch/dispose_meal_prep_batch if more than one is active -- ask which one rather than guessing.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "eat_meal_prep_batch",
            "description": "Logs eating a percentage of a pending meal-prep batch (e.g. 'I ate 60% of it' -> percent=60). Defaults to 100 if the user just says they ate it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "batch_id": {"type": "integer"},
                    "percent": {"type": "number"},
                },
                "required": ["batch_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dispose_meal_prep_batch",
            "description": "Marks a percentage of a pending meal-prep batch as thrown out/given away -- NOT eaten, no calories logged.",
            "parameters": {
                "type": "object",
                "properties": {
                    "batch_id": {"type": "integer"},
                    "percent": {"type": "number"},
                },
                "required": ["batch_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_meal_estimate",
            "description": "Logs an ad-hoc food item with no known ingredient match as a rough estimate (e.g. 'I had a banana'). No permanent ingredient record is created.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fat_g": {"type": "number"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_shopping_list_item",
            "description": "Adds an item to the shopping list. Provide either category_id or ingredient_id, plus the quantity needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category_id": {"type": "integer"},
                    "ingredient_id": {"type": "integer"},
                    "quantity_needed": {"type": "number"},
                },
                "required": ["quantity_needed"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_weigh_in",
            "description": "Logs today's body weight (in pounds).",
            "parameters": {
                "type": "object",
                "properties": {"weight": {"type": "number"}},
                "required": ["weight"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_ingredient_by_barcode",
            "description": "Looks up whether a scanned barcode matches a known ingredient/product.",
            "parameters": {
                "type": "object",
                "properties": {"upc": {"type": "string"}},
                "required": ["upc"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_inventory_item",
            "description": "Adds a quantity of a known ingredient to inventory (e.g. after a grocery haul). ingredient_id must already exist -- use lookup_ingredient_by_barcode first for a new product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredient_id": {"type": "integer"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string", "description": "A unit code, e.g. g, kg, oz, lb, ml, l, tsp, tbsp, cup, fl_oz, count."},
                    "expiration_date": {"type": "string", "description": "YYYY-MM-DD, optional."},
                },
                "required": ["ingredient_id", "quantity", "unit"],
            },
        },
    },
]


def _safe_json(response: httpx.Response):
    try:
        return response.json()
    except ValueError:
        return response.text


async def dispatch_tool_call(name: str, arguments: dict) -> dict:
    async with httpx.AsyncClient(base_url=BACKEND_BASE_URL, timeout=30.0) as client:
        if name == "list_recipes":
            resp = await client.get("/recipes")
        elif name == "get_recipe":
            resp = await client.get(f"/recipes/{arguments['recipe_id']}")
        elif name == "get_recommendations":
            params = {"max_minutes": arguments["max_minutes"]} if "max_minutes" in arguments else {}
            resp = await client.get("/recommendations", params=params)
        elif name == "start_cooking_session":
            resp = await client.post("/sessions/start", json={"recipe_id": arguments["recipe_id"]})
        elif name == "get_active_session":
            resp = await client.get("/sessions/active")
        elif name == "adjust_ingredient_delta":
            resp = await client.patch(
                f"/sessions/{arguments['session_id']}/ingredients/{arguments['recipe_ingredient_id']}/delta",
                json={"amount": arguments["amount"]},
            )
        elif name == "set_ingredient_absolute":
            resp = await client.patch(
                f"/sessions/{arguments['session_id']}/ingredients/{arguments['recipe_ingredient_id']}/absolute",
                json={"quantity": arguments["quantity"]},
            )
        elif name == "scale_recipe":
            body = {k: v for k, v in arguments.items() if k != "session_id"}
            resp = await client.post(f"/sessions/{arguments['session_id']}/scale", json=body)
        elif name == "finish_cooking":
            body = {"mode": arguments["mode"], "percent_eaten": arguments.get("percent_eaten", 100)}
            resp = await client.post(f"/sessions/{arguments['session_id']}/finish-cooking", json=body)
        elif name == "end_session_without_deducting":
            resp = await client.post(f"/sessions/{arguments['session_id']}/finish")
        elif name == "list_pending_meal_prep_batches":
            resp = await client.get("/meal-prep-batches", params={"pending_only": True})
        elif name == "eat_meal_prep_batch":
            resp = await client.post(
                f"/meal-prep-batches/{arguments['batch_id']}/eat",
                json={"percent": arguments.get("percent", 100)},
            )
        elif name == "dispose_meal_prep_batch":
            resp = await client.post(
                f"/meal-prep-batches/{arguments['batch_id']}/dispose",
                json={"percent": arguments.get("percent", 100)},
            )
        elif name == "log_meal_estimate":
            resp = await client.post("/meal-log/estimate", json=arguments)
        elif name == "add_shopping_list_item":
            resp = await client.post("/shopping-list", json=arguments)
        elif name == "log_weigh_in":
            from datetime import date

            resp = await client.post(
                "/weigh-ins", json={"date": date.today().isoformat(), "weight": arguments["weight"]}
            )
        elif name == "lookup_ingredient_by_barcode":
            resp = await client.get(f"/ingredients/barcode/{arguments['upc']}")
        elif name == "add_inventory_item":
            resp = await client.post("/inventory", json=arguments)
        else:
            return {"error": f"unknown tool: {name}"}

    return {"status_code": resp.status_code, "body": _safe_json(resp)}
