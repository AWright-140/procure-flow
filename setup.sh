#!/usr/bin/env bash
# First-time setup: install all dependencies.
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

echo "=== GOJEP Procurement Dashboard – Setup ==="

# ── Python 3.12 virtualenv ──────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "▶ Creating Python 3.12 virtual environment…"
    python3.12 -m venv .venv
fi

echo "▶ Installing Python dependencies…"
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r backend/requirements.txt --quiet

echo "▶ Installing Playwright Chromium browser…"
.venv/bin/playwright install chromium

# ── Node.js packages ────────────────────────────────────────────────────────
echo "▶ Installing Node.js packages…"
cd frontend && npm install --silent && cd ..

# ── Database ─────────────────────────────────────────────────────────────────
echo "▶ Initialising database…"
(cd backend && ../.venv/bin/python -c "from database import create_tables; create_tables()")

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Run:  ./start.sh"
echo "  2. Open: http://localhost:5173"
echo "  3. Click 'Run Scraper Now' in the sidebar."
echo ""
echo "To customise CSS selectors (if the GOJEP site changes):"
echo "  edit backend/config.py  →  LISTING_SELECTORS / DETAIL_SELECTORS"
echo "  then run:  cd backend && ../.venv/bin/python scraper.py --inspect"
