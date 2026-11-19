import json
import os
from datetime import UTC, datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

INDIA = ZoneInfo("Asia/Kolkata")


def alert_text(event):
    symbol, frame, bos_end, bullish, kind = event["id"]
    direction = "Bullish" if bullish else "Bearish"
    headline = "BOS" if kind == "bos" else "zone return"
    bos_time = datetime.fromtimestamp(bos_end * 60, UTC).astimezone(INDIA)
    low, high = event["zone"]
    lines = [
        f"{symbol} • {frame} • {direction} {headline}",
        f"BOS candle closed {bos_time:%d %b %Y, %H:%M} India time",
        f"Zone {low:g}–{high:g}",
    ]
    if kind == "return":
        lines.append(f"Confirmed on {event['lower_minutes']}-minute candles")
        lines.append(f"Price level to watch {event['watch_price']:g}")
    if event.get("daily_unclear"):
        lines.append("Daily trend unclear")
    return "\n".join(lines)


def send_alert(event):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id.isdecimal():
        raise RuntimeError("Check the Telegram secrets in GitHub.")

    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({
            "chat_id": int(chat_id),
            "text": alert_text(event),
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except (OSError, ValueError):
        raise RuntimeError("Telegram could not send the alert.") from None

    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the alert.")
