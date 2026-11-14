# btc-cent-forecast-01: 4-hour-ahead BTC (cbBTC/USDC) point forecast.
#
# Model: shrunk mean reversion to the trailing 24-hour mean.
#   forecast = last + 0.10 * (mean(last 1440 closes) - last)
#   rounded to the price grid (5 decimals) and clamped to (0, 10_000_000).
#
# Why: the score is mean absolute error, so the point forecast should be
# the conditional median. BTC's 4-hour returns are close to a martingale,
# but in this pool's 1-minute closes the 4-hour-ahead return is negatively
# related to the price's deviation from its trailing 24-hour mean (the
# pool price overshoots its own recent mean and drifts back). The raw
# relation is regime-dependent -- it wins in choppy/range-bound windows
# and loses in steady trends -- so the coefficient is shrunk to 0.10:
# walk-forward (15-minute steps, 240-minute horizon) over three disjoint
# 4-day windows (the practice window Nov 7-11 plus two Coinbase BTC-USD
# windows Oct 30-Nov 3 and Nov 3-7) gave, vs persistence:
#   practice: -3.2%, Oct 30-Nov 3: +3.8%, Nov 3-7: -10.2%.
# A larger coefficient wins more in choppy windows but loses much more
# in trending ones (a=0.20: +7.6% worst case); 0.10 is the min-max pick.
# Pure persistence ties the house baseline exactly and therefore cannot
# take a prize (a prize needs a strictly lower score), so a small,
# evidence-backed deviation is the right play.
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
# Trailing window for the mean (minutes) and the shrinkage coefficient.
MEAN_WINDOW = 1440
REVERSION = 0.10


def price5(x):
    """x kept on the grid's 5 decimals and inside (0, 10_000_000)."""
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def forecast(prices):
    if not isinstance(prices, list) or not prices:
        raise ValueError("market has no prices")
    # Keep only finite numbers; a stray non-finite bar must not poison
    # the mean or the last price.
    clean = [p for p in prices if isinstance(p, (int, float))
             and not isinstance(p, bool) and math.isfinite(p)]
    if not clean:
        raise ValueError("market has no finite prices")
    last = clean[-1]
    window = clean[-MEAN_WINDOW:]
    # fsum keeps the 1440-term mean accurate to the last ulp instead of
    # accumulating float rounding the way sum() does.
    mean24 = math.fsum(window) / len(window)
    raw = last + REVERSION * (mean24 - last)
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
