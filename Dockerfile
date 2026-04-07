FROM python:3.11-slim

WORKDIR /app

# ── 1. Python deps (pure Python only, no compilation) ─────────────────────
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# ── 2. Node.js (install, build frontend, then remove) ─────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci --prefer-offline

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Remove Node + node_modules to free space
RUN apt-get purge -y nodejs && apt-get autoremove -y && rm -rf frontend/node_modules

# ── 3. App source ──────────────────────────────────────────────────────────
COPY api/      ./api/
COPY config.py ./

ENV PORT=8000
EXPOSE $PORT

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
