from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine
from app.routers import cookware, ingredients, inventory, recipes

app = FastAPI(title="Kitchen AI")

app.include_router(ingredients.router)
app.include_router(inventory.router)
app.include_router(cookware.router)
app.include_router(recipes.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
