from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine

app = FastAPI(title="Kitchen AI")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
