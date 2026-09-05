from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routers import (
    behavior_settings,
    cookware,
    garmin,
    ingredients,
    inventory,
    meal_log,
    meal_prep_batches,
    notifications,
    recipes,
    recommendations,
    sessions,
    shopping_list,
    system_log,
    tracking,
)

app = FastAPI(title="Kitchen AI")

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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
