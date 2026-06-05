#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# CourtReserve Booker — Setup Script
# Run this ONCE before using book_court_manual.py
# Works on macOS and Linux
# ─────────────────────────────────────────────────────────────────────────────

set -e  # stop on any error

echo ""
echo "═══════════════════════════════════════════════════════"
echo "   CourtReserve Booker — Setup"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── 1. CHECK PYTHON ───────────────────────────────────────────────────────────
echo "▶ Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
    VERSION=$($PYTHON --version 2>&1)
    echo "  ✅ Found: $VERSION at $PYTHON"
else
    echo "  ❌ Python 3 not found."
    echo ""
    # macOS: install via Homebrew
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Installing Python via Homebrew..."
        if ! command -v brew &>/dev/null; then
            echo "  Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python3
        PYTHON=$(command -v python3)
        echo "  ✅ Python installed: $($PYTHON --version)"
    # Linux (Debian/Ubuntu)
    elif command -v apt-get &>/dev/null; then
        echo "  Installing Python via apt..."
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-pip
        PYTHON=$(command -v python3)
        echo "  ✅ Python installed: $($PYTHON --version)"
    else
        echo "  Please install Python 3 manually from https://www.python.org/downloads/"
        exit 1
    fi
fi

# ── 2. CHECK PIP ──────────────────────────────────────────────────────────────
echo ""
echo "▶ Checking pip..."
if $PYTHON -m pip --version &>/dev/null; then
    echo "  ✅ pip is available."
else
    echo "  Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON
    echo "  ✅ pip installed."
fi

# ── 3. INSTALL PYTHON PACKAGES ────────────────────────────────────────────────
echo ""
echo "▶ Installing required Python packages..."
$PYTHON -m pip install --quiet --upgrade playwright schedule
echo "  ✅ playwright and schedule installed."

# ── 4. INSTALL PLAYWRIGHT BROWSER ────────────────────────────────────────────
echo ""
echo "▶ Installing Playwright browser (Chromium)..."
echo "  (This downloads ~150MB — only needed once)"
$PYTHON -m playwright install chromium
echo "  ✅ Chromium installed."

# ── 5. VERIFY ─────────────────────────────────────────────────────────────────
echo ""
echo "▶ Verifying installation..."
$PYTHON -c "from playwright.sync_api import sync_playwright; print('  ✅ Playwright OK')"
$PYTHON -c "import schedule; print('  ✅ Schedule OK')"

# ── DONE ──────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "   ✅ Setup complete! You're ready to run the booker."
echo "═══════════════════════════════════════════════════════"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🤖 Auto-Booker (books every night at midnight)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Test immediately:"
echo "    python3 book_court.py --now"
echo ""
echo "  Run in background (auto-books every midnight):"
echo "    nohup python3 book_court.py >> court_booker.log 2>&1 &"
echo ""
echo "  Check logs:"
echo "    tail -f court_booker.log"
echo ""
echo "  Stop the scheduler:"
echo "    pkill -f book_court.py"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📅 Manual Booker (book a specific date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "    python3 book_court_manual.py 3/25/2026                   # best available"
echo "    python3 book_court_manual.py 3/25/2026 anytime anycourt  # same as above"
echo "    python3 book_court_manual.py 3/25/2026 7:00PM            # specific time"
echo "    python3 book_court_manual.py 3/25/2026 7:00PM 3          # time + court #3"
echo "    python3 book_court_manual.py 3/25/2026 anytime 1         # any time, court #1"
echo ""
echo "  See README.md for full documentation."
echo ""
