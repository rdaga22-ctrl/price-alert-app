import json
import os
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from candles import closed_candles, combine, NEW_YORK
from smc_alert import Candle, replay
from structure import scan_structure

SYMBOLS = ("EUR/USD", "USD/JPY", "AUD/USD", "GBP/USD",
           "USD/CAD", "EUR/GBP", "XAU/USD")


def fetch(key, interval, count):
    query = urlencode({
        "symbol": ",".join(SYMBOLS),
        "interval": interval,
        "outputsize": count,
        "timezone": "UTC",
        "apikey": key,
    })
    try:
        with urlopen("https://api.twelvedata.com/time_series?" + query,
                     timeout=45) as response:
            data = json.load(response)
    except (OSError, ValueError):
        raise SystemExit(f"Twelve Data request failed for {interval}.") from None

    candles = {}
    for symbol in SYMBOLS:
        result = data.get(symbol, {})
        if result.get("status") != "ok" or not result.get("values"):
            code = result.get("code", data.get("code"))
            detail = f" (code {code})" if isinstance(code, int) else ""
            raise SystemExit(f"No {interval} candle history for {symbol}{detail}.")
        candles[symbol] = result["values"]
    return candles


def as_bars(values, minutes):
    bars = []
    for start, prices in values.items():
        if minutes == 1440:
            end = (start.astimezone(NEW_YORK) + timedelta(days=1)).astimezone(UTC)
        else:
            end = start + timedelta(minutes=minutes)
        bars.append(Candle(int(end.timestamp()) // 60, *prices))
    return bars


def trend_at(changes, end):
    return next((trend for timestamp, trend in reversed(changes)
                 if timestamp <= end), None)


def qualifies(bos, daily, four_hour):
    direction = "bullish" if bos.bullish else "bearish"
    day = trend_at(daily, bos.end)
    if bos.timeframe == "Daily":
        return True
    if bos.timeframe == "4H":
        return day == direction
    return day in (direction, "range") and trend_at(four_hour, bos.end) == direction


def scan(symbol, hourly, five_minute, now):
    hourly = closed_candles(hourly, 60, now)
    five_minute = closed_candles(five_minute, 5, now)
    bars = {
        "Daily": as_bars(combine(hourly, 60, 1440, now), 1440),
        "4H": as_bars(combine(hourly, 60, 240, now), 240),
        "1H": as_bars(hourly, 60),
        "15m": as_bars(combine(five_minute, 5, 15, now), 15),
        "5m": as_bars(five_minute, 5),
    }
    lower = {"Daily": "1H", "4H": "15m", "1H": "5m"}
    results = {frame: scan_structure(symbol, frame, bars[frame])
               for frame in lower}
    report = {}
    for frame, smaller in lower.items():
        setups = [bos for bos in results[frame][1]
                  if qualifies(bos, results["Daily"][0], results["4H"][0])]
        events = [event for bos in setups
                  for event in replay(bos, bars[frame], bars[smaller])]
        report[frame] = (len(bars[frame]), len(setups),
                         sum(event["id"][-1] == "return" for event in events))
    return report


def main():
    key = os.environ.get("TWELVE_DATA_API_KEY")
    if not key:
        raise SystemExit("GitHub could not find the Twelve Data secret.")

    now = datetime.now(UTC)
    hourly = fetch(key, "1h", 1200)
    # Each batch uses seven credits. Separate them for the free plan.
    time.sleep(61)
    five_minute = fetch(key, "5min", 4200)

    for symbol in SYMBOLS:
        report = scan(symbol, hourly[symbol], five_minute[symbol], now)
        for frame, (candles, breaks, returns) in report.items():
            print(f"{symbol} {frame}: {candles} candles, "
                  f"{breaks} qualifying breaks, {returns} qualifying returns")


if __name__ == "__main__":
    main()
