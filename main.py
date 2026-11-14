# btc-cent-forecast-01: 4-hour-ahead BTC (cbBTC/USDC) point forecast.
#
# Model: shrunk mean reversion to the trailing 24-hour MEDIAN.
#   forecast = last + 0.20 * (median(last 1440 closes) - last)
#   rounded to the price grid (5 decimals) and clamped to (0, 10_000_000).
#
# Why: the score is mean absolute error, so the point forecast should be
# the conditional median. In this pool's 1-minute closes the 4-hour-ahead
# return is negatively related to the price's deviation from its trailing
# 24-hour center (the pool price overshoots its own recent center and
# drifts back). The window median is that center estimated robustly: this
# series is step-like (long flat stretches, then ticks), so a few extreme
# minutes can drag the mean while the median stays on the level the price
# actually traded at.
#
# Evidence (walk-forward on the practice series, reconstructed from the
# six practice cases: 161 forecast origins, 15-minute steps, 240-minute
# horizon, scored exactly as the kit scores, 100 * |guess - actual|):
# this model averages 36,805.6 cents vs 38,788.0 for the previous entry
# (reversion 0.10 to the 24-hour mean) and 41,213.7 for persistence.
# Per fold (six chronological blocks) it beats the previous entry in
# five of six folds; the loss is the one strongly trending fold, where
# every reversion strength does worse. On the five practice checkpoints
# whose answers the released data contains it is worse (48,939.5 vs
# 47,891.5) -- five sparse, overlapping points inside the same series;
# the 161-origin walk-forward is the broader measurement and is what
# this choice rests on.
#
# Deterministic: no randomness, no network, stdlib only. Runs in well
# under a second per case.

import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999
# Trailing window for the center (minutes) and the shrinkage coefficient.
CENTER_WINDOW = 1440
REVERSION = 0.20


def price5(x):
    """x kept on the grid's 5 decimals and inside (0, 10_000_000)."""
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def window_median(window):
    """Median of the window, with the exact definition the walk-forward
    harness measured: the middle value of the sorted window, or the mean
    of the two middle values when the count is even. Written out instead
    of statistics.median so the graded definition is pinned in this file
    and cannot drift with library conventions."""
    ordered = sorted(window)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def forecast(prices):
    if not isinstance(prices, list) or not prices:
        raise ValueError("market has no prices")
    # Keep only finite numbers; a stray non-finite bar must not poison
    # the center or the last price.
    clean = [p for p in prices if isinstance(p, (int, float))
             and not isinstance(p, bool) and math.isfinite(p)]
    if not clean:
        raise ValueError("market has no finite prices")
    last = clean[-1]
    window = clean[-CENTER_WINDOW:]
    center = window_median(window)
    raw = last + REVERSION * (center - last)
    # A non-finite result (overflow on pathological inputs) falls back
    # to the last price rather than poisoning the output.
    if not math.isfinite(raw):
        raw = last
    return price5(raw)


def pick_market(case, name):
    markets = case.get("markets")
    if not isinstance(markets, list) or not markets:
        raise ValueError(f"{name} holds no markets")
    for market in markets:
        if isinstance(market, dict) and market.get("id") == "btc-usdc":
            return market
    if len(markets) == 1:
        return markets[0]
    raise ValueError(f"{name} does not hold exactly one market")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for name in inputs:
        case_id = name[:-len(".in")]
        with open(os.path.join(INPUT_DIR, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        market = pick_market(case, name)
        price = forecast(market.get("prices"))
        out = {"forecasts": [{"case": case_id, "price": price}]}
        with open(os.path.join(OUTPUT_DIR, f"{case_id}.out"), "w",
                  encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
