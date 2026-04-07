# ── Stage 1: Build React frontend ───────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime + FastAPI ───────────────────────────────────────
# The dashboard API only uses fastapi, uvicorn, aiosqlite, python-dotenv.
# No compilation needed — all pure Python or pre-built wheels.
FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy source (api + config only — bot deps not needed for the dashboard)
COPY api/      ./api/
COPY config.py ./

# Copy built React app
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PORT=8000
EXPOSE $PORT

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
