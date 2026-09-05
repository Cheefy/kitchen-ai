FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/alembic.ini .
COPY backend/alembic ./alembic
# Frontend PWA lives at the repo root (sibling of backend/), served
# same-origin by FastAPI -- see app/main.py's StaticFiles mount.
COPY frontend ./frontend

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
