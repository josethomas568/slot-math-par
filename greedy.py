import numpy as np
from game import analytic, NSYM, W, S
from tune_valid import valid

def moves(c, allow_len=True, syms=range(NSYM)):
    syms = list(syms)
    for r in range(5):
        for a in syms:
            for b in syms:
                if a != b:
                    d = c.copy(); d[r, a] -= 1; d[r, b] += 1; yield d
            if allow_len:
                d = c.copy(); d[r, a] += 1; yield d
                d = c.copy(); d[r, a] -= 1; yield d

def greedy(cb, cf, loss, which=("b", "f"), max_steps=200, allow_len=True, syms=range(NSYM), verbose=False):
    cur = loss(cb, cf)
    for step in range(max_steps):
        best = (cur, None, None)
        for wch in which:
            base = cb if wch == "b" else cf
            for d in moves(base, allow_len, syms):
                if not valid(d): continue
                l = loss(d, cf) if wch == "b" else loss(cb, d)
                if l < best[0] - 1e-12: best = (l, wch, d)
        if best[1] is None: break
        cur = best[0]
        if best[1] == "b": cb = best[2]
        else: cf = best[2]
        if verbose and step % 5 == 0: print(step, cur, flush=True)
    return cb, cf, cur
