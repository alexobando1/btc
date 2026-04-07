#!/bin/sh
set -e

echo "=== PolyBot Starting ==="

# Run the trading bot in the background (if private key is set)
if [ -n "$POLYMARKET_PRIVATE_KEY" ]; then
  echo "▶ Starting trading bot..."
  python main.py &
  BOT_PID=$!
  echo "  Bot PID: $BOT_PID"
else
  echo "⚠ POLYMARKET_PRIVATE_KEY not set — bot running in dashboard-only mode"
fi

# Run the dashboard API in the foreground (keeps container alive)
echo "▶ Starting dashboard API on port ${PORT:-8000}..."
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
