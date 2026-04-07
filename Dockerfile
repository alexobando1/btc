FROM python:3.11

WORKDIR /app

# ── 1. Python deps ─────────────────────────────────────────────────────────
# Dashboard API deps (pure Python, fast)
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# Bot deps (needs gcc/Rust — python:3.11 full image has them)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ── 2. Node.js → build React frontend → remove Node ───────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci

COPY frontend/ ./frontend/
RUN cd frontend && npm run build \
    && rm -rf node_modules

# ── 3. App source ──────────────────────────────────────────────────────────
COPY bot/       ./bot/
COPY api/       ./api/
COPY prompts/   ./prompts/
COPY config.py  ./
COPY main.py    ./
COPY start.sh   ./
RUN chmod +x start.sh

ENV PORT=8000
EXPOSE $PORT

CMD ["./start.sh"]
