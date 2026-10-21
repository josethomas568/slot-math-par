"""Monte Carlo verification: 100M+ game rounds per RTP variant, plus chi-square RNG tests."""
import json, sys, time
import numpy as np
from scipy import stats
from game import (LINES, PAY, SC_PAY, BET, MAX_WIN, FS_AWARD, FS_MULT, FS_MAX_SPINS, build_strips)
from engine import windows, simulate_chunk
from exact import bucketize, BUCKET_LABELS

N_SPINS = int(float(sys.argv[1])) if len(sys.argv) > 1 else 100_000_000
CHUNK = 2_000_000
SEEDS = {"96": 960001, "94": 940001, "92": 920001}


def chisq_gof(obs, exp_p, min_exp=5.0):
    """Pearson GOF; adjacent cells merged until expected >= min_exp."""
    exp = exp_p * obs.sum()
    o_m, e_m, o_acc, e_acc = [], [], 0.0, 0.0
    for o, e in zip(obs, exp):
        o_acc += o; e_acc += e
        if e_acc >= min_exp:
            o_m.append(o_acc); e_m.append(e_acc); o_acc = e_acc = 0.0
    if e_acc > 0:
        o_m[-1] += o_acc; e_m[-1] += e_acc
    o_m, e_m = np.array(o_m), np.array(e_m)
    chi = float(((o_m - e_m) ** 2 / e_m).sum()); df = len(o_m) - 1
    return dict(chi2=chi, df=df, p=float(stats.chi2.sf(chi, df)), cells=len(o_m))


def run_variant(key, base_strips, fs_strips, exact):
    wb, lb = windows(base_strips); wf, lf = windows(fs_strips)
    rng = np.random.Generator(np.random.PCG64(SEEDS[key]))
    round_hist = np.zeros(MAX_WIN + 1, dtype=np.int64)
    nsc_hist = np.zeros(6, dtype=np.int64)
    acc = np.zeros(13)
    stop_counts_b = [np.zeros(L, dtype=np.int64) for L in lb]
    stop_counts_f = [np.zeros(L, dtype=np.int64) for L in lf]
    pair_cross = np.zeros((lb[0], lb[1]), dtype=np.int64)
    pair_serial = np.zeros((lb[0], lb[0]), dtype=np.int64)
    batch_rtp = []
    t0 = time.time(); done = 0
    while done < N_SPINS:
        n = min(CHUNK, N_SPINS - done)
        sb = np.stack([rng.integers(0, L, size=n) for L in lb], axis=1)
        nf = int(n * 0.3) + 50_000
        sf = np.stack([rng.integers(0, L, size=nf) for L in lf], axis=1)
        before_won = acc[0] + acc[1]
        acc[12] = 0
        i, fp = simulate_chunk(wb, lb, wf, lf, sb, sf, LINES, PAY, SC_PAY, round_hist, nsc_hist, acc,
                               MAX_WIN, FS_AWARD, FS_MULT, FS_MAX_SPINS)
        assert i == n, "feature stop pool exhausted"
        for r in range(5):
            stop_counts_b[r] += np.bincount(sb[:, r], minlength=lb[r])
            stop_counts_f[r] += np.bincount(sf[:fp, r], minlength=lf[r])
        if done < 20_000_000:
            pair_cross += np.bincount(sb[:, 0] * lb[1] + sb[:, 1], minlength=pair_cross.size).reshape(pair_cross.shape)
            pair_serial += np.bincount(sb[:-1, 0] * lb[0] + sb[1:, 0], minlength=pair_serial.size).reshape(pair_serial.shape)
        batch_rtp.append(((acc[0] + acc[1]) - before_won) / (n * BET))
        done += n
    secs = time.time() - t0
    N = done
    won = acc[0] + acc[1]
    rtp = won / (N * BET)
    mean = rtp
    var = acc[8] / N / BET ** 2 - mean ** 2
    sd = float(np.sqrt(var))
    se = sd / np.sqrt(N)
    pmf_exact = np.load(f"round_pmf_{key}.npy")
    obs_b = bucketize(round_hist.astype(float))
    res = dict(variant=key, spins=N, seconds=secs, spins_per_sec=N / secs,
               rtp=rtp, rtp_exact=exact["rtp"], z_vs_exact=(rtp - exact["rtp"]) / (exact["sd"] / np.sqrt(N)),
               ci90=[rtp - 1.645 * se, rtp + 1.645 * se], ci95=[rtp - 1.96 * se, rtp + 1.96 * se],
               ci99=[rtp - 2.576 * se, rtp + 2.576 * se],
               exact_in_ci95=bool(abs(rtp - exact["rtp"]) <= 1.96 * se),
               base_rtp=(acc[0]) / (N * BET), fs_rtp=acc[1] / (N * BET),
               base_scatter_rtp=acc[10] / (N * BET),
               hit_freq=acc[3] / N, base_hit_freq=acc[2] / N,
               trigger_freq=acc[4] / N, retriggers_per_feature=acc[6] / max(acc[4], 1),
               spins_per_feature=acc[5] / max(acc[4], 1), sd=sd, vi90=1.645 * sd,
               cap_hits=int(acc[7]), cap_expected=exact["p_cap"] * N, max_round_win_x=acc[9] / BET,
               batch_rtp_sd=float(np.std(batch_rtp, ddof=1)), batch_size=CHUNK,
               batch_rtp_sd_expected=exact["sd"] / np.sqrt(CHUNK),
               buckets_sim=dict(zip(BUCKET_LABELS, (obs_b / N).tolist())),
               buckets_exact=exact["buckets"])
    # ---- chi-square tests
    tests = {}
    for r in range(5):
        tests[f"stop_uniformity_base_reel{r+1}"] = chisq_gof(stop_counts_b[r], np.full(lb[r], 1 / lb[r]))
        tests[f"stop_uniformity_fs_reel{r+1}"] = chisq_gof(stop_counts_f[r], np.full(lf[r], 1 / lf[r]))
    tests["independence_reel1_x_reel2"] = chisq_gof(pair_cross.ravel(), np.full(pair_cross.size, 1 / pair_cross.size))
    tests["serial_pairs_reel1"] = chisq_gof(pair_serial.ravel(), np.full(pair_serial.size, 1 / pair_serial.size))
    tests["scatter_count_vs_exact"] = chisq_gof(nsc_hist.astype(float), np.array(exact["nsc_dist_base"]))
    tests["win_buckets_vs_exact"] = chisq_gof(obs_b, bucketize(pmf_exact))
    res["chi_square"] = tests
    return res


