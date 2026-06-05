"""
CourtReserve Manual Booker — Racquetball Courts, Worldgate Athletic Club

Usage:
    python3 book_court_manual.py <date> [time] [court]

Examples:
    python3 book_court_manual.py 3/25/2026                   # best available
    python3 book_court_manual.py 3/25/2026 anytime anycourt  # same as above
    python3 book_court_manual.py 3/25/2026 7:00PM            # specific time
    python3 book_court_manual.py 3/25/2026 7:00PM 3          # time + court #3
    python3 book_court_manual.py 3/25/2026 anytime 1         # any time, court #1

Arguments:
    date    Required. Format: M/D/YYYY  e.g. 3/25/2026
    time    Optional. e.g. 7:00PM or anytime  (default: anytime)
    court   Optional. 1, 2, or 3              (default: anycourt)
"""

import asyncio
import logging
import sys
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── CONFIG ────────────────────────────────────────────────────────────────────
DEFAULT_EMAIL    = "gopi.accs@gmail.com"
DEFAULT_PASSWORD = "Gopi*1992"
ORG_ID   = "9062"
LOGIN_URL        = f"https://app.courtreserve.com/Online/Account/LogIn/{ORG_ID}"
RESERVATIONS_URL = f"https://app.courtreserve.com/Online/Reservations/Bookings/{ORG_ID}?sId=18284"

COURT_PREFERENCE = ["Racquetball Court #3", "Racquetball Court #1", "Racquetball Court #2"]

PRIME_TIME_SLOTS = ["6:00 PM", "7:00 PM", "5:00 PM", "8:00 PM", "9:00 PM"]
NON_PRIME_SLOTS  = [
    "4:00 PM", "3:00 PM", "2:00 PM", "1:00 PM",
    "12:00 PM", "11:00 AM", "10:00 AM", "9:00 AM",
    "8:00 AM",  "7:00 AM",
]
ALL_TIMES = PRIME_TIME_SLOTS + NON_PRIME_SLOTS

# Preferred time orders based on day type
# Weekday: 6 PM or later ONLY — never book before 6 PM on a weekday
WEEKDAY_TIMES = [
    "6:00 PM", "7:00 PM", "8:00 PM", "9:00 PM",
]
# Weekend: after 2 PM preferred, 12 PM minimum — never book before 12 PM on a weekend
WEEKEND_TIMES = [
    "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM",    # ideal
    "6:00 PM", "7:00 PM", "8:00 PM", "9:00 PM",    # evening fine too
    "1:00 PM", "12:00 PM",                          # acceptable minimum
]

