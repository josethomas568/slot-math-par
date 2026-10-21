# Lucky Sevens 20 — 5×3 video slot math model

A complete slot math package: game design, exact RTP by full-cycle enumeration, a free-spin Markov
chain, an exact round-win distribution with the max-win cap, a 250M-spin Monte Carlo check per variant,
three RTP variants tuned by reel strips only, and an Excel PAR sheet whose live formulas reproduce
the Python RTP.

## Game
- 5 reels × 3 rows, 20 fixed lines, total bet = 20 credits (1 credit per line).
- WILD on reels 2–4 only, substitutes for everything except STAR, no pay of its own.
- STAR scatter pays anywhere (2× / 10× / 100× total bet for 3 / 4 / 5); 3+ awards 10 free spins.
- Free spins use their own reel set, all wins ×3, 3+ STAR retriggers +10, max 50 spins per feature.
- Round win (base spin + its feature) capped at 5,000× total bet.

## Files
| File | Purpose |
|---|---|
| `game.py` | Symbols, pay table, paylines, strip builder, fast analytic evaluator (product formula + Poisson-binomial + Markov chain) |
| `engine.py` | Numba kernels: full-cycle enumeration and the simulation spin evaluator (same code path) |
| `finetune.py` | Tunes base strip counts to 96 / 94 / 92% (scatters, pay table and FS strips fixed) → `counts.json` |
| `exact.py` | Enumerates every stop combination of both reel sets, per-symbol and per-feature RTP, exact capped round distribution by DP with exact sparse convolution → `exact_results.json`, `round_pmf_*.npy` |
| `simulate.py` | 250M rounds per variant (PCG64), RTP / hit rate / volatility / CIs / win buckets, chi-square tests → `sim_results.json` |
| `build_par.py` | Writes `LuckySevens20_PAR.xlsx` with live formulas |
| `design96.py`, `greedy.py`, `tune.py`, `tune_valid.py` | Earlier design-search scaffolding (kept for reference) |

## Run order
```
pip install numba numpy scipy openpyxl
python finetune.py        # ~20 s
python exact.py           # ~75 s (3 variants)
python simulate.py 250e6  # ~5 min
python build_par.py
```

## Validation chain
1. Analytic product formula vs. full-cycle enumeration: agree to ~1e-16.
2. Capped DP mean + exact expected cap loss vs. Markov-chain mean: agree to ~5e-16.
3. Excel formulas (recalculated in LibreOffice) vs. Python: difference shown on each PAR tab.
4. Simulated RTP within its confidence interval of the exact value; win-bucket and scatter-count
   distributions pass chi-square goodness-of-fit against the exact distribution.
