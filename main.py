# polymarket-nvidia-ceo-forecast-01 entry (Python 3.13, standard library only).
#
# Forecasts the Yes price of every market of Polymarket's "Next CEO of
# NVIDIA?" event at every minute of the 4 hours after a checkpoint: for each
# market and each of the 240 minutes, five quantiles (5%, 25%, 50%, 75%, 95%).
#
# Method — per market, from that market's own price history only:
#
#   * The median forecast is persistence: the price at the checkpoint.
#     (Checked on the practice history: a price that jumps at the checkpoint
#     keeps its new level; pulling the median back toward a recent median,
#     or toward the empirical median change, both scored worse.)
#   * The spread around the median is a 50/50 blend of two estimates:
#       1. Empirical: for a set of horizon anchors h, the quantiles of the
#          market's own h-minute price changes over the last 12 hours
#          (720 minutes), centred on their median and interpolated in
#          log(h). This captures the real shape of the moves — prices sit
#          still for minutes, then tick, then occasionally jump — including
#          their asymmetry (a market near 0 can only really jump up) and
#          the way the spread saturates instead of growing like sqrt(h)
#          forever. The changes are recency-weighted (exponential decay,
#          half-life 120 minutes): volatility regimes change — a market
#          that just jumped is likelier to jump again than one quiet for
#          hours — so recent moves count more than old ones.
#       2. Normal: z_tau * 0.0015 * sqrt(h), the house baseline's shape.
#          It regularises the empirical quantiles, which are noisy for
#          young markets and at long horizons, and guarantees a sane
#          spread even when a market has barely moved in the last 12h.
#   * The blend is scaled by 0.8, and the outer (5% / 95%) quantiles are
#     widened by a further 1.3: the move distribution is heavy-tailed, so
#     the tails need relatively more room than the quartiles.
#   * Every quantile is clamped to [0, 1], forced non-decreasing within a
#     row, and rounded to 6 decimals.
#
# Tuning (practice cases p00-p04, whose answers are recoverable from the
# next case's input, plus pseudo-cases cut from the last 24h of each
# practice case's history): this scored a mean pinball loss of ~0.333 on the
# five real practice cases, against ~0.393 for the house baseline, and
# ~0.560 vs ~0.565 on the twelve pseudo-cases. Parameters were chosen at
# the flat middle of the grid (window 720, tail 0.8, blend 0.5, sigma
# 0.0015, outer 1.3, recency half-life 120), not at a sharp optimum, so the
# result does not hinge on one tuned number. (Revision 2: recency
# weighting replaced the unweighted empirical quantiles after the kit
# check failed thinking_revised; horizon-shrink variants were tested and
# rejected — they won on the five real cases but lost on the pseudo-cases.)
#
# Runs offline, deterministic (no randomness, no time, no network), well
# inside the 8-second per-case cap: per market it sorts at most 720
# numbers at each of 13 horizon anchors.
#
# Usage (grader): python3 /bot/main.py  (reads /input, writes /output)
# Local:  mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py

import json
import math
import os
from bisect import bisect_left

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]

# Tuned constants (see header).
WINDOW = 720            # minutes of recent history for empirical changes
ANCHORS = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 240)
NORM_SIGMA = 0.0015    # normal spread per sqrt(minute)
BLEND = 0.5             # weight of the normal spread in the blend
TAIL = 0.8              # overall shrink of the blended spread
OUTER = 1.3             # extra widening of the 5% / 95% quantiles
MIN_SAMPLES = 20        # extra points beyond h an anchor needs to count
HL = 120                # recency half-life (minutes) for empirical changes


def _wquantile(pairs, tau):
    """Weighted linear-interpolation quantile of (value, weight) pairs."""
    pairs = sorted(pairs)
    tot = sum(w for _, w in pairs)
    if tot <= 0 or len(pairs) == 1:
        return pairs[0][0]
    target = tau * tot
    acc = 0.0
    for i, (v, w) in enumerate(pairs):
        prev_acc = acc
        prev_v = pairs[i - 1][0] if i else v
        acc += w
        if acc >= target:
            if i == 0:
                return v
            frac = (target - prev_acc) / w if w > 0 else 0.0
            return prev_v * (1.0 - frac) + v * frac
    return pairs[-1][0]


def _quantile(sorted_vals, tau):
    """Linear-interpolation quantile of an already-sorted list."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _interp(x, xs, ys):
    """Piecewise-linear interpolation in x, flat outside [xs[0], xs[-1]]."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = bisect_left(xs, x)
    if xs[i] == x:
        return ys[i]
    x0, x1 = xs[i - 1], xs[i]
    y0, y1 = ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)) * 1e6) / 1e6 + 0.0


def forecast_market(prices, horizon):
    """240 (or `horizon`) rows of five quantiles for one market."""
    if not prices:
        x = 0.5
        use = []
    else:
        x = prices[-1]
        use = prices[-WINDOW:] if len(prices) > WINDOW else prices

    # Empirical h-step change quantiles, centred on their median, per anchor.
    anchor_log = []
    anchor_off = []  # list of 5 offsets per anchor
    n_use = len(use)
    for h in ANCHORS:
        if n_use <= h + MIN_SAMPLES:
            continue
        pairs = [(use[i + h] - use[i], 0.5 ** ((n_use - 1 - (i + h)) / HL))
                 for i in range(n_use - h)]
        qs = [_wquantile(pairs, tau) for tau in QUANTILES]
        med = qs[2]
        anchor_log.append(math.log(h))
        anchor_off.append([q - med for q in qs])

    sqrt_h = [math.sqrt(h) for h in range(1, horizon + 1)]
    log_h = [math.log(h) for h in range(1, horizon + 1)]

    rows = []
    for idx in range(horizon):
        row = []
        for j in range(5):
            if anchor_off:
                emp = _interp(
                    log_h[idx], anchor_log, [off[j] for off in anchor_off]
                )
            else:
                emp = 0.0
            norm = Z[j] * NORM_SIGMA * sqrt_h[idx]
            spread = (1.0 - BLEND) * emp + BLEND * norm
            if j == 0 or j == 4:
                spread *= OUTER
            row.append(x + TAIL * spread)
        # Clamp, round, and enforce non-decreasing within the row.
        row = [_price6(v) for v in row]
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for fname in inputs:
        case_id = fname[: -len(".in")]
        with open(os.path.join(INPUT_DIR, fname), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        horizon = int(case.get("horizon_minutes", 240))
        forecasts = [
            {"id": m["id"], "q": forecast_market(m.get("prices") or [], horizon)}
            for m in case["markets"]
        ]
        out_path = os.path.join(OUTPUT_DIR, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"forecasts": forecasts}) + "\n")


if __name__ == "__main__":
    main()
