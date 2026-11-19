from dataclasses import dataclass

LOWER_MINUTES = {"Daily": 60, "4H": 15, "1H": 5}


@dataclass(frozen=True)
class Candle:
    end: int  # UTC timestamp in minutes
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Break:
    symbol: str
    timeframe: str
    end: int
    bullish: bool
    low: float
    high: float
    impulse_bars: int


def overlaps(candle, low, high):
    return candle.low <= high and candle.high >= low


def invalidated(candle, bullish, low, high):
    return candle.close < low if bullish else candle.close > high


def replay(setup, higher, lower):
    """Read completed candles from oldest to newest."""
    minutes = LOWER_MINUTES[setup.timeframe]
    key = (setup.symbol, setup.timeframe, setup.end, setup.bullish)
    events = [{"id": (*key, "bos"), "zone": (setup.low, setup.high)}]

    inside = False
    armed_at = None
    later_bars = (bar for bar in higher if bar.end > setup.end)
    for count, candle in enumerate(later_bars, 1):
        if invalidated(candle, setup.bullish, setup.low, setup.high):
            break
        touching = overlaps(candle, setup.low, setup.high)
        if touching and not inside and count > setup.impulse_bars:
            armed_at = candle.end
            break
        inside = touching
    if armed_at is None:
        return events

    parent_bars = iter(bar for bar in higher if bar.end > armed_at)
    parent = next(parent_bars, None)
    pivot = None
    block = None
    for index, candle in enumerate(lower):
        if candle.end <= armed_at:
            continue
        while parent is not None and parent.end <= candle.end:
            if invalidated(parent, setup.bullish, setup.low, setup.high):
                return events
            parent = next(parent_bars, None)

        if block is not None:
            if invalidated(candle, setup.bullish, block.low, block.high):
                block = None
            elif overlaps(candle, block.low, block.high):
                events.append({
                    "id": (*key, "return"),
                    "lower_minutes": minutes,
                    "zone": (block.low, block.high),
                    "watch_price": block.high if setup.bullish else block.low,
                    "end": candle.end,
                })
                return events

        if index < 4:
            continue
        window = lower[index - 4:index + 1]
        if any(b.end - a.end != minutes for a, b in zip(window, window[1:])):
            pivot = None
            continue

        center = window[2]
        neighbors = window[:2] + window[3:]
        level = center.high if setup.bullish else center.low
        if all(level > bar.high if setup.bullish else level < bar.low for bar in neighbors):
            pivot = (index - 2, level)
        if block is not None or pivot is None:
            continue

        pivot_index, level = pivot
        previous = lower[index - 1]
        crossed = (
            previous.close <= level < candle.close if setup.bullish
            else previous.close >= level > candle.close
        )
        if not crossed:
            continue

        for candidate in reversed(lower[pivot_index + 1:index]):
            opposite = (
                candidate.close < candidate.open if setup.bullish
                else candidate.close > candidate.open
            )
            if opposite:
                if candidate.end > armed_at and setup.low <= candidate.low <= candidate.high <= setup.high:
                    block = candidate
                break
    return events
