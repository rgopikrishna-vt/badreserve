"""
CourtReserve Auto-Booker — Racquetball Courts, Worldgate Athletic Club

Usage:
    python3 book_court.py            # start midnight scheduler (runs every night)
    python3 book_court.py --now      # run immediately (for testing)

What it does:
    - Runs every night at midnight
    - Tries to book 7 days out, falls back to 6, 5, then 4 days out
    - Skips dates where you already have a booking
    - Prefers Court #3 at 6 PM, falls back by court then time
    - On weekdays: only books 6 PM or later
    - On weekends: only books 12 PM or later, prefers 2 PM+
    - Handles Prime Time restriction by skipping to daytime slots
    - Retries up to 3 times on transient failures

Logs:
    tail -f court_booker.log

Run in background (keeps running after closing terminal):
    nohup python3 book_court.py >> court_booker.log 2>&1 &
"""

import asyncio
import logging
import schedule
import time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ── CONFIG ────────────────────────────────────────────────────────────────────
EMAIL    = "gopi.accs@gmail.com"
PASSWORD = "Gopi*1992"
ORG_ID   = "9062"
LOGIN_URL        = f"https://app.courtreserve.com/Online/Account/LogIn/{ORG_ID}"
RESERVATIONS_URL = f"https://app.courtreserve.com/Online/Reservations/Bookings/{ORG_ID}?sId=18284"

# Court preference: #3 first, then #1, then #2
COURT_PREFERENCE = ["Racquetball Court #3", "Racquetball Court #1", "Racquetball Court #2"]

# Preferred time
PREFERRED_TIME = "6:00 PM"

# Weekday preferred slots: 6 PM and later
WEEKDAY_TIMES = [
    "6:00 PM", "7:00 PM", "8:00 PM", "9:00 PM", "10:00 PM",
]

# Weekend preferred slots: 3 PM and later
WEEKEND_TIMES = [
    "3:00 PM", "4:00 PM", "5:00 PM", "6:00 PM",
    "7:00 PM", "8:00 PM", "9:00 PM", "10:00 PM",
]

# Prime Time slots (club limits 1/day) — just track for error detection
PRIME_TIME_SLOTS = WEEKDAY_TIMES + WEEKEND_TIMES

# Non-prime fallback (only used if all preferred slots are taken/blocked)
NON_PRIME_SLOTS = [
    "2:00 PM", "1:00 PM", "12:00 PM", "11:00 AM", "10:00 AM", "9:00 AM",
]

def get_preferred_times() -> list:
    """Return time slots in preference order based on today's day of week."""
    # Target date is 7 days from now
    target_dt = datetime.now() + timedelta(days=7)
    is_weekend = target_dt.weekday() >= 5  # 5=Saturday, 6=Sunday
    if is_weekend:
        return WEEKEND_TIMES + NON_PRIME_SLOTS
    else:
        return WEEKDAY_TIMES + NON_PRIME_SLOTS

ALL_TIMES = get_preferred_times()  # computed at import time; also recalculated in book_court

