#!/usr/bin/env bash
# One-command launcher: starts the FastAPI backend and Vite frontend together.
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "▶ Starting backend on http://localhost:8000 …"
"$REPO/.venv/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 \
    --app-dir "$REPO/backend" &
BACKEND_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "▶ Starting frontend on http://localhost:5173 …"
cd "$REPO/frontend"
npm run dev &
FRONTEND_PID=$!

# ── Cleanup on Ctrl-C ────────────────────────────────────────────────────────
trap "echo ''; echo '⏹ Shutting down…'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "✅ Dashboard running at http://localhost:5173"
echo "   API docs at       http://localhost:8000/docs"
echo "   Press Ctrl+C to stop."
echo ""
wait
