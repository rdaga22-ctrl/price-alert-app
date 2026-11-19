from smc_alert import Break


def scan_structure(symbol, timeframe, candles):
    """Return trend changes and continuation breaks from closed candles."""
    highs, lows, changes, breaks = [], [], [], []
    consumed = set()
    previous_trend = None

    for index in range(4, len(candles)):
        candle = candles[index]
        pivot = index - 2
        middle = candles[pivot]
        neighbors = candles[index - 4:pivot] + candles[pivot + 1:index + 1]
        if all(middle.high > bar.high for bar in neighbors):
            highs.append(pivot)
        if all(middle.low < bar.low for bar in neighbors):
            lows.append(pivot)
        if len(highs) < 2 or len(lows) < 2:
            continue

        old_high, high = (candles[i].high for i in highs[-2:])
        old_low, low = (candles[i].low for i in lows[-2:])
        trend = "range"
        if high > old_high and low > old_low:
            trend = "bullish"
        elif high < old_high and low < old_low:
            trend = "bearish"
        if trend != previous_trend:
            changes.append((candle.end, trend))
            previous_trend = trend
        if trend == "range":
            continue

        bullish = trend == "bullish"
        level_index = highs[-1] if bullish else lows[-1]
        origin = lows[-1] if bullish else highs[-1]
        level = high if bullish else low
        previous_close = candles[index - 1].close
        crossed = (
            previous_close <= level < candle.close if bullish
            else previous_close >= level > candle.close
        )
        key = (bullish, level_index)
        if not crossed or key in consumed or not (level_index < origin < index):
            continue
        consumed.add(key)
        if origin < 14:
            continue

        before = candles[origin - 14:origin]
        threshold = 1.5 * sum(abs(bar.close - bar.open) for bar in before) / 14
        move = candles[origin + 1:index + 1]
        bodies = [
            bar.close - bar.open if bullish else bar.open - bar.close
            for bar in move
        ]
        largest_body = max(bodies)
        if largest_body <= 0 or largest_body < threshold:
            continue

        zone = candles[origin]
        breaks.append(Break(
            symbol, timeframe, candle.end, bullish,
            zone.low, zone.high, len(move),
        ))

    return changes, breaks
