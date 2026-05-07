"""
Login and availability scraping for openresa.com / TC Sweet Spot.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

BASE_URL = "https://openresa.com"
BERLIN_TZ = pytz.timezone("Europe/Berlin")

# Court schedule IDs on openresa.com
COURT_IDS = {
    "70562": "Court 1",
    "70563": "Court 2",
    "70564": "Court 3",
}

# Target window: 18:00–21:00 in minutes from midnight
TIME_START_MIN = 18 * 60   # 1080
TIME_START_MAX = 21 * 60   # 1260  (slot must START before 21:00)


def login(username: str, password: str) -> requests.Session:
    """Log in to openresa.com and return an authenticated session."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    # GET the club page to obtain CSRF token and club_id
    resp = session.get(f"{BASE_URL}/club/tcsweetspot")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    auth_form = soup.find("form", id="auth-form")
    if not auth_form:
        raise RuntimeError("Login form not found on page")

    csrf_input = auth_form.find("input", attrs={"name": lambda n: n and "csrf" in n})
    club_id_input = auth_form.find("input", attrs={"name": "club_id"})

    if not csrf_input or not club_id_input:
        raise RuntimeError("CSRF token or club_id not found in login form")

    data = {
        "username": username,
        "password": password,
        "cookie_enabled": "true",
        "club_id": club_id_input["value"],
        csrf_input["name"]: csrf_input["value"],
        "remember": "1",
    }

    login_resp = session.post(
        f"{BASE_URL}/auth/login/from/club-home",
        data=data,
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/club/tcsweetspot",
        },
    )
    login_resp.raise_for_status()

    result = login_resp.json()
    if not result.get("success"):
        raise RuntimeError(f"Login failed: {result}")

    return session


def get_slots_for_date(session: requests.Session, date_offset: int) -> list[dict]:
    """
    Fetch available slots for a given day offset from today (Berlin time).
    Returns a list of slot dicts for Courts 1–3 between 18:00–21:00.
    """
    resp = session.get(
        f"{BASE_URL}/reservation/day",
        params={"date": date_offset, "group": 0},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract the date label from the page
    date_header = soup.find("div", class_="visible-print")
    date_label = date_header.get_text(strip=True) if date_header else f"Day +{date_offset}"

    available = []
    for slot in soup.find_all("a", class_="slot"):
        classes = slot.get("class", [])
        schedule_id = slot.get("data-schedule", "")

        # Only Courts 1, 2, 3
        if schedule_id not in COURT_IDS:
            continue

        # Only fully free/bookable slots
        if "slot-free-full" not in classes:
            continue

        timestart = int(slot.get("data-timestart", 0))
        duration = int(slot.get("data-duration", 60))

        # Only slots starting within 18:00–21:00 window
        if timestart < TIME_START_MIN or timestart >= TIME_START_MAX:
            continue

        start_h, start_m = divmod(timestart, 60)
        end_total = timestart + duration
        end_h, end_m = divmod(end_total, 60)

        available.append({
            "court": COURT_IDS[schedule_id],
            "schedule_id": schedule_id,
            "date_label": date_label,
            "date_offset": date_offset,
            "timestart": timestart,
            "duration": duration,
            "time_str": f"{start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}",
            # Stable unique key for state tracking
            "key": f"{schedule_id}|{date_label}|{timestart}",
        })

    return available


def get_weekend_offsets() -> list[int]:
    """
    Return date offsets for the coming Friday, Saturday, Sunday
    relative to today in Berlin time.
    """
    today_weekday = datetime.now(BERLIN_TZ).weekday()  # Mon=0 … Sun=6
    # Friday=4, Saturday=5, Sunday=6
    offsets = []
    for target in (4, 5, 6):
        diff = (target - today_weekday) % 7
        offsets.append(diff)
    return offsets


def get_all_weekend_slots(session: requests.Session) -> list[dict]:
    """Return available slots for the full coming weekend (Fri–Sun)."""
    all_slots = []
    for offset in get_weekend_offsets():
        all_slots.extend(get_slots_for_date(session, offset))
    return all_slots