MAX_RETRIES = 3
HEADLESS    = True  # Set False to watch the browser
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("court_booker.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def get_target_dates() -> list[str]:
    """Returns dates 7, 6, 5, 4 days from now as M/D/YYYY strings.
    e.g. if today is Mar 15: ['3/22/2026', '3/21/2026', '3/20/2026', '3/19/2026']
    """
    return [
        (datetime.now() + timedelta(days=d)).strftime("%-m/%-d/%Y")
        for d in [7, 6, 5, 4]
    ]


async def book_court(target_date: str, attempt: int = 1) -> bool | str:
    """
    Opens browser, logs in, navigates to March 22, finds and books best slot.
    Returns:
        True        — booking confirmed
        "ALL_BOOKED" — no slots available at all
        False       — transient error (will retry)
    """
    log.info(f"Attempt {attempt}: Booking court on {target_date}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        page.set_default_timeout(60000)

        try:
            # ── 1. LOGIN ──────────────────────────────────────────────────────
            log.info(f"Navigating to login page...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            log.info(f"Current URL: {page.url}")

            await page.wait_for_selector('input[name="email"]', timeout=30000)
            await page.fill('input[name="email"]', EMAIL)
            await page.fill('input[name="password"]', PASSWORD)
            await page.click('button[data-testid="Continue"]')
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(3000)

            if "/account/login" in page.url.lower():
                log.error("Login failed — still on login page.")
                return False
            log.info(f"Login successful. URL: {page.url}")

            # ── 2. GO TO RACQUETBALL PAGE ─────────────────────────────────────
            log.info("Navigating to racquetball reservations...")
            await page.goto(RESERVATIONS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            # ── 3. NAVIGATE TO TARGET DATE ────────────────────────────────────
            # Parse target_date (M/D/YYYY) to figure out how many Next clicks needed
            from datetime import date as date_type
            parts = target_date.split("/")
            target_dt = date_type(int(parts[2]), int(parts[0]), int(parts[1]))
            today_dt = datetime.now().date()
            clicks_needed = (target_dt - today_dt).days
            log.info(f"Target: {target_dt.strftime('%A, %B %-d, %Y')} ({clicks_needed} clicks needed)")

            async def get_scheduler_date():
                try:
                    return (await page.inner_text('.k-lg-date-format')).strip()
                except:
                    return ""

            current = await get_scheduler_date()
            log.info(f"Scheduler showing: {current}")
            log.info(f"Clicking Next {clicks_needed} times...")
            for i in range(clicks_needed):
                await page.click('button[data-testid="button-2"].k-nav-next')
                await page.wait_for_timeout(1500)
                current = await get_scheduler_date()
                log.info(f"  After click {i+1}: {current}")

            await page.wait_for_timeout(2000)
            log.info(f"Scheduler now showing: {await get_scheduler_date()}")

            # ── 4. CHECK IF ALREADY BOOKED ON THIS DATE ──────────────────────
            # My reservations show a star icon with class 'sch-my-reservation'
            already_booked = await page.evaluate("""() => {
                return document.querySelectorAll('.sch-my-reservation').length > 0;
            }""")
            if already_booked:
                log.info(f"Already have a booking on {target_date} — skipping.")
                return "ALL_BOOKED"
            log.info(f"No existing booking on {target_date} — proceeding.")

            # ── 5. FIND AVAILABLE SLOT ────────────────────────────────────────
            log.info("Scanning grid for available slots...")

            async def find_slot(time_str, court_label):
                """Return visible Reserve button for court+time, or None."""
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

            async def wait_for_modal_content():
                """
                Poll until AJAX-loaded modal content appears.
                Returns ('save', btn) or ('error', text) or ('timeout', None).
                """
                for _ in range(25):  # up to 25 seconds
                    await page.wait_for_timeout(1000)
                    s = await page.query_selector('button[data-testid="Save"]')
                    if s and await s.is_visible():
                        return 'save', s
                    e = await page.query_selector('.fn-error-modal-content')
                    if e:
                        txt = (await e.inner_text()).strip()
                        return 'error', txt
                return 'timeout', None

            async def close_modal():
                try:
                    c = await page.query_selector('button[data-dismiss="modal"]')
                    if c:
                        await c.click()
                        await page.wait_for_timeout(1500)
                except Exception:
                    pass

            async def try_book_slot(time_str, court_label):
                """
                Click a slot, wait for modal, click Save.
                Returns: 'success', 'prime_time', 'blocked:<msg>', or 'no_slot'
                """
                btn = await find_slot(time_str, court_label)
                if not btn:
                    return 'no_slot'

                log.info(f"Clicking: Reserve {time_str} on {court_label}")
                await btn.click()
                await page.wait_for_timeout(2000)

                # Wait for modal shell
                try:
                    await page.wait_for_selector('#create-res-modal', timeout=10000)
                except PlaywrightTimeout:
                    log.warning("Modal shell didn't appear.")
                    return 'no_slot'

                # Wait for AJAX content
                kind, data = await wait_for_modal_content()

                if kind == 'timeout':
                    log.warning(f"Modal content never loaded for {time_str}.")
                    await close_modal()
                    return 'no_slot'

                if kind == 'error':
                    log.warning(f"Blocked at {time_str}: {data}")
                    await close_modal()
                    if "prime time" in data.lower():
                        return 'prime_time'
                    return f'blocked:{data}'

                # kind == 'save' — click it
                log.info("Clicking Save...")
                await data.click()
                await page.wait_for_timeout(4000)

                # Check for post-submit error
                e = await page.query_selector('.fn-error-modal-content')
                if e:
                    err_txt = (await e.inner_text()).strip()
                    log.warning(f"Post-submit error at {time_str}: {err_txt}")
                    await close_modal()
                    if "prime time" in err_txt.lower():
                        return 'prime_time'
                    return f'blocked:{err_txt}'

                log.info(f"✅ SUCCESS: {court_label} booked at {time_str}!")
                return 'success'

            # Count available buttons for debug
            counts = await page.evaluate("""() => {
                const all = document.querySelectorAll('button[data-testid="reserveBtn"]');
                const vis = [...all].filter(b => !b.classList.contains('hide'));
                return {total: all.length, visible: vis.length};
            }""")
            log.info(f"Grid: {counts['total']} total buttons, {counts['visible']} visible")

            if counts['total'] == 0:
                log.error("No buttons found — page may not have rendered.")
                return False

            # Determine preferred times based on target day (weekday vs weekend)
            times_to_try = get_preferred_times()
            target_dt = datetime.now() + timedelta(days=7)
            day_type = "weekend" if target_dt.weekday() >= 5 else "weekday"
            log.info(f"Target is a {day_type} — trying times: {times_to_try}")

            # Try all times × courts; on Prime Time block, skip to non-prime
            prime_time_blocked = False

            for t in times_to_try:
                # Once prime time is blocked, skip any prime time slots
                if prime_time_blocked and t in PRIME_TIME_SLOTS:
                    log.info(f"Skipping prime time slot {t} (already restricted).")
                    continue

                for court in COURT_PREFERENCE:
                    result = await try_book_slot(t, court)
                    if result == 'success':
                        return True
                    elif result == 'prime_time':
                        log.warning("Prime Time restricted — will skip remaining prime time slots.")
                        prime_time_blocked = True
                        break  # break courts loop, move to next time
                    elif result == 'no_slot':
                        continue  # try next court
                    # other block reason — try next court

            log.error("ALL BOOKED — no slots available.")
            print("\n❌ ALL BOOKED — no slots available for the target date.\n")
            return "ALL_BOOKED"

        except Exception as e:
            log.error(f"Error during booking: {e}", exc_info=True)
            try:
                await page.screenshot(path=f"error_{attempt}.png")
            except:
                pass
            return False

        finally:
            await browser.close()


async def run_booking_job():
    """Try each target date (7→6→5→4 days out). Stop on first success."""
    dates = get_target_dates()
    log.info(f"Will try dates in order: {', '.join(dates)}")

    for target_date in dates:
        log.info(f"--- Trying date: {target_date} ---")
        booked = False

        for attempt in range(1, MAX_RETRIES + 1):
            result = await book_court(target_date=target_date, attempt=attempt)
            if result is True:
                log.info(f"✅ Booking confirmed for {target_date}. Done!")
                return
            elif isinstance(result, str) and result.startswith("ALL_BOOKED"):
                log.info(f"All slots taken on {target_date} — trying previous day.")
                break  # move to next (earlier) date
            else:
                # Transient error — retry same date
                if attempt < MAX_RETRIES:
                    wait_secs = 30 * attempt
                    log.info(f"Transient error — retrying in {wait_secs}s...")
                    await asyncio.sleep(wait_secs)

    log.error("No slots available on any of the target dates (7→4 days out).")
    print("\n❌ ALL BOOKED — no slots on any target date.\n")


def scheduled_job():
    log.info("⏰ Midnight job triggered!")
    asyncio.run(run_booking_job())


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("--help", "-h"):
        print(__doc__)
    elif len(sys.argv) > 1 and sys.argv[1] == "--now":
        log.info("Running immediately (--now flag)...")
        asyncio.run(run_booking_job())
    else:
        log.info("Scheduler started. Will book every night at 12:00 AM.")
        log.info(f"Target dates will be: {get_target_dates()}")
        schedule.every().day.at("00:00").do(scheduled_job)
        while True:
            schedule.run_pending()
            time.sleep(10)
