import numpy as np
from game import W, S
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


