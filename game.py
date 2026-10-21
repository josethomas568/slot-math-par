"""Game definition and fast exact (analytic) evaluator for 'Lucky Sevens 20' — a 5x3, 20-line video slot.

Units: 1 credit = 1 line bet. Total bet = 20 credits. All pays are integers in credits.
"""
from __future__ import annotations
import json
import numpy as np

# ----------------------------------------------------------------------------- symbols
SYMBOLS = ["WILD", "STAR", "SEVEN", "BAR", "BELL", "MELON", "PLUM", "A", "K", "Q", "J", "10"]
W, S = 0, 1                      # wild, scatter indices
NSYM = len(SYMBOLS)
NREELS, NROWS, NLINES = 5, 3, 20
BET = NLINES                     # total bet in credits

# Line pay table (multiples of line bet) for 2,3,4,5 of a kind, left to right, adjacent reels.
# WILD substitutes for every symbol except STAR, appears on reels 2-4 only, has no pay of its own.
LINE_PAYS = {
    "SEVEN": (2, 50, 250, 1000),
    "BAR":   (0, 30, 120, 500),
    "BELL":  (0, 20, 80, 300),
    "MELON": (0, 15, 50, 150),
    "PLUM":  (0, 10, 40, 125),
    "A":     (0, 5, 25, 100),
    "K":     (0, 5, 20, 80),
    "Q":     (0, 5, 15, 60),
    "J":     (0, 4, 10, 50),
    "10":    (0, 4, 10, 40),
}
# pay[s, n] for n = 0..5 symbols in a row (credits per line bet)
PAY = np.zeros((NSYM, 6), dtype=np.int64)
for name, p in LINE_PAYS.items():
    PAY[SYMBOLS.index(name), 2:6] = p

# Scatter (STAR) pays anywhere, multiples of TOTAL bet, for 3/4/5 visible.  3+ triggers free spins.
SCATTER_PAY_X = {3: 2, 4: 10, 5: 100}
SC_PAY = np.zeros(6, dtype=np.int64)         # in credits
for k, x in SCATTER_PAY_X.items():
    SC_PAY[k] = x * BET

# Free-spin feature
FS_AWARD = 10            # spins awarded by 3+ STAR (trigger and retrigger)
FS_MULT = 3              # all free-spin wins (line + scatter) multiplied
FS_MAX_SPINS = 50        # total spins per feature capped at 50 (i.e. at most 4 retriggers)
MAX_WIN_X = 5000         # max win per game round (base spin + its feature) = 5,000x total bet
MAX_WIN = MAX_WIN_X * BET

# 20 paylines: row index (0 top, 1 middle, 2 bottom) on reels 1..5
LINES = np.array([
    [1, 1, 1, 1, 1], [0, 0, 0, 0, 0], [2, 2, 2, 2, 2], [0, 1, 2, 1, 0], [2, 1, 0, 1, 2],
    [0, 0, 1, 2, 2], [2, 2, 1, 0, 0], [1, 0, 0, 0, 1], [1, 2, 2, 2, 1], [0, 1, 1, 1, 0],
    [2, 1, 1, 1, 2], [1, 0, 1, 2, 1], [1, 2, 1, 0, 1], [0, 1, 0, 1, 0], [2, 1, 2, 1, 2],
    [1, 1, 0, 1, 1], [1, 1, 2, 1, 1], [0, 2, 0, 2, 0], [2, 0, 2, 0, 2], [0, 2, 2, 2, 0],
], dtype=np.int64)
assert len({tuple(l) for l in LINES}) == NLINES

# ----------------------------------------------------------------------------- reel strips
# Symbol counts per reel, order = SYMBOLS.  Strips are generated from counts by build_strip().
FS_COUNTS = np.array([
    # W  S  7  BAR BELL MEL PLUM A  K  Q  J  10
    [0, 1, 3, 3, 4, 4, 4, 3, 4, 4, 3, 3],
    [3, 1, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3],
    [3, 1, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3],
    [3, 1, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3],
    [0, 1, 3, 3, 4, 4, 4, 3, 4, 4, 3, 3],
], dtype=np.int64)

BASE_COUNTS_START = np.array([
    [0, 1, 2, 3, 3, 4, 4, 4, 5, 5, 5, 4],
    [2, 1, 2, 3, 3, 4, 4, 4, 4, 5, 4, 4],
    [2, 1, 2, 3, 3, 4, 4, 4, 4, 5, 4, 4],
    [2, 1, 2, 3, 3, 4, 4, 4, 4, 5, 4, 4],
    [0, 1, 2, 3, 3, 4, 4, 4, 5, 5, 5, 4],
], dtype=np.int64)


