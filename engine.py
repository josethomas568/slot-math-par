"""Numba kernels: full-cycle enumeration and Monte Carlo simulation (shared spin evaluator)."""
import numpy as np
from numba import njit, prange
from game import PAY, SC_PAY, LINES, NSYM, NREELS, NROWS, W, S, MAX_WIN, FS_AWARD, FS_MULT, FS_MAX_SPINS

MAXB = int(PAY.max() * len(LINES) + SC_PAY.max() + 1)   # bound on raw single-spin win (credits)


def windows(strips):
    """win[r, stop, row] = symbol shown; lens[r] = strip length."""
    Lmax = max(len(s) for s in strips)
    win = np.zeros((NREELS, Lmax, NROWS), dtype=np.int64)
    lens = np.array([len(s) for s in strips], dtype=np.int64)
    for r, s in enumerate(strips):
        L = len(s)
        for p in range(L):
            for k in range(NROWS):
                win[r, p, k] = s[(p + k) % L]
    return win, lens


@njit(cache=True, inline="always")
def eval_spin(win, st0, st1, st2, st3, st4, lines, pay, sc_pay, sym_pay, sym_hit):
    """Returns (raw win in credits, scatter count). Optionally accumulates per-symbol stats."""
    nsc = 0
    for k in range(3):
        if win[0, st0, k] == 1: nsc += 1
        if win[1, st1, k] == 1: nsc += 1
        if win[2, st2, k] == 1: nsc += 1
        if win[3, st3, k] == 1: nsc += 1
        if win[4, st4, k] == 1: nsc += 1
    total = sc_pay[nsc]
    for li in range(lines.shape[0]):
        sym = win[0, st0, lines[li, 0]]
        if sym == 1:
            continue
        n = 1
        x = win[1, st1, lines[li, 1]]
        if x == sym or x == 0:
            n = 2
            x = win[2, st2, lines[li, 2]]
            if x == sym or x == 0:
                n = 3
                x = win[3, st3, lines[li, 3]]
                if x == sym or x == 0:
                    n = 4
                    x = win[4, st4, lines[li, 4]]
                    if x == sym or x == 0:
                        n = 5
        p = pay[sym, n]
        if p > 0:
            total += p
            if sym_pay.shape[0] > 1:
                sym_pay[sym, n] += p
                sym_hit[sym, n] += 1
    return total, nsc


@njit(parallel=True, cache=True)
def enumerate_cycle(win, lens, lines, pay, sc_pay, maxb):
    """Every reel-stop combination exactly once.
    Returns hist[nsc, raw_win] (combo counts), sym_pay[s,n] (credits), sym_hit[s,n] (line hits)."""
    L0 = lens[0]
    hist = np.zeros((L0, 6, maxb), dtype=np.int64)
    spay = np.zeros((L0, pay.shape[0], 6), dtype=np.int64)
    shit = np.zeros((L0, pay.shape[0], 6), dtype=np.int64)
    for a in prange(L0):
        sp = spay[a]; sh = shit[a]; h = hist[a]
        for b in range(lens[1]):
            for c in range(lens[2]):
                for d in range(lens[3]):
                    for e in range(lens[4]):
                        t, nsc = eval_spin(win, a, b, c, d, e, lines, pay, sc_pay, sp, sh)
                        h[nsc, t] += 1
    return hist.sum(axis=0), spay.sum(axis=0), shit.sum(axis=0)


@njit(cache=True)
def simulate_chunk(win_b, lens_b, win_f, lens_f, stops_b, stops_f, lines, pay, sc_pay,
                   round_hist, nsc_hist, acc, max_win, fs_award, fs_mult, fs_max_spins):
    """Play len(stops_b) game rounds. Feature spins consume rows of stops_f sequentially.
    acc: [0 base_line+scatter credits, 1 fs credits(after mult, after cap), 2 base hits,
          3 round hits, 4 triggers, 5 fs spins, 6 retriggers, 7 cap hits, 8 sum win^2 (float),
          9 max round win, 10 base scatter credits, 11 fs scatter credits, 12 fs pointer]"""
    dummy = np.zeros((1, 1), dtype=np.int64)
    fp = int(acc[12])
    nf = stops_f.shape[0]
    for i in range(stops_b.shape[0]):
        t, nsc = eval_spin(win_b, stops_b[i, 0], stops_b[i, 1], stops_b[i, 2], stops_b[i, 3], stops_b[i, 4],
                           lines, pay, sc_pay, dummy, dummy)
        rw = t
        nsc_hist[nsc] += 1
        acc[0] += t
        acc[10] += sc_pay[nsc]
        if t > 0: acc[2] += 1
        if nsc >= 3:
            acc[4] += 1
            remaining = fs_award
            awarded = fs_award
            fs_won = 0
            while remaining > 0:
                if fp >= nf:            # out of pre-drawn feature stops: signal caller
                    return i, fp
                st = stops_f[fp]; fp += 1
                ft, fsc = eval_spin(win_f, st[0], st[1], st[2], st[3], st[4], lines, pay, sc_pay, dummy, dummy)
                remaining -= 1
                acc[5] += 1
                acc[11] += fs_mult * sc_pay[fsc]
                fs_won += fs_mult * ft
                if fsc >= 3 and awarded < fs_max_spins:
                    remaining += fs_award; awarded += fs_award; acc[6] += 1
                if rw + fs_won >= max_win:      # cap reached: feature ends
                    break
            if rw + fs_won >= max_win:
                acc[7] += 1
                fs_won = max_win - rw
            acc[1] += fs_won
            rw += fs_won
        if rw > 0: acc[3] += 1
        acc[8] += float(rw) * float(rw)
        if rw > acc[9]: acc[9] = rw
        round_hist[rw] += 1
    acc[12] = fp
    return stops_b.shape[0], fp
