# Kitchen AI — Design Spec

Living reference document. Captures architecture, schema, and behavioral rules decided during planning. Update this as decisions change rather than re-deriving them from memory.

## Guiding principle — assumption model

Not a uniform "always ask." Split into two tiers by **consequence**, not by how the request happened to be phrased:

- **Assume-and-announce** (state what was done, correctable after the fact) for anything cheap/reversible:
  - permanent-vs-this-time-only edits default to **this-time-only**
  - a new barcode's category is **guessed from the label**
  - ambiguous absolute-vs-scale phrasing defaults to the **narrower single-ingredient interpretation**
  - high-confidence fuzzy food/recipe matches **auto-match**

  Every case above is stated plainly to the user, never applied silently.

- **Ask-first, no default** for anything where a wrong guess would silently corrupt tracking data rather than produce an obviously-wrong, easily-noticed result: which meal-prep batch (multiple active), which specific product (multiple in stock with different macros), meal-prep eaten-vs-disposed.

- **Explicit direct commands** always carry their own stated default and are never blocked on a question — e.g. "I'm finished cooking" defaults to 100% of the recipe eaten, stated plainly, correctable after the fact. This differs from the same situation reached passively/ambiguously, which still asks — the distinction is a live direct instruction vs. an inferred guess.

- **Per-behavior settings toggle**: every assume-vs-ask behavior above is individually exposed on a settings page (assume+announce vs. always-ask), not hardcoded. Defaults follow the reversible/silent-corruption line above; adjustable per behavior as real usage reveals which defaults work (`behavior_settings` table, §3).

New shortcuts beyond what's listed above only get added later, after real friction is felt with a specific case — never assumed in advance because it "seems obvious."

---

## 1. Architecture

- **Backend**: custom app (Python/FastAPI or similar) on the user's own AI server (RTX 4000 Ada, RTX 4000 Blackwell, Arc Pro B70, EPYC 7443P, 80GB ECC RAM). Postgres for storage — containerized via Docker; see §2 for the deployment plan and the Postgres-vs-SQLite rationale.
- **Not using Home Assistant as the backbone** — the system is relational/computational (joins, live macro math, scaling, calibration loops), not entity/state-based like HA's model. HA is now in the stack as a **voice front-end** for the purchased hardware (below), but the kitchen-AI backend and its database remain independent of it.
- **iPad**: web app (PWA, "Add to Home Screen"), not a native app. Lowest effort, cross-device if needed later.
- **Access**: local network only. No auth/HTTPS/exposure hardening built in. Remote access via Tailscale when needed, not port-forwarding.
- **Voice**: 3x **Home Assistant Voice Preview Edition** purchased (kitchen, office, bedroom) — one shared Home Assistant instance for all three units, not one HA install per device. HA instance hosting location (lightweight VM/container on the existing AI server, vs. a separate small box for independence from server reboots) not yet decided — see §14.
  - **Office and bedroom units**: standard HA area assignment, native Assist pipeline handling — ordinary smart-home use, no custom work needed.
  - **Kitchen unit**: needs a device-scoped HA automation that intercepts its commands *before* HA's own Assist/conversation agent handles them, forwards the transcript to the kitchen-AI backend via webhook, and routes the response back to that unit's speaker. Scoped tightly to the kitchen device/area specifically — never applied globally, so office/bedroom commands can't accidentally route to the kitchen backend.
  - Devices ship with ESPHome firmware assuming HA + the Wyoming protocol; this is why the translation-layer automation was chosen over reflashing custom firmware — it keeps the other two units free for genuine HA/smart-home use.
  - **iPad push-to-talk button** remains the backup path (e.g. a mic issue on the kitchen unit), also usable anytime.
  - Whichever channel is used to speak, that channel gives the spoken response back (including clarifying/confirmation questions). The iPad is otherwise a **pure live display** — visual state (macros, recipe, quantities) updates in real time regardless of which device triggered the change, no interaction required on the iPad to see it reflected.
- **Session state**: one canonical "current session" on the backend (active recipe, in-progress edits, elapsed time). All devices read/write to it; changes push to the iPad rather than requiring polling. Session start/end is **explicit and voice-triggered**, not implicit — see §7 for the full cooking-session lifecycle and how it gates the deduction-reminder logic.
- **Command routing**: transcript from either voice path (or push-to-talk) goes to the main LLM with tool-calling access into the backend (inventory, recipes, macros, shopping list, etc.) rather than a rigid intent classifier — handles open-ended phrasing without enumerating every command pattern in advance. **Compound/multi-clause commands are first-class, not an edge case**: one utterance can map to multiple sequential tool calls (e.g. "deduct the ingredients and count as eaten"), with all outcomes reported back together. Reliability notes for this are tracked separately — see §12. This LLM runs locally via `llama.cpp` — see §2.

---

## 2. Deployment (Docker)

