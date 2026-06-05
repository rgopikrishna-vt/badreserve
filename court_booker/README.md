# 🏸 CourtReserve Racquetball Auto-Booker
### Worldgate Athletic Club — Automated Court Booking

---

## 📦 What's Included

| File | Description |
|---|---|
| `book_court.py` | Runs every night at midnight, auto-books 7 days out |
| `book_court_manual.py` | Book a specific date on demand |
| `setup.sh` | One-time setup — installs all requirements |
| `README.md` | This file |

---

## ⚙️ First-Time Setup (Run Once)

Open a Terminal, navigate to the folder, then run:

```bash
cd path/to/court_booker        # e.g. cd ~/Downloads/court_booker
chmod +x setup.sh              # make the script executable (required once)
./setup.sh                     # run the setup
```

This will automatically install:
- Python 3
- pip
- Playwright (browser automation library)
- Chromium browser (~150MB)
- Schedule library

> ✅ You only need to do this once.

---

## 🤖 Auto-Booker (book_court.py)

Runs every night at midnight and books the best available court 7 days out,
falling back to 6, 5, then 4 days out if needed.

### Step 1 — Test it first (run immediately):
```bash
cd path/to/court_booker
python3 book_court.py --now
```
This runs the booking logic immediately so you can verify it works before setting up automation.

### Step 2 — Run it automatically every midnight

**Option A: Run in the background (simplest)**
Opens a persistent background process. Keeps running even after closing the terminal,
but stops if you restart your Mac.
```bash
nohup python3 book_court.py >> court_booker.log 2>&1 &
```
To stop it later:
```bash
pkill -f book_court.py
```

**Option B: Run automatically on Mac startup using launchd (recommended)**
This starts the script automatically every time your Mac boots, so you never have to remember to start it manually.

1. Create the launchd config file:
```bash
cat > ~/Library/LaunchAgents/com.courtbooker.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.courtbooker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/anaconda3/bin/python3</string>
        <string>/path/to/court_booker/book_court.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/court_booker/court_booker.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/court_booker/court_booker.log</string>
</dict>
</plist>
EOF
```

2. Replace `/path/to/court_booker/` with your actual folder path (e.g. `/Users/yourname/Downloads/court_booker/`):
```bash
sed -i '' 's|/path/to/court_booker|/Users/yourname/Downloads/court_booker|g' ~/Library/LaunchAgents/com.courtbooker.plist
```

3. Load and start it:
```bash
launchctl load ~/Library/LaunchAgents/com.courtbooker.plist
launchctl start com.courtbooker
```

4. To stop and remove it:
```bash
launchctl unload ~/Library/LaunchAgents/com.courtbooker.plist
```

**Option C: Use cron (alternative to launchd)**
```bash
crontab -e
```
Add this line (replace path with your actual folder path):
```
0 0 * * * /opt/anaconda3/bin/python3 /path/to/court_booker/book_court.py --now >> /path/to/court_booker/court_booker.log 2>&1
```

### Check the logs (any option):
```bash
tail -f court_booker.log
```

### Booking logic:
- Tries dates: 7 days out → 6 → 5 → 4 days from today
- Stops as soon as one booking succeeds
- Skips dates where you already have a booking
- Prefers Court #3, then #1, then #2
- Weekdays: only books 6 PM or later
- Weekends: only books 12 PM or later, prefers 2 PM+
- If Prime Time is restricted, skips to daytime slots
- Retries up to 3 times on failure

### ⚠️ Important (for Options A and B):
- Your Mac must be **ON and AWAKE** at midnight
- Prevent sleep: go to **System Settings → Battery → Prevent automatic sleep**
- Or run: `sudo pmset -a sleep 0` to disable sleep entirely

---

## 📅 Manual Booker (book_court_manual.py)

Book a specific date on demand.

### Usage:

```bash
# Best available slot
python3 book_court_manual.py 3/25/2026

# Any time, any court
python3 book_court_manual.py 3/25/2026 anytime anycourt

# Specific time
python3 book_court_manual.py 3/25/2026 7:00PM

# Specific time + court number
python3 book_court_manual.py 3/25/2026 7:00PM 3

# Any time, specific court
python3 book_court_manual.py 3/25/2026 anytime 1
```

### Time rules (when using anytime):

  Weekday (Mon-Fri): 6 PM → 7 PM → 8 PM → 9 PM only. Never before 6 PM.
  Weekend (Sat-Sun): 2 PM → 3 PM → ... → 9 PM → 1 PM → 12 PM. Never before 12 PM.

### Login prompt:
When you run the script, it will ask for your credentials:

  ── CourtReserve Login ──────────────────────────────────────
  Default account: gopi.accs@gmail.com
  Email (press Enter to use default):

- Press Enter to use the default account
- Type your own email to use a different account (password will be hidden)

---

## ❗ Troubleshooting

  command not found: python3   → Run ./setup.sh first
  Login timeout error          → Slow internet, try again
  Prime Time restricted        → Already have an evening booking that day
  Already booked on this date  → Existing reservation, script skips to next date
  ALL BOOKED                   → All courts taken, try a different date
  Script stops at midnight     → Mac went to sleep, disable auto-sleep

---

## 📋 Requirements

- macOS or Linux
- Internet connection
- CourtReserve account at Worldgate Athletic Club
- Mac must be awake at midnight (auto-scheduler only)

---

---

## 📌 Quick Reference

### book_court.py — Auto Scheduler
```bash
# Start scheduler (runs every midnight automatically)
nohup python3 book_court.py >> court_booker.log 2>&1 &

# Test immediately without waiting for midnight
python3 book_court.py --now

# Watch live logs
tail -f court_booker.log
```

### book_court_manual.py — Manual Booking
```bash
# Best available slot on a date
python3 book_court_manual.py 3/25/2026

# Any time, any court
python3 book_court_manual.py 3/25/2026 anytime anycourt

# Specific time
python3 book_court_manual.py 3/25/2026 7:00PM

# Specific time + court number
python3 book_court_manual.py 3/25/2026 7:00PM 3

# Any time, specific court
python3 book_court_manual.py 3/25/2026 anytime 1
```

---

Built with Python + Playwright
