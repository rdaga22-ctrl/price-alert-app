import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from scan_market import SYMBOLS, fetch, scan
from telegram_alerts import send_alert

STATE = Path("alert-state.json")
PENDING = Path(os.environ.get("RUNNER_TEMP", ".")) / "price-alert-pending.json"


def prepare():
    now = datetime.now(UTC)
    minute = int(now.timestamp()) // 60
    if not STATE.exists():
        STATE.write_text(json.dumps({
            "started": minute,
            "checked": minute,
            "queued": {},
        }) + "\n")
        PENDING.write_text("[]\n")
        print("Starting time saved. Historical alerts skipped.")
        return

    state = json.loads(STATE.read_text())
    key = os.environ.get("TWELVE_DATA_API_KEY")
    if not key:
        raise SystemExit("GitHub could not find the Twelve Data secret.")

    hourly = fetch(key, "1h", 1200)
    time.sleep(61)
    five_minute = fetch(key, "5min", 4200)

    events = []
    for symbol in SYMBOLS:
        scan(symbol, hourly[symbol], five_minute[symbol], now, events)

    cutoff = max(state["started"], state["checked"] - 10)
    queued = {
        event_id: stamp for event_id, stamp in state["queued"].items()
        if stamp > cutoff
    }
    pending = []
    for event in sorted(events, key=lambda item: item.get("end", item["id"][2])):
        stamp = event.get("end", event["id"][2])
        event_id = json.dumps(event["id"], separators=(",", ":"))
        if cutoff < stamp <= minute and event_id not in queued:
            pending.append(event)
            queued[event_id] = stamp

    state.update(checked=minute, queued=queued)
    STATE.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n")
    PENDING.write_text(json.dumps(pending) + "\n")
    print(f"{len(pending)} new alerts prepared.")


def deliver():
    for event in json.loads(PENDING.read_text()):
        send_alert(event)
    print("Telegram delivery step finished.")


if __name__ == "__main__":
    if sys.argv[1:] == ["prepare"]:
        prepare()
    elif sys.argv[1:] == ["deliver"]:
        deliver()
    else:
        raise SystemExit("Choose prepare or deliver.")