def build_strip(counts: np.ndarray) -> np.ndarray:
    """Deterministically lay out one reel strip from symbol counts.

    STARs are placed evenly (spacing >= 3 so at most one is ever visible in the 3-row window);
    remaining symbols are interleaved by their ideal fractional positions so no symbol clumps.
    """
    L = int(counts.sum())
    strip = -np.ones(L, dtype=np.int64)
    n_sc = int(counts[S])
    if n_sc:
        assert L // n_sc >= 3, "scatters too dense for one-per-window"
        for i in range(n_sc):
            strip[(i * L) // n_sc] = S
    keys = []
    for s in range(NSYM):
        if s == S:
            continue
        c = int(counts[s])
        for i in range(c):
            # ideal position (i + offset)/c, offset staggered per symbol to avoid ties
            keys.append(((i + 0.5 + 0.37 * s / NSYM) / c, s))
    keys.sort()
    free = [p for p in range(L) if strip[p] < 0]
    for p, (_, s) in zip(free, keys):
        strip[p] = s
    return strip


def build_strips(counts):
    return [build_strip(c) for c in counts]


def strip_counts(strips):
    return np.array([np.bincount(s, minlength=NSYM) for s in strips], dtype=np.int64)


def scatter_ok(strip) -> bool:
    """True if no 3-row window (circular) shows more than one STAR."""
    L = len(strip)
    return all(sum(strip[(p + r) % L] == S for r in range(NROWS)) <= 1 for p in range(L))


# ----------------------------------------------------------------------------- analytic exact model
def line_ev_table(counts):
    """Exact probability of each (symbol, n-of-a-kind) on ONE payline, from strip counts.

    Valid because each payline reads exactly one cell per reel and every reel stop is equally
    likely, so the symbol in any fixed row of reel r is distributed as reel r's symbol frequencies.
    Returns prob[s, n] and the expected line pay per line bet (= line-pay contribution to RTP).
    """
    c = counts.astype(float)
    T = c.sum(axis=1)
    w = c[:, W]
    prob = np.zeros((NSYM, 6))
    for s in range(2, NSYM):
        m = [c[0, s]] + [c[r, s] + w[r] for r in range(1, NREELS)]   # matches incl. wild (reel1 has none)
        f = [mm / T[r] for r, mm in enumerate(m)]
        for n in range(2, 6):
            p = np.prod(f[:n])
            if n < 5:
                p *= (1 - f[n])
            prob[s, n] = p
    return prob, float((prob * PAY).sum())


def scatter_dist(counts):
    """P(k STARs visible), k=0..5 — Poisson-binomial over reels with p_r = 3*n_r/L_r."""
    p = NROWS * counts[:, S] / counts.sum(axis=1)
    d = np.zeros(6); d[0] = 1.0
    for pr in p:
        d[1:] = d[1:] * (1 - pr) + d[:-1] * pr
        d[0] *= (1 - pr)
    return d


def fs_expected_spins(q):
    """Markov chain over (spins played t, retriggers r) with the 50-spin cap. Returns E[spins] and P(r)."""
    max_r = FS_MAX_SPINS // FS_AWARD - 1
    P = np.zeros(max_r + 1); P[0] = 1.0
    E = 0.0
    for t in range(FS_MAX_SPINS):
        alive = np.array([t < FS_AWARD * (1 + r) for r in range(max_r + 1)])
        E += P[alive].sum()
        newP = np.where(alive, 0.0, P)              # finished states keep their mass
        a = np.where(alive, P, 0.0)
        newP += a * (1 - q)
        newP[1:] += a[:-1] * q
        newP[max_r] += a[max_r] * q                  # retrigger at cap: no extra spins
        P = newP
    return E, P


def analytic(base_counts, fs_counts=FS_COUNTS):
    """Exact theoretical RTP (before the 5,000x round cap) from strip counts."""
    pb, line_b = line_ev_table(base_counts)
    pf, line_f = line_ev_table(fs_counts)
    db, df = scatter_dist(base_counts), scatter_dist(fs_counts)
    sc_b = float((db * SC_PAY).sum()) / BET
    sc_f = float((df * SC_PAY).sum()) / BET
    p_trig = float(db[3:].sum())
    q = float(df[3:].sum())
    E_spins, _ = fs_expected_spins(q)
    fs_spin_ev = FS_MULT * (line_f + sc_f)           # per free spin, in units of total bet
    fs_value = E_spins * fs_spin_ev                  # per feature, units of total bet
    return dict(line_base=line_b, scatter_base=sc_b, p_trigger=p_trig, q_retrigger=q,
                E_spins=E_spins, fs_spin_ev=fs_spin_ev, fs_value=fs_value,
                fs_rtp=p_trig * fs_value, rtp=line_b + sc_b + p_trig * fs_value,
                line_prob_base=pb, line_prob_fs=pf, line_fs=line_f, scatter_fs=sc_f)


def save_design(path, variants):
    out = {"symbols": SYMBOLS, "line_pays": LINE_PAYS, "scatter_pay_x_total_bet": SCATTER_PAY_X,
           "lines": LINES.tolist(), "fs": dict(award=FS_AWARD, mult=FS_MULT, max_spins=FS_MAX_SPINS),
           "max_win_x": MAX_WIN_X, "fs_strips": [s.tolist() for s in build_strips(FS_COUNTS)],
           "variants": {k: [s.tolist() for s in v] for k, v in variants.items()}}
    with open(path, "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    a = analytic(BASE_COUNTS_START)
    for k in ["line_base", "scatter_base", "p_trigger", "q_retrigger", "E_spins", "fs_spin_ev", "fs_value", "fs_rtp", "rtp"]:
        print(f"{k:14s} {a[k]:.6f}")
    for st in build_strips(BASE_COUNTS_START) + build_strips(FS_COUNTS):
        assert scatter_ok(st)
