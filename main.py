# btc-cent-forecast-01: 4-hour-ahead BTC (cbBTC/USDC) point forecast.
#
# Model: shrunk mean reversion to the trailing 24-hour MEAN.
#   forecast = last + 0.30 * (mean(last 1440 closes) - last)
#   rounded to the price grid (5 decimals) and clamped to (0, 10_000_000).
#
# Why: the score is mean absolute error. In this pool's 1-minute closes
# the 4-hour-ahead return is negatively related to the price's deviation
# from its trailing 24-hour center (the pool price overshoots its own
# recent center and drifts back). The first entry reverted 0.10 to the
# mean; a walk-forward sweep then favoured the median at 0.20; extending
# the sweep to stronger shrinkage favours the plain mean at 0.30 -- the
# mean uses every minute in the window, and at this strength the extra
# pull outweighs the median's robustness to the series' step ticks.
#
# Evidence (walk-forward on the practice series, reconstructed from the
# six practice cases: 161 forecast origins, 15-minute steps, 240-minute
# horizon, scored exactly as the kit scores, 100 * |guess - actual|):
# this model averages 36,033.4 cents vs 36,805.6 for the median-0.20
# variant it replaces, 38,788.0 for the first entry (mean, 0.10) and
# 41,213.7 for persistence. Per fold (six chronological blocks) against
# the median-0.20 variant: 29,919.1 vs 33,268.9; 18,736.4 vs 19,167.2;
# 33,709.2 vs 36,168.6; 26,553.8 vs 28,183.2; 74,203.0 vs 70,242.2;
# 33,555.4 vs 34,287.9 -- better in five of six folds; the loss is the
# one strongly trending fold, where every reversion strength does
# worse. On the five practice checkpoints whose
# answers the released data contains it is worse (49,565.3 vs 48,939.5
# and 47,891.5) -- five sparse, overlapping points inside the same
# series; the 161-origin walk-forward is the broader measurement and is
# what this choice rests on.
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
REVERSION = 0.30


def price5(x):
    """x kept on the grid's 5 decimals and inside (0, 10_000_000)."""
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def window_mean(window):
    """Mean of the window, summed with math.fsum so the result is the
    correctly rounded exact sum divided by the count -- the definition
    the walk-forward harness measured (its prefix-sum means agree with
    fsum on every practice case)."""
    return math.fsum(window) / len(window)


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
    center = window_mean(window)
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
