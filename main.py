"""
Main entry point for TC Sweet Spot court availability checker.

Usage:
  python main.py --mode=weekly    # Thursday 8am: send overview, start monitoring
  python main.py --mode=monitor   # Every 30min Fri–Sun: alert on new slots
  python main.py --mode=stop      # Sunday 10pm: disable monitoring
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytz

from scraper import login, get_all_weekend_slots
from notify import send_weekly_overview, send_new_slot_alert

STATE_FILE = Path(__file__).parent / "state.json"
BERLIN_TZ = pytz.timezone("Europe/Berlin")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"monitoring_active": False, "seen_keys": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mode_weekly() -> None:
    """Thursday: send full weekend overview and activate monitoring."""
    username = os.environ["OPENRESA_USERNAME"]
    password = os.environ["OPENRESA_PASSWORD"]

    print("Logging in to openresa.com...")
    session = login(username, password)

    print("Fetching weekend availability...")
    slots = get_all_weekend_slots(session)

    print(f"Found {len(slots)} available slots. Sending overview email...")
    send_weekly_overview(slots)

    # Save all currently seen slot keys so monitor can detect new ones
    state = {
        "monitoring_active": True,
        "seen_keys": [s["key"] for s in slots],
        "last_weekly_run": datetime.now(BERLIN_TZ).isoformat(),
    }
    save_state(state)
    print("State saved. Monitoring activated.")


def mode_monitor() -> None:
    """Every 30min Fri–Sun: check for newly available slots and alert."""
    now_berlin = datetime.now(BERLIN_TZ)

    state = load_state()
    if not state.get("monitoring_active"):
        print("Monitoring not active. Skipping.")
        return

    # Safety check: stop after Sunday 22:00 Berlin
    if now_berlin.weekday() == 6 and now_berlin.hour >= 22:
        print("Sunday 22:00+ reached. Deactivating monitoring.")
        state["monitoring_active"] = False
        save_state(state)
        return

    username = os.environ["OPENRESA_USERNAME"]
    password = os.environ["OPENRESA_PASSWORD"]

    print(f"Monitoring check at {now_berlin.strftime('%a %d %b %H:%M')} Berlin time...")
    session = login(username, password)
    current_slots = get_all_weekend_slots(session)

    seen_keys = set(state.get("seen_keys", []))
    new_slots = [s for s in current_slots if s["key"] not in seen_keys]

    if new_slots:
        print(f"{len(new_slots)} new slot(s) found! Sending alert...")
        send_new_slot_alert(new_slots)
    else:
        print("No new slots since last check.")

    # Update state with all currently seen keys
    state["seen_keys"] = [s["key"] for s in current_slots]
    state["last_monitor_run"] = now_berlin.isoformat()
    save_state(state)


def mode_stop() -> None:
    """Sunday 10pm: deactivate monitoring."""
    state = load_state()
    state["monitoring_active"] = False
    state["stopped_at"] = datetime.now(BERLIN_TZ).isoformat()
    save_state(state)
    print("Monitoring deactivated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="TC Sweet Spot court availability checker")
    parser.add_argument(
        "--mode",
        choices=["weekly", "monitor", "stop"],
        required=True,
        help="weekly: Thursday overview | monitor: 30-min check | stop: end monitoring",
    )
    args = parser.parse_args()

    if args.mode == "weekly":
        mode_weekly()
    elif args.mode == "monitor":
        mode_monitor()
    elif args.mode == "stop":
        mode_stop()


if __name__ == "__main__":
    main()
