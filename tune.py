"""Tune reel-strip symbol counts (pay table and features fixed).

Step A: design the 96% master (base + free-spin strips) to a target RTP split.
Step B: derive 94% and 92% by editing BASE strips only (scatter counts and FS strips untouched,
        so feature frequency and feature value are identical across variants).
"""
import numpy as np, json
from game import (analytic, BASE_COUNTS_START, FS_COUNTS, NSYM, W, S, build_strips, scatter_ok)

rng = np.random.default_rng(20261021)
LMIN, LMAX = 34, 48


def valid(c, reel_has_wild=(False, True, True, True, False), sc_range=(1, 2), wild_max=8):
    for r in range(5):
        if (np.diff(c[r, 2:]) < 0).any(): return False      # higher-paying symbols never more common
        if c[r, 2] > 3: return False
        if not reel_has_wild[r] and c[r, W] != 0: return False
        if reel_has_wild[r] and not (1 <= c[r, W] <= wild_max): return False
        if not (sc_range[0] <= c[r, S] <= sc_range[1]): return False
        if (c[r, 2:] < 1).any(): return False
        if not (LMIN <= c[r].sum() <= LMAX): return False
        if c[r].sum() // max(c[r, S], 1) < 3: return False
    return True


def mutate(c, symbols_allowed, allow_len=True):
    c = c.copy()
    r = rng.integers(5)
    kind = rng.random()
    if allow_len and kind < 0.15:
        c[r, rng.choice(symbols_allowed)] += 1
    elif allow_len and kind < 0.30:
        c[r, rng.choice(symbols_allowed)] -= 1
    else:
        a, b = rng.choice(symbols_allowed, 2, replace=False)
        c[r, a] -= 1; c[r, b] += 1
    return c


def anneal(c0, loss, symbols_allowed, iters=60000, T0=1e-3, allow_len=True):
    cur, lc = c0.copy(), loss(c0)
    best, lb = cur.copy(), lc
    for i in range(iters):
        T = T0 * (1 - i / iters) + 1e-9
        cand = mutate(cur, symbols_allowed, allow_len)
        if not valid(cand): continue
        l = loss(cand)
        if l < lc or rng.random() < np.exp((lc - l) / T):
            cur, lc = cand, l
            if l < lb: best, lb = cand.copy(), l
    return best, lb


# ---------------- Step A: 96% master, tune base + FS strips jointly to a target split
TARGET = dict(rtp=0.96, line_base=0.66, scatter_base=0.035, p_trigger=1 / 125, fs_value=33.0)


def lossA(cb, cf):
    a = analytic(cb, cf)
    return (((a["rtp"] - TARGET["rtp"]) / 0.0002) ** 2
            + ((a["line_base"] - TARGET["line_base"]) / 0.01) ** 2
            + ((a["scatter_base"] - TARGET["scatter_base"]) / 0.005) ** 2
            + ((a["p_trigger"] - TARGET["p_trigger"]) / 0.0005) ** 2
            + ((a["fs_value"] - TARGET["fs_value"]) / 2.0) ** 2)


all_syms = np.arange(NSYM)
cb = np.array([[0,1,2,2,3,3,4,4,5,5,5,6],[3,1,2,2,3,3,4,4,4,4,5,5],[3,1,2,2,3,3,4,4,4,4,5,5],
               [3,1,2,2,3,3,4,4,4,4,5,5],[0,1,2,2,3,3,4,4,5,5,5,6]])
cf = np.array([[0,1,2,3,3,3,3,4,4,4,4,5],[6,1,2,2,3,3,3,3,3,3,3,4],[6,1,2,2,3,3,3,3,3,3,3,4],
               [6,1,2,2,3,3,3,3,3,3,3,4],[0,1,2,3,3,3,3,4,4,4,4,5]])
for rnd in range(6):  # alternate base / fs coordinate search
    cb, _ = anneal(cb, lambda c: lossA(c, cf), all_syms, iters=15000, T0=5.0)
    cf, l = anneal(cf, lambda c: lossA(cb, c), all_syms, iters=15000, T0=5.0)
    a = analytic(cb, cf)
    print(f"round {rnd}: loss={l:.4f} rtp={a['rtp']:.6f} base={a['line_base']:.4f} sc={a['scatter_base']:.4f} "
          f"ptrig=1/{1/a['p_trigger']:.1f} fsv={a['fs_value']:.2f}")

# final polish of exact RTP using base non-scatter symbols only
polish = np.array([s for s in all_syms if s != S])
cb, _ = anneal(cb, lambda c: lossA(c, cf), polish, iters=40000, T0=0.5)
a96 = analytic(cb, cf)
print("96 master:", a96["rtp"])

# ---------------- Step B: 94 / 92 from 96 base strips, base strips only, scatters fixed
variants = {"96": cb}
for tgt in (0.94, 0.92):
    def lossB(c, tgt=tgt):
        a = analytic(c, cf)
        return ((a["rtp"] - tgt) / 0.00005) ** 2 + 0.05 * np.abs(c - cb).sum()
    best, lbest = None, 1e18
    for restart in range(4):
        c, l = anneal(cb, lossB, polish, iters=40000, T0=2.0)
        if l < lbest: best, lbest = c, l
    variants[str(int(tgt * 100))] = best
    print(tgt, analytic(best, cf)["rtp"], "edits:", np.abs(best - cb).sum() // 2)

for k, c in variants.items():
    for st in build_strips(c): assert scatter_ok(st)
for st in build_strips(cf): assert scatter_ok(st)
json.dump({"fs_counts": cf.tolist(), "base_counts": {k: v.tolist() for k, v in variants.items()}},
          open("counts.json", "w"), indent=1)