def raw_rng_tests(seed=123456789, n_words=1 << 26):
    g = np.random.Generator(np.random.PCG64(seed))
    words = g.integers(0, 2 ** 32, size=n_words, dtype=np.uint32)
    by = words.view(np.uint8)
    cnt = np.bincount(by, minlength=256)
    t1 = chisq_gof(cnt.astype(float), np.full(256, 1 / 256))
    pop = np.array([bin(i).count('1') for i in range(256)]); ones = int((cnt * pop).sum()); nbits = by.size * 8
    z = (ones - nbits / 2) / np.sqrt(nbits / 4)
    # 4-bit nibble serial pairs (256 cells) on consecutive bytes
    pair = (by[:-1] >> 4).astype(np.uint16) * 16 + (by[1:] >> 4)
    t3 = chisq_gof(np.bincount(pair, minlength=256).astype(float), np.full(256, 1 / 256))
    return {"raw_byte_uniformity": t1,
            "raw_monobit": dict(z=float(z), p=float(2 * stats.norm.sf(abs(z))), bits=nbits),
            "raw_nibble_serial_pairs": t3}


if __name__ == "__main__":
    counts = json.load(open("counts.json"))
    exact = json.load(open("exact_results.json"))
    fs_strips = build_strips(np.array(counts["fs_counts"]))
    out = {}
    keys = sys.argv[2].split(",") if len(sys.argv) > 2 else list(counts["base_counts"])
    for k in keys:
        r = run_variant(k, build_strips(np.array(counts["base_counts"][k])), fs_strips, exact[k])
        out[k] = r
        print(k, {kk: r[kk] for kk in ["spins", "seconds", "rtp", "rtp_exact", "z_vs_exact", "hit_freq", "sd", "cap_hits", "cap_expected"]}, flush=True)
    out["raw_rng"] = raw_rng_tests()
    json.dump(out, open("sim_results.json", "w"), indent=1, default=float)
