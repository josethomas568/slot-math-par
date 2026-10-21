"""Exact math: full-cycle enumeration of base and free-spin reel sets, Markov chain for the
free-spin feature (retriggers, 50-spin cap) and exact game-round win distribution including the
5,000x max-win cap (dynamic programming over spins with FFT convolution)."""
import json, time, sys
import numpy as np
from numba import njit
from game import (SYMBOLS, NSYM, PAY, SC_PAY, LINES, BET, FS_AWARD, FS_MULT, FS_MAX_SPINS, MAX_WIN,
                  MAX_WIN_X, build_strips, analytic, fs_expected_spins, scatter_ok)
from engine import windows, enumerate_cycle, MAXB

BUCKETS = [0, 1e-9, 1, 2, 5, 10, 20, 50, 100, 250, 500, 1000, 2500, MAX_WIN_X - 1e-9, MAX_WIN_X + 1]
BUCKET_LABELS = ["0", "(0,1)", "[1,2)", "[2,5)", "[5,10)", "[10,20)", "[20,50)", "[50,100)", "[100,250)",
                 "[250,500)", "[500,1000)", "[1000,2500)", "[2500,5000)", "5000 (cap)"]


def bucketize(pmf):
    """pmf over round win in credits -> probabilities per x-total-bet bucket."""
    x = np.arange(len(pmf)) / BET
    idx = np.digitize(x, BUCKETS) - 1
    return np.bincount(idx, weights=pmf, minlength=len(BUCKET_LABELS))[:len(BUCKET_LABELS)]


def enum_reelset(strips):
    win, lens = windows(strips)
    hist, spay, shit = enumerate_cycle(win, lens, LINES, PAY, SC_PAY, MAXB)
    N = int(np.prod(lens.astype(object)))
    assert hist.sum() == N
    return dict(hist=hist, sym_pay=spay, sym_hit=shit, N=N, lens=lens)


@njit(cache=True)
def _conv_trunc(d, gk, gp, cap, out):
    """out[:cap] += d (*) g restricted below cap; returns (overflow mass, overflow mass*value).
    Direct (exact) convolution over the sparse support of g — no FFT round-off."""
    om = 0.0; ov = 0.0
    for i in range(d.shape[0]):
        di = d[i]
        if di == 0.0: continue
        for j in range(gk.shape[0]):
            v = i + gk[j]
            m = di * gp[j]
            if v >= cap:
                om += m; ov += m * v
            else:
                out[v] += m
    return om, ov


def feature_round_pmf(trig_pmf, g0, g1, cap, q, mu):
    """Distribution of total round win (base trigger spin + free spins), truncated at cap.
    trig_pmf: base-win pmf given trigger (credits). g0/g1: per-free-spin win pmf (credits, multiplier
    applied) jointly with no-retrigger / retrigger. Returns (pmf length cap+1 with index cap = capped,
    expected uncapped excess removed by the cap). q, mu: retrigger prob and mean free-spin win (credits)."""
    max_r = FS_MAX_SPINS // FS_AWARD - 1
    # R[t][r]: expected further spins from (t, r)
    R = np.zeros((FS_MAX_SPINS + 2, max_r + 1))
    for t in range(FS_MAX_SPINS, -1, -1):
        for r in range(max_r + 1):
            if t >= FS_AWARD * (1 + r):
                R[t, r] = 0.0
            else:
                R[t, r] = 1 + (1 - q) * R[t + 1, r] + q * R[t + 1, min(r + 1, max_r)]
    gs = []
    for g in (g0, g1):
        k = np.nonzero(g)[0]
        gs.append((k.astype(np.int64), g[k].copy()))
    D = {0: np.zeros(cap)}
    D[0][:len(trig_pmf)] = trig_pmf
    final = np.zeros(cap + 1)
    capped = 0.0; loss = 0.0
    for t in range(FS_MAX_SPINS + 1):
        newD = {}
        for r, d in D.items():
            if t >= FS_AWARD * (1 + r):            # feature over for this state
                final[:cap] += d
                continue
            for (gk, gp), r2 in ((gs[0], r), (gs[1], min(r + 1, max_r))):
                out = newD.setdefault(r2, np.zeros(cap))
                om, ov = _conv_trunc(d, gk, gp, cap, out)
                capped += om
                loss += ov + om * R[t + 1, r2] * mu - om * cap
        D = newD
    assert not D, "all states must finish within FS_MAX_SPINS"
    final[cap] += capped
    return final, loss


