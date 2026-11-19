from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


def closed_candles(values, minutes, now):
    period = timedelta(minutes=minutes)
    candles = {}
    for row in values:
        start = datetime.fromisoformat(row["datetime"]).replace(tzinfo=UTC)
        if start + period <= now:
            candles[start] = tuple(
                float(row[field]) for field in ("open", "high", "low", "close")
            )
    return dict(sorted(candles.items()))


def window_start(start, minutes):
    if minutes < 240:
        return start.replace(
            minute=start.minute // minutes * minutes, second=0, microsecond=0
        )
    local = start.astimezone(NEW_YORK)
    daily = local.replace(hour=17, minute=0, second=0, microsecond=0)
    if local < daily:
        daily -= timedelta(days=1)
    daily = daily.astimezone(UTC)
    if minutes == 1440:
        return daily
    period = timedelta(minutes=minutes)
    return daily + ((start - daily) // period) * period


def combine(candles, source_minutes, target_minutes, now):
    if (source_minutes, target_minutes) not in {(5, 15), (60, 240), (60, 1440)}:
        raise ValueError("Unsupported candle sizes")
    period = timedelta(minutes=source_minutes)
    groups = {}
    for start, prices in sorted(candles.items()):
        group = window_start(start, target_minutes)
        groups.setdefault(group, {})[start] = prices

    combined = {}
    for start, group in groups.items():
        if target_minutes == 1440:
            end = (start.astimezone(NEW_YORK) + timedelta(days=1)).astimezone(UTC)
        else:
            end = start + timedelta(minutes=target_minutes)
        if end > now:
            continue
        expected = [start + index * period for index in range((end - start) // period)]
        if not all(timestamp in group for timestamp in expected):
            continue
        prices = [group[timestamp] for timestamp in expected]
        combined[start] = (
            prices[0][0], max(p[1] for p in prices),
            min(p[2] for p in prices), prices[-1][3],
        )
    return combined
