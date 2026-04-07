# ── Stage 1: Build React frontend ───────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime + FastAPI ───────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

# Copy bot source
COPY bot/       ./bot/
COPY api/       ./api/
COPY config.py  ./
COPY prompts/   ./prompts/

# Copy built React app
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Default port (Railway sets $PORT)
ENV PORT=8000

EXPOSE $PORT

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