**Why Postgres, not SQLite**: this system has multiple concurrent writers hitting the same database — the voice satellite, iPad push-to-talk, and a live remaining-budget recompute that fires on every `meal_log` write (§8) — plus joins for live macro computation (§3) across ingredients/recipes/inventory. That's real concurrent relational load, not an embedded single-process tool, and it's exactly the pattern SQLite's single-writer lock handles poorly (contention/`SQLITE_BUSY`, even with WAL mode). Postgres also gives proper `NUMERIC` types for macros and `JSONB` for the flexible micronutrient tail (§3), and drops cleanly into Compose as its own service with a persistent volume. Staying with Postgres.

**Postgres runs standalone, not as a Compose service.** It's set up as its own Unraid Community Applications container (`postgres:18`) — matches how the existing paperless-ai Postgres (v14) is already run on this box, and gives it independent updates/lifecycle from the app stack rather than being coupled to `backend` rebuilds. Published on host port **5433** (paperless-ai's Postgres already holds 5432). `backend` connects to it over the LAN via `DATABASE_URL` in `.env` (the Unraid host's IP/hostname, port 5433) — not Compose-internal DNS, since it's outside this project's network.
- Container path is mounted at `/var/lib/postgresql` (the parent directory, **not** `/var/lib/postgresql/data`) — this is the correct fix for Postgres 18's data-directory change (18 moved its default `PGDATA` to a version-specific subpath, `/var/lib/postgresql/18/docker`; mounting the parent dir instead of the old specific subpath means the volume covers it either way, no separate `PGDATA` override needed).
- `POSTGRES_USER` set to `kitchenai` (not left at the `postgres` superuser default) to match the app's connection string; `POSTGRES_DB` also `kitchenai`.

**The tool-calling LLM also runs standalone, not as a Compose service** — same reasoning as Postgres. It's `ghcr.io/ggml-org/llama.cpp:server-vulkan`, run as its own Unraid CA container, published on host port **8081**, GPU-passthrough'd to the **Arc Pro B70** via `--device=/dev/dri:/dev/dri` in the container's Extra Parameters (needs the **Intel-GPU** Unraid plugin, community ich777, installed at the OS level first — same category as the Nvidia-Driver plugin, just for Arc).
- **Why Arc over the NVIDIA cards for this**: initially assumed NVIDIA-primary with Arc deferred as immature (Ollama's Docker GPU story is NVIDIA-first), but reported benchmarks don't support treating Arc as the weaker option here — the B70 has more VRAM (32GB vs. the Blackwell's 24GB) and wins meaningfully on concurrent-request throughput, though the Blackwell is faster on single-request generation (~11-25% depending on model size) while the B70 has roughly half the time-to-first-token. For a single-user voice assistant doing short, frequent tool-calling round-trips, low TTFT plausibly matters more than steady-state tok/s. Starting here to validate the Vulkan/GPU-passthrough pipeline works at all; tensor-parallel across the two NVIDIA cards together (Ada 20GB + Blackwell 24GB = 44GB combined, mature same-vendor multi-GPU tooling) remains a candidate to try and compare against, not a settled decision.
- The template expects an actual `model.gguf` file at its mounted model path (`/mnt/apps/appdata/llama_cpp/model` → container `/models`), not a `-hf` auto-pull — download a GGUF manually and place/rename it there.
- Model choice needs tool/function-calling support and enough context for a session's recipe + inventory state — benchmark plan, not yet committed, see §12/§14. Currently running Qwen3-8B (`bartowski/Qwen_Qwen3-8B-GGUF`, Q4_K_M) purely to validate the pipeline (GPU passthrough, Vulkan detection) before committing to a larger/benchmarked choice.

**Compose services** (`backend` only — Postgres and the LLM both run standalone, above):
- **`backend`** — the FastAPI app, built from a local Dockerfile. Talks to Postgres and to the llama.cpp server over the LAN via env vars in `.env`, not Compose-internal DNS, since both are outside this project's network.
- `backend`'s API/web port is published to the LAN (for the iPad PWA and the satellite device) on host **8001** — not 8000, which PortainerCE already holds on this box.
- **Remote access**: Tailscale runs on the Docker host itself, not as a container — it reaches any published port (backend's 8001, Postgres's 5433, llama.cpp's 8081) like any other LAN service, so no sidecar/ACL setup is needed for v1.
- **Backups**: scheduled `pg_dump` (never raw live DB file copies — risk of mid-write corruption) synced to the existing storage array, covered by the array's own parity. No off-site/second-location backup for v1 — accepted given array redundancy and this data being lower-priority than other things on the server.

**Unraid-specific notes** (the actual deployment target):
- Postgres and llama.cpp both have ready-made Community Applications (CA) templates and run standalone. `backend` is custom code — not something CA has; it needs its own `Dockerfile`, built into an image and run as the one service in the Compose stack.
- Cleanest path for `backend`: the **Docker Compose Manager** CA plugin, which takes `docker-compose.yml` pasted into the Unraid UI, rather than wiring up a Docker template by hand for custom code.
- **GPU passthrough is not automatic on Unraid** — a plugin has to be installed at the OS level before any container can see a GPU: **Nvidia-Driver** for the NVIDIA cards, **Intel-GPU** for the Arc card (both community, ich777).
- Persistent volumes (llama.cpp's model file; Postgres's own data dir) live under `/mnt/apps/appdata/<container>/` — this box keeps Docker appdata on its own dedicated pool named `apps`, not Unraid's usual default `/mnt/user/appdata/`.
- **Port allocations on this box are dense** (arr-stack, paperless-net, and others already claim a wide range) — always check the existing allocation list before picking a new host port rather than assuming a default is free.

**Source control**: `backend` lives in its own GitHub repo (private — no secrets committed either way; DB password/any API keys go in a `.gitignore`d `.env` consumed via Compose's `env_file`). Update flow for v1: repo cloned onto the Unraid box, `git pull && docker compose up -d --build` picks up changes — no CI needed for a single-user project. Revisit a GitHub Actions build → `ghcr.io` image → Compose `pull` flow later if building on the Unraid box itself becomes annoying; premature for now.

---

## 3. Database schema

### Core reference data
- **`ingredients`** — canonical nutrition reference AND product catalog in one table (no separate "nutrition facts" table). Fields: `id`, `name`, `upc_barcode` (nullable — packaged items only), `category_id` (FK to `ingredient_categories`), fixed macro columns (`calories`, `protein_g`, `carbs_g`, `fat_g`, `serving_size`, `serving_size_unit` — canonical unit the macro columns are measured per, `g` or `ml`, defaulting to `g`, plus the standard label fields: saturated fat, sodium, fiber, sugars, etc.), a flexible field for the variable micronutrient tail (vitamins/minerals — not fixed columns, since not every product lists the same set), `ingredients_list_raw` (full text of the label's ingredient statement, for "what's in this" queries), `source` (barcode scan / USDA import / chain-menu import / user-confirmed / estimate), `density_g_per_ml` (nullable — volume↔weight bridge specific to this product, see §5), `unit_weight_g` + `unit_label` (nullable pair — weight of one discrete unit of this product, e.g. `unit_label='slice'`, `unit_weight_g=28`, see §5).
- **`ingredient_categories`** — the generic concept ("hamburger bun," "chicken breast," "cheddar cheese"). Recipes reference this, not a specific product. `ingredients.category_id` links each specific product to its generic category.
- **`units`** — small fixed reference table of accepted units: `code` (`g`, `kg`, `oz`, `lb`, `ml`, `l`, `tsp`, `tbsp`, `cup`, `fl_oz`, `count`), `type` (`mass` / `volume` / `count`), `to_canonical_factor` (multiplier to grams for mass units, to ml for volume units; unused for `count`, which is always resolved per-ingredient via `unit_weight_g`). Canonical storage unit is **grams for mass, ml for volume** — see §5.
- **`allergens`** — small fixed list (FDA major nine + anything else the user cares about).
- **`ingredient_allergens`** — join table, populated from the label's "Contains" statement during ingestion.
- **`inventory`** — what's physically on hand. `id`, `ingredient_id` (FK), `quantity`, `unit`, `expiration_date`, `location`. Multiple rows can share an `ingredient_id` (e.g. two milk cartons with different expiration dates).
- **`cookware`** — `id`, `name`, `type`, `tare_weight` (empty weight, weighed once at setup), `label_number` (physical engraved ID — handle/unexposed area, never the cooking surface). Enables "how much food is in pot 3" → read live scale weight, subtract that item's stored `tare_weight`, no re-weighing empty cookware each use. Ambiguous "the pot" with more than one plausible candidate in session context → ask-first (wrong guess here silently mislabels tracked food).

### Behavior & logging
- **`behavior_settings`** — one row per toggle-able assume/ask behavior (e.g. `permanent_vs_temporary_edit`, `barcode_category_guess`, `absolute_vs_scale_ambiguity`, `fuzzy_match_autoconfirm`, `recipe_downscale_suggestion`, ...), `mode` (`assume_and_announce` / `always_ask`). Defaults seeded per the reversible/corruption line in the Guiding Principle; user-adjustable per behavior over time.
- **`system_log`** (a.k.a. `assumption_log`) — separate from `activity_log` (Garmin data). **Build this in Phase 1**, before most feature work — real assumption data should exist from the very first barcode scan onward. Two modes:
  - **Regular** (default on): one row per assumption/ambiguous action — `id`, `timestamp`, plain-language `description`, `trigger` (what prompted it), `corrected` (bool — whether the user later overrode it), `behavior_key` (which `behavior_settings` toggle governed this decision, so a pattern of frequent corrections points directly at which default to reconsider). Structured (consistent schema / JSON lines), not free text, so it can be parsed and reviewed systematically — including bulk-uploading it to Claude for pattern review.
  - **Debug** (off by default, toggle on for troubleshooting): full technical trace per interaction — raw transcript, parsed intent, confidence scores, DB reads/writes, before/after values, session-state snapshots.

### Recipes
- **`recipes`** — `id`, `name`, `instructions`, `base_servings`, `prep_minutes`, `active_minutes`, `passive_minutes`. Macros are never stored directly — always computed live from the ingredient join, so substitutions and edits recalculate automatically with no caching to keep in sync.
- **`recipe_ingredients`** — join table, `recipe_id`, **`category_id`** (generic, not a specific `ingredient_id` — resolved to a specific product at cook time), `quantity`, `unit`.
- **`recipe_cookware`** — `recipe_id`, `cookware_id`, `required` (bool).
- **`recipe_versions`** — `id`, `recipe_id`, `version_number`, `changed_at`, full snapshot (not a diff) of ingredients + instructions at that point. A permanent edit writes the pre-change snapshot here before mutating the live recipe. Reverting restores an old snapshot as current and logs the revert as a new version entry (history never has silent gaps).
- **`cooking_sessions`** — the "one canonical current session" §1 describes conceptually but never gave a concrete table. `id`, `recipe_id`, `status` (`active`/`finished`), `started_at`, `ended_at`, `ingredient_overrides` (JSONB, sparse `{recipe_ingredient_id: quantity}` map for this-time-only edits, §6), `servings_override`. A partial unique index allows at most one `active` row at a time, matching the single-session model.

### Shopping & meal prep
- **`shopping_list`** — `id`, `ingredient_id` (or category — TBD at build time), `quantity_needed`, `date_added`. No status field — added only on explicit "yes," removed only when the corresponding purchase is logged during a post-haul inventory pass (barcode scan matching an item on the list clears it automatically).
- **`meal_prep_batches`** — `id`, `recipe_id`, `description`, `date_prepared`, `units_total`, `units_remaining` (**decimal**, not integer — see partial consumption below), and macros **per unit, snapshotted at prep time** (reflects any this-time-only session edits active when it was cooked, not the base recipe).
  - **Cooked-but-not-yet-eaten (pending)**: "I'm done cooking, deduct the ingredients" (no "count as eaten") deducts inventory and creates a batch with `units_total = 1`, `units_remaining = 1` — cooked and pending, nothing logged as eaten yet. A later "I ate it all, mark as eaten" resolves to that pending batch — **ask-first if more than one pending batch is active** (wrong guess would misattribute macros to the wrong meal) — then decrements to 0 and writes the `meal_log` entry from the snapshot.
  - **Partial consumption**: "I ate 60%, rest in the fridge" → `meal_log` entry for `0.6 × per-unit macros`, `units_remaining` drops to `0.4`. Chains correctly across repeated partial-consumption sessions (each is a further subtraction from whatever decimal remains).
  - **Eating a unit**: decrement `units_remaining`, write a `meal_log` entry from the snapshotted per-unit macros. **Disposing** (thrown out / given away): decrement `units_remaining`, **no** `meal_log` entry. Distinguishing eaten-vs-disposed is **ask-first, no default** — a wrong guess here silently corrupts intake tracking.
  - **Compound command handling**: "I'm finished cooking, deduct the ingredients and count as eaten" parses as two separate actions (deduct inventory; log as eaten) chained from one utterance — the underlying tool calls stay atomic/separable rather than one welded operation, since a "deduct only" command needs the same deduction logic without the eaten side. See §12.
  - **Recipe auto-downscale suggestion**: tracks eaten-percentage per `recipe_id` across sessions where a batch wasn't fully consumed as-cooked. A consistent pattern (e.g. the last 3–4 times landing in a similar range) triggers a suggestion to permanently scale the recipe down to match actual consumption — reuses the existing proportional-scale mechanism (§6), written as a new `recipe_versions` snapshot. Its own `behavior_settings` toggle — some users won't want the proactive suggestion.

### Tracking
- **`meal_log`** — one row per thing eaten. `id`, `timestamp`, `recipe_id` / `meal_prep_batch_id` / `ingredient_id` (whichever applies, nullable), `quantity`, `description` (nullable — what an ad-hoc estimate actually was, when there's no `recipe_id`/`meal_prep_batch_id`/`ingredient_id` to derive that from; found missing from the original field list while building meal logging), and macros **snapshotted at log time** (editing a recipe later doesn't retroactively change past logged meals). `is_estimate` (bool) — see Section 7 for the toggle behavior. All fields editable after the fact on the iPad.
- **`planned_meals`** — same-day only, cleared at day boundary regardless of fulfillment. `meal_slot`, `description`, `estimated_calories/protein/carbs/fat`. Used for declared-but-not-yet-eaten intent (e.g. "pizza for dinner tonight") so remaining-budget math and other-meal recommendations account for it. Logging the actual meal for that slot converts/replaces the planned entry rather than double-counting.
- **`weigh_ins`** — `id`, `date`, `weight`.
- **`activity_log`** — `id`, `date`, exercise data (see Garmin integration, Section 9).
- **`user_goals`** — history, not a single overwritable row (`effective_date`-keyed) so past projections stay accurate to the goal active at the time. Fields: `goal_type` (label only), `target_deficit_surplus` (signed kcal/day), `protein_g`/`fat_g`/`carbs_g` (or protein/fat fixed + carbs fill remainder), `goal_weight`, `target_date`.
  - **Deficit/date solver**: `total_calories_needed = (current_weight − goal_weight) × 3500` (or 7700/kg). Whichever of `target_date` / `target_deficit_surplus` was most recently edited is treated as the fixed input; the other recalculates. `goal_weight` is the anchor and doesn't auto-recalculate on its own edit (minor UX detail, not fully settled).
  - **TDEE personal calibration**: predicted weight change (from BMR formula + logged intake + logged exercise burn) is compared weekly against actual weigh-in trend (smoothed, not single readings). Persistent gaps become a rolling personal correction factor applied to future projections. Needs 3–4 weeks of paired data before applying — flag confidence level ("still calibrating" vs. "adjusted based on N weeks") rather than applying corrections off noisy early data.
- **`recommendation_settings`** — single current-state row (not history — reflects current priorities only). Slider values for: calorie-deficit adherence, protein adherence, carb adherence, fat adherence, diversity, expiration urgency. Defaults given current context: calorie and protein high, carb/fat low, diversity moderate, expiration moderate. Also holds `enabled_meal_slots`, `typical_delivery_lead_hours`, `ingredient_coverage_threshold` (all named as settings in §8 but missing from this table's field list until the recommendation engine was actually built).
- **`user_allergen_restrictions`** — `allergen_id` (FK to `allergens`). The "permanent default" restriction set §8's hard filters assume exists; missing from this schema entirely until the recommendation engine needed it. Session-declared exclusions (the "just for tonight" case) still need the session-state infrastructure that doesn't exist yet, §14.

---

## 4. Ingredient resolution (generic ↔ specific)

Recipes call for generic categories ("2 hamburger buns"); inventory holds specific products. Resolution happens at cook/recommendation time, not recipe-authoring time:

- **Exactly one matching product in stock** → auto-selected, no question. Macros come from that specific product's real data.
- **Zero in stock** → feeds the shopping-list-suggestion flow.
- **Two or more distinct products in stock** → ask which one (ask-first tier — voice or iPad, whichever channel is active).

**New product ingestion (barcode scan):**
1. Scan barcode → matched in `ingredients`? → prompt for quantity + expiration → added to inventory.
2. Not matched → scan the nutrition facts label (+ ingredients list + allergen "Contains" line) → vision/OCR extraction → new `ingredients` row created (barcode saved for future instant matches). OCR also parses `density_g_per_ml`/`unit_weight_g` from the label's serving size when possible — see §5.
3. **Category assignment for a brand-new product**: guessed from the label (assume-and-announce tier), stated to the user, correctable — no blocking question.

**Recipe seeding**: batch-created via a separate AI (Claude) using a reusable prompt template (see Section 13) that outputs recipes as JSON referencing *generic* categories, not brands — kept standard/generic, not tailored to any specific macro goal (goal-fitting happens at recommendation time, not baked into seed data). Local system resolves category names against existing `ingredient_categories` on import, flagging low-confidence matches for confirmation rather than silently creating near-duplicates.

---

## 5. Unit conversion (grams & ml canonical)

Two independent tiers — only the second needs per-ingredient data:

- **Tier 1 — universal (`units` table, hardcoded, no ingredient lookup)**: mass↔mass (`g`/`kg`/`oz`/`lb`) and volume↔volume (`ml`/`l`/`tsp`/`tbsp`/`cup`/`fl_oz`) each reduce through their own canonical unit via fixed physical constants. Always available, never ambiguous, never asked about.
- **Tier 2 — ingredient-specific bridge** (`ingredients.density_g_per_ml`, `ingredients.unit_weight_g`/`unit_label`): needed only when a quantity crosses *between* volume and mass (a recipe or label giving "1 cup," "2 tbsp" for something tracked by weight) or from a discrete count to mass ("1 slice," "1 clove," "1 bun"). Density and unit-weight vary per product, so this data lives on the specific `ingredients` row, not the generic category — consistent with resolution happening at cook time (§4), not authoring time.

**Populating Tier 2 automatically at ingestion**: many nutrition labels already state serving size in both a household measure and a weight (e.g. "2 tbsp (32 g)," "1 slice (28 g)"). The OCR extraction step (§4 step 2) parses both halves when present and derives `density_g_per_ml` or `unit_weight_g` directly — no user prompt needed. Only when the label gives just one form (e.g. "30 g" alone, or "1 cup" with no weight given) does the system fall back to asking once, per the standing ask-first principle; the answer is cached permanently on that `ingredients` row, so it's asked at most once per product.

**Resolution flow for any incoming quantity + unit** (recipe authoring, ad-hoc log entry, inventory add):
1. Unit already canonical for its type (`g` or `ml`) → store directly, no conversion.
2. Unit is same-type, non-canonical (`kg`, `oz`, `lb`, `tsp`, `tbsp`, `cup`, `fl_oz`, `l`) → Tier 1 conversion, always succeeds, never asked about.
3. Unit crosses type (volume for a mass-tracked ingredient, or a `count` unit) → Tier 2 lookup on the *resolved specific* ingredient. Present → converts silently. Missing → ask once, then backfill onto that `ingredients` row.
4. `recipe_ingredients` rows (category-level, pre-resolution) keep the author's original quantity + unit as written — no canonical conversion happens until a specific product is resolved at cook time (§4), since Tier 2 data doesn't exist at the category level yet.

**Display**: canonical g/ml is what macros, joins, and scaling math run on internally; voice/iPad output still echoes back in whatever unit the user spoke in (or the recipe's original unit) wherever practical — conversion happens at the display edge, not by surfacing raw grams for everything.

---

## 6. Recipe modification & scaling

Command-parsed edits always go to a **session-scoped copy** first; nothing touches the saved recipe until explicitly confirmed or defaulted.

- **After any modification** (ingredient tweak, scale, substitution): iPad updates live, and the change defaults to **this-time-only** (assume-and-announce tier), stated plainly, correctable to permanent afterward — no blocking question. A "permanent" confirmation, whenever it happens, writes a new `recipe_versions` snapshot before mutating the live recipe.
- **Delta edits** ("2g more/less garlic"): `more`/`less`/`extra`/`fewer` = signed delta against the recipe's *current* (possibly already session-modified) quantity for that one ingredient only. If amount is unspecified ("more garlic," no number), ask how much before applying.
- **Absolute edits** ("change/set/use chicken to 180g"): overwrites that one ingredient's quantity only. Nothing else in the recipe moves.
- **Proportional scale** ("scale this recipe to 200g chicken," or by target servings): `scale_factor = target ÷ current`, applied to every ingredient. Triggers a required follow-up question: **"is this still one meal, or does this make more servings?"** (ask-first — this genuinely can't be inferred, not a candidate for a default).
  - *Still one meal* (e.g. cut of meat is naturally larger than the recipe calls for): all quantities scale, `servings` stays fixed — the whole batch counts as one meal.
  - *More servings* (meal prep / feeding more people): quantities and `servings` scale together, per-serving macros land near the original intent.
- **Ambiguous phrasing** (e.g. "make the chicken 200g" with no "scale" keyword and no other context) → defaults to the narrower **absolute single-ingredient** interpretation (assume-and-announce tier), stated, correctable — rather than blocking on a question.
- **Revert**: "revert"/"undo" always prompts a confirm of which change is being undone (even the single-most-recent-change case) — ask-first, since a wrong guess here silently loses recipe history. More specific requests ("go back to how it was two weeks ago") list available `recipe_versions` snapshots to choose from.
- **Auto-downscale suggestion**: see `meal_prep_batches` (§3) — a consistent under-consumption pattern for a recipe can trigger a suggested permanent scale-down, using this same proportional-scale mechanism.

---

## 7. Meal logging

### Cooking session lifecycle
- **"Let's start"** (while a recipe is pulled up) → writes `session_started_at`, moves the session into active-cooking state. This is also the clock the deduction-reminder logic measures elapsed time against — no session start means no reminder fires (nothing to measure from).
- **Deduction-not-triggered reminder**: if a cooking session has been active a while with no matching deduction/finish command, a Pushover notification (§10) nudges the user — catches the "forgot to tell it I finished" case rather than letting inventory silently drift out of sync.
- **"I'm finished cooking, deduct the ingredients and count as eaten"** — a compound command: deduct inventory + log as eaten, as two separable actions chained from one utterance (§12). Saying just "deduct the ingredients" without "count as eaten" leaves the meal as a pending `meal_prep_batches` row instead (§3).
- Explicit direct commands carry their own stated default per the Guiding Principle: "I'm finished cooking" alone (no explicit percentage) defaults to 100% of the recipe eaten, stated plainly, correctable after the fact.

### Recipes / meal prep units
Logged via the deduction/eating flows above — macros pulled from the live/snapshotted recipe or batch data, no manual entry needed. See §3 for the full pending-batch / partial-consumption / eaten-vs-disposed behavior.

### Ad-hoc items
- **Ad-hoc items** (snacks, eating out, raw ingredients not tied to a recipe): user states what they ate; assistant attempts a fuzzy match against existing confirmed `ingredients` first (avoids re-asking about frequently-repeated meals — the "same 5 things" pattern). If matched with high confidence, auto-matches and states the match (assume-and-announce tier).
  - **No match found** → assistant asks: *estimate, or do you know the real numbers (e.g. already looked it up)?*
    - **Estimate** → rough figure logged to `meal_log` (`is_estimate = true`) for that meal only. **No permanent `ingredients` row created.**
    - **Real numbers provided** → permanent `ingredients` row created (`source = user-confirmed`), tagged for exact match next time, `meal_log` entry written with `is_estimate = false`.
  - Trivial-variance foods (e.g. "a banana," where the realistic size range barely moves the day's total) default to a reasonable estimate without asking for clarification. Foods with a wide plausible portion range (e.g. "a bowl of cereal") are more likely to warrant a clarifying question.

### Editing a logged entry
- **Editing a logged entry** (iPad, all fields mutable): editing calorie/macro values alone never changes `is_estimate` — a better guess is still a guess. The `is_estimate` toggle is a separate, explicit control:
  - Edit numbers, leave toggle on → today's entry updates only.
  - Edit numbers, flip toggle off → today's entry updates **and** a permanent `ingredients` row is created/updated from those numbers.
  - Leave numbers, flip toggle off → current numbers get promoted to a permanent row as-is.
  - Edit numbers on an already-confirmed (`is_estimate = false`) entry → propagates to the linked `ingredients` row too, keeping the confirmed source-of-truth in sync.

### Bulk seed sources
USDA FoodData Central for generic whole foods (imported as ordinary `ingredients` rows, no schema difference); individual restaurant/chain nutrition data imported per-chain from the chain's own published figures (not in USDA) using the same reusable-prompt pattern as recipe batches.

---

## 8. Recommendation engine

### Hard filters (not scored — exclude before ranking)
- Allergen restrictions (permanent default + any session-declared exclusion, e.g. "one of us has a gluten intolerance" for tonight only — never saved as a reusable profile per user preference).
- Time constraint (uses prep + active time only; passive/unattended time excluded from the "can I fit this" check).
- Cookware available.
- Ingredient availability (full-stock vs. shopping-required — see tiering below).

### Sliders (adjustable, `recommendation_settings`)
Calorie-deficit adherence, protein adherence, carb adherence, fat adherence, diversity (penalizes recent repeats via `meal_log` history), expiration urgency.

### Expiration handling
Kept as a **modest** influence on the main ranking (not allowed to force a poor macro/protein fit). A separate check runs alongside the main recommendation: if an expiring ingredient doesn't fit well into the top-ranked meal, it's surfaced as an **additive side-dish suggestion** rather than distorting the primary pick (e.g. "also, your basil's about to turn — want a quick caprese side?").

### Meal slots
`enabled_meal_slots` setting — default excludes breakfast (user doesn't eat it), includes lunch/dinner/treat. Governs *proactive* suggestions only; explicit requests ("give me a breakfast idea") always work regardless of default. The Ninja Creami treat slot is logged manually, no active recommendation ranking needed for it (narrow, largely fixed category).

### Two-list, two-tier iPad display (lunch / dinner)
Each list split into: full-inventory-coverage recipes first, then shopping-required recipes — ranked within each tier by the sliders above.

### Forward-looking / delivery-order mode
For meals further out than `typical_delivery_lead_hours` (default: **5**): a recipe is eligible if ingredient coverage ≥ `ingredient_coverage_threshold` (default: **50%**), tagged with exactly what's missing. On request ("what's for dinner"), currently on-request only rather than a proactive daily nudge (matches the ask-first/explicit-action pattern used throughout) — revisit if a gentle daily nudge later proves more useful than intrusive.

### Live remaining-budget recompute
`remaining = daily_target − sum(meal_log so far today) − sum(planned_meals not yet logged/converted)`. Recalculated on every `meal_log` write — dinner list re-ranks automatically by closeness-of-fit to the exact remaining gap (not just "high protein" in the abstract) the moment lunch is logged, or the moment a meal is declared via `planned_meals`.

---

## 9. Exercise / Garmin integration

- **Unofficial route** (e.g. `python-garminconnect`-style library, authenticating as the user to pull their own data) chosen over the official Developer Program, which is business-only with a slow/opaque approval process not well suited to a personal project. Accepted tradeoff: some maintenance risk if the unofficial API breaks.
- Feeds `activity_log` with activity type, duration, distance, and Garmin's own device-based calorie estimate (generally better-informed than a generic MET-table guess, though itself imperfect — device calorie accuracy varies by activity type, fitness level, and HR sensor quality, with no consistent overestimate/underestimate bias to correct for globally).
- Feeds into the same TDEE personal-calibration loop as intake logging (Section 3) — corrected against real weigh-in trends over time rather than trusted at face value.

---

## 10. Notifications (Pushover)

Single shared notification function, not scattered calls throughout the codebase:

```python
import requests

PUSHOVER_TOKEN = "your_app_token"
PUSHOVER_USER = "your_user_key"

def notify(message: str, title: str = "Kitchen AI", priority: int = 0, sound: str | None = None):
    payload = {
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "message": message,
        "title": title,
        "priority": priority,
    }
    if sound:
        payload["sound"] = sound
    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # log and continue — a failed notification should never crash the caller
        print(f"Pushover notify failed: {e}")
        return None
```

`PUSHOVER_TOKEN`/`PUSHOVER_USER` are placeholders above — real values belong in `.env` (never committed), loaded at runtime, consistent with how the DB credentials are handled (§2).

Used for: weekly weigh-in check-in, optional expiration alerts (only if proactive nudges are enabled), and the deduction-not-triggered reminder (§7).

---

## 11. Cook-mode iPad UX

Three-column layout, mockups built and approved (built/shown separately due to this chat interface's narrower rendering width — not the intended design; compositing one full-width reference image is a to-do for a full-width working session).

- **Left column**: ingredient checklist.
- **Middle column**: step-by-step instructions, scrollable, no pagination lock. Per-step timers are **non-blocking** — a "Start" button inline on a step doesn't prevent scrolling ahead or reading other steps, and multiple timers can run concurrently (e.g. sear chicken + simmer rice at once). A persistent tray at the top of the screen shows every currently-running timer regardless of scroll position, updates live, and flags completion (sound alert in the real build) independently per timer.
  - Voice ties in: "start the timer for step two" / "how much time's left on the rice" map to the same timer objects, using the alarm/timer capability already part of the voice toolset.
  - **Open question**: should phrasing like "simmer 15 minutes" let the assistant suggest starting the timer when the user reaches that step (still requiring a tap/voice confirm, never auto-starting)?
- **Right column** (comfortable at the iPad's actual 12" width): live macro panel — large circular progress ring for calories at top, three smaller rings below for protein/carbs/fat (consistent color-coding, reused everywhere these are shown), then a scrollable list of thin horizontal progress bars for a **curated** subset of vitamins/minerals (not the full label set — avoid noise).
  - **Open questions**: how to visually treat a micronutrient over 100% of target; which micronutrients make the curated list.

---

## 12. LLM reliability for compound commands

Architecture notes, not yet implemented:

- A reasoning/scratchpad step before tool execution — the model explicitly writes out the command's parsed structure before calling tools — improves multi-part decomposition reliability.
- Backend tools stay atomic/single-purpose rather than a few large multi-parameter functions — easier for the model to chain correctly (this is why `meal_prep_batches` deduction and eaten-logging stay separable actions even when triggered by one compound command, §3/§7).
- A few-shot example set of real compound-command phrasings gets built into the system prompt once real usage data exists.
- For compound-sounding input, consider a two-stage pipeline: a cheap first pass splits the utterance into clean single-intent sub-commands, each handled normally from there.
- Misparsed compound commands caught in `system_log` (§3) feed back in as few-shot examples in the near term, and potentially a small LoRA fine-tune on the local model longer-term (feasible given the hardware already purchased).
- **Before committing to a specific model** (Qwen3 is the leading candidate, currently Qwen3-8B as a pipeline-validation placeholder — see §2): benchmark a written test set of realistic compound phrasings against it and any competitive alternative available at build time. "Good at tool-calling generally" doesn't guarantee "good at this project's specific phrasing patterns." Feeds directly into the open model-choice item, §14.
- **Response streaming to TTS**: the LLM's output is chunked (word/phrase/sentence, configurable — sentence-level by default) and handed to TTS per chunk as it's ready, rather than waiting for the full response — cuts perceived latency on longer or compound replies. Sentence-level chunking works today with Piper as already planned (§1) — just repeated calls, no different TTS engine needed. Only revisit the TTS engine choice if a specific limitation shows up trying to go finer-grained (word-level) with Piper.

---

## 13. Reusable content-generation prompt (for Claude, external to the local system)

Used to batch-generate recipes and bulk nutrition data outside the local pipeline, since it's a one-off/occasional task better suited to a general-purpose model than the always-on local system:

> *"Give me [N] recipes for [description] as JSON matching my kitchen AI schema. Each recipe needs: name, servings, prep_minutes, active_minutes, passive_minutes, instructions, and an ingredients array where each ingredient is a generic category name (e.g. 'hamburger bun,' 'cheddar cheese,' 'chicken breast' — not a specific brand) with quantity and unit. Standard/generic versions of the dishes, not tailored to any specific macro goal."*

Local system handles category resolution against `ingredient_categories` on import (ask-if-uncertain, per standing principle).

---

## 14. Remaining open items / not yet decided

- **Tool-calling model choice** — benchmark plan defined (§12); Qwen3 is the leading candidate but not committed until tested against realistic compound-command phrasing. Also open: whether the Arc B70 (current default, §2) or NVIDIA tensor-parallel (Ada+Blackwell) ends up hosting it — decision deferred until both have actually been tried.
- **HA instance hosting location** — lightweight VM/container on the existing AI server vs. a separate small box, for independence from server reboots — not yet decided, see §1.
- **STT/TTS processing location** — depends on how the HA instance ends up configured (§1); may end up centralized through HA's own Assist pipeline rather than needing a separate container in this stack.
- **Kitchen scale** — not yet purchased. Needs to handle both bulk pot-weighing (several kg, matches `cookware.tare_weight`, §3) and fine small-ingredient precision (sub-gram). Dual-platform scales (large platform ~1g resolution to ~10kg, small secondary platform ~0.1g resolution to ~200g, usable simultaneously) are the best fit found so far, over a single uniform-resolution scale.
- **Shopping list resolution granularity** — whether `shopping_list.ingredient_id` should reference a specific product or a generic category (leaning category, to match how recipes reference ingredients, but not explicitly confirmed).
- **`goal_weight` edit behavior** when it's changed after `target_date`/`target_deficit_surplus` are already set — minor UX call, not fully settled.
- **Recipe sourcing at scale** — the 200-common-meals seed batch and chain-nutrition imports are planned via the Section 13 prompt pattern but not yet executed.