HEADLESS = True  # Set False to watch the browser
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("court_booker_manual.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


async def book_court_manual(target_date: str, preferred_time: str = None, preferred_court: str = None, email: str = None, password: str = None):
    """
    Book a court on the given date.
    - target_date: M/D/YYYY e.g. '3/25/2026'
    - preferred_time: e.g. '7:00 PM' — if None, tries all times in order
    - preferred_court: e.g. '#1' or 'Racquetball Court #1' — if None, tries all courts
    - email/password: CourtReserve credentials (defaults used if not provided)
    """
    # Use defaults if not provided
    if not email:
        email = DEFAULT_EMAIL
    if not password:
        password = DEFAULT_PASSWORD

    # Resolve court preference
    # Accepts: None, "anycourt", "#1", "1", "#3", "Racquetball Court #2"
    if not preferred_court or preferred_court.lower() in ("anycourt", "any", "all"):
        courts = COURT_PREFERENCE
    else:
        courts = COURT_PREFERENCE  # default
        for c in COURT_PREFERENCE:
            if preferred_court.replace("Racquetball Court ", "").strip("#") in c:
                courts = [c] + [x for x in COURT_PREFERENCE if x != c]
                break

    # Normalize time input: convert 7:00PM → 7:00 PM, 7PM → 7:00 PM
    if preferred_time and preferred_time.lower() not in ("anytime", "any", "best", "all"):
        import re
        t = preferred_time.strip().upper()
        # Insert space before AM/PM if missing: 7:00PM → 7:00 PM
        t = re.sub(r'(\d)(AM|PM)$', r'\1 \2', t)
        # Handle shorthand like 7PM → 7:00 PM
        t = re.sub(r'^(\d+)\s(AM|PM)$', r'\1:00 \2', t)
        preferred_time = t

    # Normalize court input: accept 1, 2, 3, #1, #2, #3
    if preferred_court and preferred_court.lower() not in ("anycourt", "any", "all"):
        preferred_court = preferred_court.strip().lstrip('#')

    # Resolve time preference
    # Accepts: None, "anytime", "any", "best"
    from datetime import datetime, date as date_type
    parts = target_date.split("/")
    target_dt = date_type(int(parts[2]), int(parts[0]), int(parts[1]))
    is_weekend = target_dt.weekday() >= 5  # Saturday=5, Sunday=6
    day_label = "weekend" if is_weekend else "weekday"
    default_times = WEEKEND_TIMES if is_weekend else WEEKDAY_TIMES

    if not preferred_time or preferred_time.lower() in ("anytime", "any", "best", "all"):
        times = default_times
        log.info(f"Target is a {day_label} — trying times: {times}")
    else:
        # Specific time requested — put it first, then fall back within allowed window
        times = [preferred_time] + [t for t in default_times if t != preferred_time]
        log.info(f"Target is a {day_label} — trying times: {times}")

    log.info(f"Manual booking: {target_date}")
    log.info(f"Preferred time: {preferred_time or 'best available'}")
    log.info(f"Preferred court: {preferred_court or 'Court #3 → #1 → #2'}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        page.set_default_timeout(60000)

        try:
            # ── LOGIN ─────────────────────────────────────────────────────────
            log.info("Logging in...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)  # extra wait for React to hydrate
            await page.wait_for_selector('input[name="email"]', timeout=60000)
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[data-testid="Continue"]')
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(3000)

            if "/account/login" in page.url.lower():
                log.error("Login failed.")
                return False
            log.info("Login successful.")

            # ── NAVIGATE TO RESERVATIONS ──────────────────────────────────────
            await page.goto(RESERVATIONS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            # ── NAVIGATE TO TARGET DATE ───────────────────────────────────────
            from datetime import datetime, date as date_type
            parts2 = target_date.split("/")
            target_dt2 = date_type(int(parts2[2]), int(parts2[0]), int(parts2[1]))
            today_dt  = datetime.now().date()
            target_dt = target_dt2
            clicks    = (target_dt - today_dt).days

            if clicks < 0:
                log.error(f"Date {target_date} is in the past!")
                return False
            if clicks > 7:
                log.error(f"Date {target_date} is more than 7 days out — CourtReserve won't allow it.")
                return False

            log.info(f"Navigating to {target_dt.strftime('%A, %B %-d, %Y')} ({clicks} clicks)...")

            async def get_date():
                try: return (await page.inner_text('.k-lg-date-format')).strip()
                except: return ""

            for i in range(clicks):
                await page.click('button[data-testid="button-2"].k-nav-next')
                await page.wait_for_timeout(1500)
            await page.wait_for_timeout(2000)
            log.info(f"Scheduler showing: {await get_date()}")

            # ── CHECK IF ALREADY BOOKED ───────────────────────────────────────
            already = await page.evaluate(
                "() => document.querySelectorAll('.sch-my-reservation').length > 0"
            )
            if already:
                log.warning(f"You already have a booking on {target_date}!")
                print(f"\n⚠️  Already booked on {target_date}. Exiting.\n")
                return False

            # ── GRID DEBUG ────────────────────────────────────────────────────
            counts = await page.evaluate("""() => {
                const all = document.querySelectorAll('button[data-testid="reserveBtn"]');
                const vis = [...all].filter(b => !b.classList.contains('hide'));
                return {total: all.length, visible: vis.length};
            }""")
            log.info(f"Grid: {counts['total']} total, {counts['visible']} available")

            # ── HELPERS ───────────────────────────────────────────────────────
            async def find_slot(time_str, court_label):
                btn = await page.evaluate_handle(f"""() => {{
                    const buttons = document.querySelectorAll(
                        'button[data-testid="reserveBtn"][data-courtlabel="{court_label}"]'
                    );
                    for (const b of buttons) {{
                        if (!b.classList.contains('hide') &&
                            b.textContent.trim() === 'Reserve {time_str}') {{
                            return b;
                        }}
                    }}
                    return null;
                }}""")
                ok = await page.evaluate("el => el !== null && el !== undefined", btn)
                return btn if ok else None

            async def wait_for_modal():
                for _ in range(25):
                    await page.wait_for_timeout(1000)
                    s = await page.query_selector('button[data-testid="Save"]')
                    if s and await s.is_visible():
                        return 'save', s
                    e = await page.query_selector('.fn-error-modal-content')
                    if e:
                        return 'error', (await e.inner_text()).strip()
                return 'timeout', None

            async def close_modal():
                try:
                    c = await page.query_selector('button[data-dismiss="modal"]')
                    if c:
                        await c.click()
                        await page.wait_for_timeout(1500)
                except Exception:
                    pass

            # ── TRY SLOTS ─────────────────────────────────────────────────────
            prime_blocked = False

            for t in times:
                if prime_blocked and t in PRIME_TIME_SLOTS:
                    log.info(f"Skipping prime time slot {t} (restricted).")
                    continue

                for court in courts:
                    btn = await find_slot(t, court)
                    if not btn:
                        continue

                    log.info(f"Trying: {court} at {t}...")
                    await btn.click()
                    await page.wait_for_timeout(2000)

                    try:
                        await page.wait_for_selector('#create-res-modal', timeout=10000)
                    except PlaywrightTimeout:
                        log.warning("Modal didn't appear.")
                        continue

                    kind, data = await wait_for_modal()

                    if kind == 'timeout':
                        log.warning(f"Modal content timed out for {t}.")
                        await close_modal()
                        continue

                    if kind == 'error':
                        log.warning(f"Blocked at {t}: {data}")
                        await close_modal()
                        if "prime time" in data.lower():
                            prime_blocked = True
                        break  # try next time

                    # Save button found — click it
                    log.info("Clicking Save...")
                    await data.click()
                    await page.wait_for_timeout(4000)

                    err = await page.query_selector('.fn-error-modal-content')
                    if err:
                        err_txt = (await err.inner_text()).strip()
                        log.warning(f"Post-submit error: {err_txt}")
                        await close_modal()
                        if "prime time" in err_txt.lower():
                            prime_blocked = True
                        break

                    log.info(f"✅ SUCCESS: {court} booked at {t} on {target_date}!")
                    print(f"\n✅ Booked {court} at {t} on {target_date}\n")
                    return True

            log.error(f"Could not book any slot on {target_date}.")
            print(f"\n❌ No slots available on {target_date}.\n")
            return False

        except Exception as e:
            log.error(f"Error: {e}", exc_info=True)
            return False
        finally:
            await browser.close()


if __name__ == "__main__":
    import getpass

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    date_arg  = sys.argv[1]
    time_arg  = sys.argv[2] if len(sys.argv) > 2 else None
    court_arg = sys.argv[3] if len(sys.argv) > 3 else None

    # ── CREDENTIALS PROMPT ────────────────────────────────────────────────────
    print("\n── CourtReserve Login ──────────────────────────────────────")
    print(f"Default account: {DEFAULT_EMAIL}")
    email_input = input("Email (press Enter to use default): ").strip()
    if email_input:
        email_arg = email_input
        password_arg = getpass.getpass("Password: ")
        print(f"Using account: {email_arg}")
    else:
        email_arg    = DEFAULT_EMAIL
        password_arg = DEFAULT_PASSWORD
        print(f"Using default account: {DEFAULT_EMAIL}")
    print("────────────────────────────────────────────────────────────\n")

    asyncio.run(book_court_manual(date_arg, time_arg, court_arg, email_arg, password_arg))
