from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import engine
from app.routers import (
    behavior_settings,
    calendar,
    cookware,
    garmin,
    ingredients,
    inventory,
    meal_log,
    meal_prep_batches,
    notifications,
    profile,
    recipes,
    recommendations,
    sessions,
    settings_backup,
    shopping_list,
    system_log,
    tracking,
    voice,
)
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Kitchen AI", lifespan=lifespan)

app.include_router(ingredients.router)
app.include_router(inventory.router)
app.include_router(cookware.router)
app.include_router(recipes.router)
app.include_router(meal_log.router)
app.include_router(shopping_list.router)
app.include_router(behavior_settings.router)
app.include_router(system_log.router)
app.include_router(tracking.router)
app.include_router(recommendations.router)
app.include_router(sessions.router)
app.include_router(meal_prep_batches.router)
app.include_router(notifications.router)
app.include_router(garmin.router)
app.include_router(profile.router)
app.include_router(calendar.router)
app.include_router(settings_backup.router)
app.include_router(voice.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}


# --- Frontend (PWA) ----------------------------------------------------------
# Mounted last so it never shadows an API route above. All in-app navigation
# is hash-based (#/home, #/recipe/12, ...), so a single static index.html at
# "/" is sufficient -- there's no server-side route to fall back for.
# In the container (Dockerfile COPYs frontend/ to /app/frontend, alongside
# /app/app) that's parent.parent; running straight from a repo checkout
# (backend/app/main.py, frontend/ at the repo root) it's one level higher --
# try both so this works either way.
_candidates = [
    Path(__file__).resolve().parent.parent / "frontend",
    Path(__file__).resolve().parent.parent.parent / "frontend",
]
class _NoCacheStaticFiles(StaticFiles):
    """Force revalidation on every load. Plain StaticFiles sends no
    Cache-Control at all, so browsers fall back to heuristic caching and
    can keep serving a stale JS file indefinitely after a deploy -- which
    silently breaks call signatures between files that update together
    (e.g. rings.js/recipe.js) since only some of them get re-fetched."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


_frontend_dir = next((p for p in _candidates if p.is_dir()), None)
if _frontend_dir is not None:
    app.mount("/", _NoCacheStaticFiles(directory=_frontend_dir, html=True), name="frontend")