def exact_analysis(base_strips, fs_strips, label, check_uncapped=False):
    t0 = time.time()
    B = enum_reelset(base_strips)
    F = enum_reelset(fs_strips)
    Nb, Nf = B["N"], F["N"]
    hb, hf = B["hist"].astype(float), F["hist"].astype(float)
    w = np.arange(MAXB)

    # ---- base game
    base_pmf_nsc = hb / Nb
    p_trig = base_pmf_nsc[3:].sum()
    line_base = (B["sym_pay"].sum()) / Nb / BET
    sc_base = (base_pmf_nsc.sum(axis=1) * SC_PAY).sum() / BET
    base_hit = 1 - base_pmf_nsc[:, 0].sum()

    # ---- free-spin reel set, per spin (raw, before multiplier)
    fs_pmf_nsc = hf / Nf
    q = fs_pmf_nsc[3:].sum()
    line_fs_raw = F["sym_pay"].sum() / Nf / BET
    sc_fs_raw = (fs_pmf_nsc.sum(axis=1) * SC_PAY).sum() / BET
    E_spins, Pr = fs_expected_spins(q)
    fs_value = E_spins * FS_MULT * (line_fs_raw + sc_fs_raw)
    rtp_uncapped = line_base + sc_base + p_trig * fs_value

    # ---- exact capped round distribution
    trig_pmf = base_pmf_nsc[3:].sum(axis=0) / p_trig
    nontrig_pmf = base_pmf_nsc[:3].sum(axis=0)
    g0 = np.zeros(FS_MULT * (MAXB - 1) + 1); g1 = g0.copy()
    g0[::FS_MULT] = fs_pmf_nsc[:3].sum(axis=0)
    g1[::FS_MULT] = fs_pmf_nsc[3:].sum(axis=0)
    mu = FS_MULT * (line_fs_raw + sc_fs_raw) * BET
    feat, cap_loss_credits = feature_round_pmf(trig_pmf, g0, g1, MAX_WIN, q, mu)
    round_pmf = np.zeros(MAX_WIN + 1)
    round_pmf[:MAXB] += nontrig_pmf
    round_pmf += p_trig * feat
    x = np.arange(MAX_WIN + 1) / BET
    rtp_capped = float((round_pmf * x).sum())
    ex2 = float((round_pmf * x * x).sum())
    sd = np.sqrt(ex2 - rtp_capped ** 2)
    feat_x = np.arange(MAX_WIN + 1) / BET
    feat_mean_round = float((feat * feat_x).sum())          # E[round win | trigger] incl. trigger spin, capped

    res = dict(label=label, N_base=Nb, N_fs=Nf, base_lens=B["lens"].tolist(), fs_lens=F["lens"].tolist(),
               line_base=line_base, scatter_base=sc_base, p_trigger=p_trig, base_hit_freq=base_hit,
               q_retrigger=q, line_fs_raw=line_fs_raw, scatter_fs_raw=sc_fs_raw, E_spins=E_spins,
               retrigger_dist=Pr.tolist(), fs_value=fs_value, fs_rtp=p_trig * fs_value,
               rtp_uncapped=rtp_uncapped, rtp=rtp_capped, cap_adjustment=rtp_capped - rtp_uncapped,
               p_cap=float(round_pmf[MAX_WIN]), round_hit_freq=float(1 - round_pmf[0]),
               sd=sd, vi90=1.645 * sd, vi95=1.96 * sd,
               base_max_win_x=float(np.nonzero(hb.sum(0))[0].max() / BET),
               fs_spin_max_raw_x=float(np.nonzero(hf.sum(0))[0].max() / BET),
               mean_feature_round_x=feat_mean_round,
               buckets=dict(zip(BUCKET_LABELS, bucketize(round_pmf).tolist())),
               nsc_dist_base=base_pmf_nsc.sum(axis=1).tolist(), nsc_dist_fs=fs_pmf_nsc.sum(axis=1).tolist())
    # per-symbol breakdown (RTP contribution, hit probability per line)
    sym = []
    for s in range(2, NSYM):
        for n in range(2, 6):
            if PAY[s, n] == 0: continue
            sym.append(dict(symbol=SYMBOLS[s], n=n, pay=int(PAY[s, n]),
                            base_prob_per_line=B["sym_hit"][s, n] / Nb / len(LINES),
                            base_rtp=B["sym_pay"][s, n] / Nb / BET,
                            fs_prob_per_line=F["sym_hit"][s, n] / Nf / len(LINES),
                            fs_rtp=p_trig * E_spins * FS_MULT * F["sym_pay"][s, n] / Nf / BET))
    res["symbols"] = sym
    a = analytic(np.array([np.bincount(s, minlength=NSYM) for s in base_strips]),
                 np.array([np.bincount(s, minlength=NSYM) for s in fs_strips]))
    res["analytic_rtp"] = a["rtp"]
    res["enum_vs_analytic_diff"] = rtp_uncapped - a["rtp"]
    # Validation: capped mean + expected excess removed by the cap must equal the Markov-chain mean
    res["cap_loss_rtp"] = p_trig * cap_loss_credits / BET
    res["dp_plus_loss_minus_uncapped"] = rtp_capped + res["cap_loss_rtp"] - rtp_uncapped
    res["seconds"] = time.time() - t0
    return res, round_pmf


if __name__ == "__main__":
    counts = json.load(open("counts.json"))
    fs_strips = build_strips(np.array(counts["fs_counts"]))
    out = {}
    for k, cb in counts["base_counts"].items():
        strips = build_strips(np.array(cb))
        assert all(scatter_ok(s) for s in strips + fs_strips)
        r, pmf = exact_analysis(strips, fs_strips, k)
        np.save(f"round_pmf_{k}.npy", pmf)
        out[k] = r
        print(k, {kk: r[kk] for kk in ["rtp_uncapped", "analytic_rtp", "enum_vs_analytic_diff", "rtp",
                                       "cap_adjustment", "p_cap", "sd", "dp_plus_loss_minus_uncapped", "seconds"]}, flush=True)
    json.dump(out, open("exact_results.json", "w"), indent=1, default=float)
