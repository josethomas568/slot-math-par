"""Build the Excel PAR sheet. All RTP math is live formulas driven by the reel strips on the Strips tab."""
import json
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.comments import Comment
from game import (SYMBOLS, LINE_PAYS, SCATTER_PAY_X, LINES, BET, NLINES, FS_AWARD, FS_MULT, FS_MAX_SPINS,
                  MAX_WIN_X, NROWS, build_strips)

counts = json.load(open("counts.json"))
exact = json.load(open("exact_results.json"))
sim = json.load(open("sim_results.json"))
VARS = ["96", "94", "92"]

F = "Arial"
f_title = Font(name=F, size=14, bold=True)
f_h = Font(name=F, size=10, bold=True, color="FFFFFF")
f_b = Font(name=F, size=10, bold=True)
f_n = Font(name=F, size=10)
f_in = Font(name=F, size=10, color="0000FF")          # hardcoded input
f_link = Font(name=F, size=10, color="008000")        # cross-sheet link
f_py = Font(name=F, size=10, color="7030A0", italic=True)  # value imported from Python
fill_h = PatternFill("solid", fgColor="1F3864")
fill_sec = PatternFill("solid", fgColor="D9E1F2")
fill_key = PatternFill("solid", fgColor="FFF2CC")
thin = Side(style="thin", color="BFBFBF")
box = Border(top=thin, bottom=thin, left=thin, right=thin)
PCT = "0.0000%"; PCT6 = "0.000000%"; PR = "0.000000000"; SCI = "0.000E+00"; INT = "#,##0"

wb = Workbook()


def hdr(ws, r, c, labels, width=None):
    for i, t in enumerate(labels):
        x = ws.cell(r, c + i, t); x.font = f_h; x.fill = fill_h; x.alignment = Alignment(horizontal="center", wrap_text=True)
        x.border = box


def put(ws, r, c, v, font=f_n, fmt=None, bold=False):
    x = ws.cell(r, c, v); x.font = f_b if bold else font; x.border = box
    if fmt: x.number_format = fmt
    return x


def section(ws, r, text, ncol=8):
    for i in range(ncol):
        ws.cell(r, 1 + i).fill = fill_sec
    ws.cell(r, 1, text).font = Font(name=F, size=11, bold=True)


# ============================================================================ Inputs
wi = wb.active; wi.title = "Inputs"
wi["A1"] = "Lucky Sevens 20 — game rules and pay table"; wi["A1"].font = f_title
wi["A2"] = "Blue = editable input. All PAR math on the PAR_xx tabs references these cells and the Strips tab."
wi["A2"].font = Font(name=F, size=9, italic=True)
params = [("Reels", 5), ("Rows", NROWS), ("Paylines (fixed)", NLINES), ("Total bet (credits = line bets)", BET),
          ("Free spins awarded per 3+ STAR", FS_AWARD), ("Free-spin win multiplier", FS_MULT),
          ("Max free spins per feature", FS_MAX_SPINS), ("Max win per round (x total bet)", MAX_WIN_X)]
hdr(wi, 4, 1, ["Parameter", "Value"])
P = {}
for i, (k, v) in enumerate(params):
    put(wi, 5 + i, 1, k); put(wi, 5 + i, 2, v, f_in)
    P[k] = f"Inputs!$B${5 + i}"
ROWS, BETC, AWARD, MULT, MAXSP, CAPX = (P["Rows"], P["Total bet (credits = line bets)"], P["Free spins awarded per 3+ STAR"],
                                        P["Free-spin win multiplier"], P["Max free spins per feature"], P["Max win per round (x total bet)"])
wi["D4"] = "Rules"; wi["D4"].font = f_b
rules = ["WILD substitutes for all symbols except STAR; appears on reels 2-4 only; no pay of its own.",
         "Line wins pay left to right on adjacent reels, highest win per line only; line pays x line bet.",
         "STAR pays anywhere (x total bet); at most one STAR visible per reel (strip spacing >= 3).",
         "3+ STAR in base game awards 10 free spins on the free-spin reel set; all free-spin wins x3.",
         "3+ STAR during free spins retriggers +10 spins, up to 50 spins per feature.",
         "Round win (base spin + its feature) capped at 5,000x total bet; feature ends when cap is reached."]
for i, t in enumerate(rules):
    wi.cell(5 + i, 4, t).font = f_n

r0 = 15
wi.cell(r0 - 1, 1, "Line pay table (x line bet)").font = f_b
hdr(wi, r0, 1, ["Symbol", "2 OAK", "3 OAK", "4 OAK", "5 OAK"])
PAYROW = {}
for i, (name, pays) in enumerate(LINE_PAYS.items()):
    put(wi, r0 + 1 + i, 1, name)
    for j, p in enumerate(pays):
        put(wi, r0 + 1 + i, 2 + j, p, f_in)
    PAYROW[name] = r0 + 1 + i
s0 = r0 + 13
wi.cell(s0 - 1, 1, "STAR scatter pays (x total bet)").font = f_b
hdr(wi, s0, 1, ["STARs visible", "Pay x bet"])
SCROW = {}
for k in range(6):
    put(wi, s0 + 1 + k, 1, k); put(wi, s0 + 1 + k, 2, SCATTER_PAY_X.get(k, 0), f_in); SCROW[k] = s0 + 1 + k
wi.column_dimensions["A"].width = 34; wi.column_dimensions["B"].width = 10
for c in "CDE": wi.column_dimensions[c].width = 10

# ============================================================================ Lines
wl = wb.create_sheet("Paylines")
wl["A1"] = "Payline definitions (row index per reel: 0 = top, 1 = middle, 2 = bottom)"; wl["A1"].font = f_b
hdr(wl, 3, 1, ["Line", "Reel 1", "Reel 2", "Reel 3", "Reel 4", "Reel 5"])
for i, l in enumerate(LINES):
    put(wl, 4 + i, 1, i + 1)
    for j, v in enumerate(l): put(wl, 4 + i, 2 + j, int(v), f_in)
wl["H3"] = "Each payline reads exactly one cell per reel, so for every line the symbol on reel r is distributed as reel r's"
wl["H4"] = "strip frequencies. The single-line probability table on the PAR tabs is therefore exact for all 20 lines."
for c in ("H3", "H4"): wl[c].font = Font(name=F, size=9, italic=True)

# ============================================================================ Strips
wsr = wb.create_sheet("Strips")
wsr["A1"] = "Reel strips (stop position = row - 2). Edit any symbol and every PAR tab recalculates."; wsr["A1"].font = f_b
fs_strips = build_strips(np.array(counts["fs_counts"]))
sets = [(f"Base {v}%", build_strips(np.array(counts["base_counts"][v]))) for v in VARS] + [("Free spins (all variants)", fs_strips)]
STRIPCOL = {}
col = 2
put(wsr, 2, 1, "Stop", bold=True)
maxlen = max(len(s) for _, ss in sets for s in ss)
for i in range(maxlen):
    put(wsr, 3 + i, 1, i)
for name, ss in sets:
    wsr.cell(1 + 1, col, name).font = f_b
    for r, s in enumerate(ss):
        hdr(wsr, 3 - 1, col + r, [f"R{r+1}"]) if False else None
        c = wsr.cell(2, col + r, f"{name.split()[0]}{'' if 'Free' in name else name.split()[1].rstrip('%')} R{r+1}")
        c.font = f_h; c.fill = fill_h; c.alignment = Alignment(horizontal="center")
        for i, sym in enumerate(s):
            x = wsr.cell(3 + i, col + r, SYMBOLS[sym]); x.font = f_in; x.alignment = Alignment(horizontal="center")
        STRIPCOL[(name, r)] = CL(col + r)
        wsr.column_dimensions[CL(col + r)].width = 8
    col += 6
LAST = 3 + 59   # count ranges cover 60 stops so strips can be lengthened in place


def strip_rng(name, r):
    c = STRIPCOL[(name, r)]
    return f"Strips!${c}$3:${c}${LAST}"


# ============================================================================ PAR sheets
SYM_ORDER = SYMBOLS  # WILD, STAR, SEVEN..10
PAYING = [s for s in SYMBOLS if s in LINE_PAYS]
check_cells = {}


def build_par(v):
    ws = wb.create_sheet(f"PAR_{v}")
    ex, sm = exact[v], sim[v]
    ws["A1"] = f"PAR sheet — Lucky Sevens 20, {v}% variant"; ws["A1"].font = f_title
    ws["A2"] = ("Black = live formula; blue = input; green = link to another tab; purple italic = value imported from the "
                "Python full-cycle / simulation run (for comparison only).")
    ws["A2"].font = Font(name=F, size=9, italic=True)
    bname, fname = f"Base {v}%", "Free spins (all variants)"

    # ---------------- reel symbol counts
    section(ws, 4, "1. Reel strip symbol counts (COUNTIF over the Strips tab)", 12)
    hdr(ws, 5, 1, ["Symbol", "Base R1", "Base R2", "Base R3", "Base R4", "Base R5", "", "FS R1", "FS R2", "FS R3", "FS R4", "FS R5"])
    CROW = {}
    for i, s in enumerate(SYM_ORDER):
        rr = 6 + i; CROW[s] = rr
        put(ws, rr, 1, s)
        for r in range(5):
            put(ws, rr, 2 + r, f'=COUNTIF({strip_rng(bname, r)},$A{rr})', fmt=INT)
            put(ws, rr, 8 + r, f'=COUNTIF({strip_rng(fname, r)},$A{rr})', fmt=INT)
    LROW = 6 + len(SYM_ORDER)
    put(ws, LROW, 1, "Strip length", bold=True)
    for r in range(5):
        put(ws, LROW, 2 + r, f"=SUM({CL(2+r)}6:{CL(2+r)}{LROW-1})", fmt=INT)
        put(ws, LROW, 8 + r, f"=SUM({CL(8+r)}6:{CL(8+r)}{LROW-1})", fmt=INT)
    put(ws, LROW + 1, 1, "Full cycle (all stop combos)", bold=True)
    put(ws, LROW + 1, 2, f"=PRODUCT(B{LROW}:F{LROW})", fmt=INT)
    put(ws, LROW + 1, 8, f"=PRODUCT(H{LROW}:L{LROW})", fmt=INT)
    CYC_B, CYC_F = f"$B${LROW+1}", f"$H${LROW+1}"

    # ---------------- line combination tables
    def line_table(top, c0, title):
        """c0 = first column of the reel-count block (2 base, 8 FS)."""
        section(ws, top, title, 12)
        hdr(ws, top + 1, 1, ["Symbol", "OAK", "Pay x line", "Combos (per line, full cycle)", "Prob per line",
                             "1 in", "RTP contribution"])
        rows = []
        rr = top + 2
        for s in PAYING:
            for n in (2, 3, 4, 5):
                if LINE_PAYS[s][n - 2] == 0: continue
                put(ws, rr, 1, s); put(ws, rr, 2, n)
                put(ws, rr, 3, f"=INDEX(Inputs!$B${PAYROW[s]}:$E${PAYROW[s]},1,{n-1})", f_link)
                # matching cells on reel r: symbol count (+ wild count, wild is 0 on reels 1 and 5)
                m = []
                for r in range(5):
                    cc = CL(c0 + r)
                    m.append(f"${cc}${CROW[s]}" if r == 0 else f"(${cc}${CROW[s]}+${cc}${CROW['WILD']})")
                L = [f"${CL(c0 + r)}${LROW}" for r in range(5)]
                terms = m[:n]
                if n < 5:
                    terms.append(f"({L[n]}-{m[n]})")
                    terms += L[n + 1:]
                put(ws, rr, 4, "=" + "*".join(terms), fmt=INT)
                cyc = CYC_B if c0 == 2 else CYC_F
                put(ws, rr, 5, f"=D{rr}/{cyc}", fmt=PR)
                put(ws, rr, 6, f'=IF(E{rr}>0,1/E{rr},"-")', fmt="#,##0.0")
                put(ws, rr, 7, f"=C{rr}*E{rr}", fmt=PCT6)
                rows.append(rr); rr += 1
        put(ws, rr, 1, "Total line RTP (x line bet per line = x total bet over 20 lines)", bold=True)
        put(ws, rr, 7, f"=SUM(G{rows[0]}:G{rows[-1]})", fmt=PCT6, bold=True)
        put(ws, rr + 1, 1, "Prob. of any single line paying (per line)")
        put(ws, rr + 1, 7, f"=SUM(E{rows[0]}:E{rows[-1]})", fmt=PR)
        return rows, rr

    b_rows, b_tot = line_table(LROW + 3, 2, "2. Base game line wins (exact, from strip counts)")
    f_rows, f_tot = line_table(b_tot + 3, 8, "3. Free-spin reel set line wins (per free spin, before x3 multiplier)")

    # ---------------- scatter
    def scatter_block(top, c0, title):
        section(ws, top, title, 12)
        hdr(ws, top + 1, 1, ["Reel", "STAR count", "Length", "P(STAR visible)", "P(0)", "P(1)", "P(2)", "P(3)", "P(4)", "P(5)"])
        put(ws, top + 2, 1, "start")
        for k in range(6): put(ws, top + 2, 5 + k, 1 if k == 0 else 0, f_in)
        for r in range(5):
            rr = top + 3 + r
            cc = CL(c0 + r)
            put(ws, rr, 1, r + 1)
            put(ws, rr, 2, f"=${cc}${CROW['STAR']}", fmt=INT)
            put(ws, rr, 3, f"=${cc}${LROW}", fmt=INT)
            put(ws, rr, 4, f"={ROWS}*B{rr}/C{rr}", fmt=PR)
            for k in range(6):
                prev = f"{CL(5+k)}{rr-1}"
                f = f"={prev}*(1-$D{rr})" + (f"+{CL(4+k)}{rr-1}*$D{rr}" if k > 0 else "")
                put(ws, rr, 5 + k, f, fmt=PR)
        dist = top + 7
        put(ws, dist + 1, 1, "Pay x total bet");
        for k in range(6): put(ws, dist + 1, 5 + k, f"=Inputs!$B${SCROW[k]}", f_link)
        put(ws, dist + 2, 1, "Scatter RTP (x total bet)", bold=True)
        put(ws, dist + 2, 5, f"=SUMPRODUCT(E{dist}:J{dist},E{dist+1}:J{dist+1})", fmt=PCT6, bold=True)
        put(ws, dist + 3, 1, "P(3+ STAR) = trigger / retrigger probability", bold=True)
        put(ws, dist + 3, 5, f"=SUM(H{dist}:J{dist})", fmt=PR, bold=True)
        put(ws, dist + 3, 6, f"=1/E{dist+3}", fmt="\"1 in \"#,##0.00")
        ws.cell(dist + 4, 1, "Poisson-binomial recursion over reels; exact because strips space STARs >= 3 apart, so at most one per reel is visible.").font = Font(name=F, size=9, italic=True)
        return f"$E${dist+2}", f"$E${dist+3}", dist

    sc_b, ptrig, dist_b = scatter_block(f_tot + 3, 2, "4. Base game STAR scatter")
    sc_f, qret, dist_f = scatter_block(dist_b + 6, 8, "5. Free-spin STAR scatter / retrigger")

    # ---------------- Markov chain
    mtop = dist_f + 6
    section(ws, mtop, "6. Free-spin Markov chain: P(t spins played, r retriggers); state alive while t < award x (1 + r)", 12)
    max_r = FS_MAX_SPINS // FS_AWARD - 1
    hdr(ws, mtop + 1, 1, ["t"] + [f"r={r}" for r in range(max_r + 1)] + ["Spins played at t (alive mass)"])
    for r in range(max_r + 1):
        put(ws, mtop + 2, 2 + r, 1 if r == 0 else 0, f_in)
    for t in range(FS_MAX_SPINS + 1):
        rr = mtop + 2 + t
        put(ws, rr, 1, t)
        if t > 0:
            pr = rr - 1; tp = t - 1
            for r in range(max_r + 1):
                cur = f"{CL(2+r)}{pr}"
                alive = f"($A{pr}<{AWARD}*(1+{r}))"
                f = f"=IF({alive},{cur}*(1-{qret}),{cur})"
                if r > 0:
                    f += f"+IF($A{pr}<{AWARD}*{r},{CL(1+r)}{pr}*{qret},0)"
                if r == max_r:
                    f += f"+IF({alive},{cur}*{qret},0)"
                put(ws, rr, 2 + r, f, fmt=PR)
        if t < FS_MAX_SPINS:
            terms = "+".join(f"IF($A{rr}<{AWARD}*(1+{r}),{CL(2+r)}{rr},0)" for r in range(max_r + 1))
            put(ws, rr, 3 + max_r, "=" + terms, fmt=PR)
    end = mtop + 2 + FS_MAX_SPINS
    put(ws, end + 1, 1, "E[free spins per feature]", bold=True)
    put(ws, end + 1, 3 + max_r, f"=SUM({CL(3+max_r)}{mtop+2}:{CL(3+max_r)}{end-1})", fmt="0.000000000", bold=True)
    put(ws, end + 2, 1, "P(r retriggers) at end")
    for r in range(max_r + 1): put(ws, end + 2, 2 + r, f"={CL(2+r)}{end}", fmt=PR)
    put(ws, end + 3, 1, "Check: probabilities sum to 1")
    put(ws, end + 3, 2, f"=SUM(B{end}:{CL(2+max_r)}{end})", fmt="0.000000000000")
    ESP = f"${CL(3+max_r)}${end+1}"
    ws.cell(end + 4, 1, "Wald's identity: E[feature win] = E[spins] x E[win per spin], since each spin's outcome is independent of whether it is played.").font = Font(name=F, size=9, italic=True)

    # ---------------- RTP summary at the top right
    sr = 4; sc = 15
    for i in range(3): ws.cell(sr, sc + i).fill = fill_sec
    ws.cell(sr, sc, "RTP SUMMARY (live)").font = Font(name=F, size=11, bold=True)
    hdr(ws, sr + 1, sc, ["Component", "Excel (formula)", "Python exact"])
    py = {"line_base": ex["line_base"], "scatter_base": ex["scatter_base"], "p_trigger": ex["p_trigger"],
          "line_fs_raw": ex["line_fs_raw"], "scatter_fs_raw": ex["scatter_fs_raw"], "q_retrigger": ex["q_retrigger"],
          "E_spins": ex["E_spins"], "fs_value": ex["fs_value"], "fs_rtp": ex["fs_rtp"], "rtp_uncapped": ex["rtp_uncapped"]}
    rows = [("Base game line RTP", f"=G{b_tot}", "line_base", PCT6),
            ("Base game STAR scatter RTP", f"={sc_b}", "scatter_base", PCT6),
            ("Base game RTP", None, None, PCT6),
            ("P(trigger) per base spin", f"={ptrig}", "p_trigger", PR),
            ("Free-spin line RTP per spin (raw)", f"=G{f_tot}", "line_fs_raw", PCT6),
            ("Free-spin scatter RTP per spin (raw)", f"={sc_f}", "scatter_fs_raw", PCT6),
            ("P(retrigger) per free spin", f"={qret}", "q_retrigger", PR),
            ("Free-spin multiplier", f"={MULT}", None, "0"),
            ("E[free spins per feature]", f"={ESP}", "E_spins", "0.000000000"),
            ("Feature value (x total bet)", None, "fs_value", "0.000000"),
            ("Free-spin feature RTP", None, "fs_rtp", PCT6),
            ("THEORETICAL RTP before 5,000x cap", None, "rtp_uncapped", PCT6)]
    R = {}
    for i, (lab, f, key, fmt) in enumerate(rows):
        rr = sr + 2 + i; R[lab] = rr
        put(ws, rr, sc, lab)
        if f: put(ws, rr, sc + 1, f, fmt=fmt)
        if key: put(ws, rr, sc + 2, py[key], f_py, fmt=fmt)
    c1 = CL(sc + 1)
    ws[f"{c1}{R['Base game RTP']}"] = f"={c1}{R['Base game line RTP']}+{c1}{R['Base game STAR scatter RTP']}"
    ws[f"{c1}{R['Feature value (x total bet)']}"] = (f"={c1}{R['E[free spins per feature]']}*{c1}{R['Free-spin multiplier']}*"
                                                    f"({c1}{R['Free-spin line RTP per spin (raw)']}+{c1}{R['Free-spin scatter RTP per spin (raw)']})")
    ws[f"{c1}{R['Free-spin feature RTP']}"] = f"={c1}{R['P(trigger) per base spin']}*{c1}{R['Feature value (x total bet)']}"
    ws[f"{c1}{R['THEORETICAL RTP before 5,000x cap']}"] = f"={c1}{R['Base game RTP']}+{c1}{R['Free-spin feature RTP']}"
    for lab in ("Base game RTP", "Feature value (x total bet)", "Free-spin feature RTP", "THEORETICAL RTP before 5,000x cap"):
        x = ws[f"{c1}{R[lab]}"]; x.font = f_b if "THEOR" in lab else f_n; x.border = box
        x.number_format = dict((a, d) for a, _, _, d in rows)[lab]
    rr = sr + 2 + len(rows)
    put(ws, rr, sc, "Excel minus Python (uncapped)", bold=True)
    put(ws, rr, sc + 1, f"={c1}{R['THEORETICAL RTP before 5,000x cap']}-{CL(sc+2)}{R['THEORETICAL RTP before 5,000x cap']}", fmt=SCI, bold=True)
    check_cells[v] = (f"PAR_{v}", f"{c1}{R['THEORETICAL RTP before 5,000x cap']}", f"{c1}{rr}")
    put(ws, rr + 1, sc, "Max-win cap adjustment (exact DP, Python)")
    put(ws, rr + 1, sc + 1, -ex["cap_loss_rtp"], f_py, fmt=SCI)
    ws.cell(rr + 1, sc + 1).comment = Comment("Exact expected RTP removed by the 5,000x round cap: dynamic program over the "
                                              "free-spin chain with exact convolution of per-spin win distributions (exact.py).", "Python")
    put(ws, rr + 2, sc, "FINAL THEORETICAL RTP", bold=True)
    x = put(ws, rr + 2, sc + 1, f"={c1}{R['THEORETICAL RTP before 5,000x cap']}+{c1}{rr+1}", fmt=PCT6, bold=True); x.fill = fill_key
    put(ws, rr + 2, sc + 2, ex["rtp"], f_py, fmt=PCT6)
    put(ws, rr + 3, sc, "Hold (house edge)")
    put(ws, rr + 3, sc + 1, f"=1-{c1}{rr+2}", fmt=PCT)
    final_cell = f"{c1}{rr+2}"

    # ---------------- RTP by symbol (live)
    br = rr + 6
    for i in range(5): ws.cell(br, sc + i).fill = fill_sec
    ws.cell(br, sc, "RTP BY SYMBOL / FEATURE (live)").font = Font(name=F, size=11, bold=True)
    hdr(ws, br + 1, sc, ["Source", "Base game", "Free spins", "Total", "Share of RTP"])
    fsfac = f"{c1}{R['P(trigger) per base spin']}*{c1}{R['E[free spins per feature]']}*{c1}{R['Free-spin multiplier']}"
    for i, s in enumerate(PAYING):
        rr2 = br + 2 + i
        put(ws, rr2, sc, f"{s} lines")
        put(ws, rr2, sc + 1, f'=SUMIF($A${b_rows[0]}:$A${b_rows[-1]},"{s}",$G${b_rows[0]}:$G${b_rows[-1]})', fmt=PCT6)
        put(ws, rr2, sc + 2, f'={fsfac}*SUMIF($A${f_rows[0]}:$A${f_rows[-1]},"{s}",$G${f_rows[0]}:$G${f_rows[-1]})', fmt=PCT6)
        put(ws, rr2, sc + 3, f"={CL(sc+1)}{rr2}+{CL(sc+2)}{rr2}", fmt=PCT6)
        put(ws, rr2, sc + 4, f"={CL(sc+3)}{rr2}/{final_cell}", fmt="0.00%")
    rr2 = br + 2 + len(PAYING)
    put(ws, rr2, sc, "STAR scatter pays")
    put(ws, rr2, sc + 1, f"={sc_b}", fmt=PCT6)
    put(ws, rr2, sc + 2, f"={fsfac}*{sc_f}", fmt=PCT6)
    put(ws, rr2, sc + 3, f"={CL(sc+1)}{rr2}+{CL(sc+2)}{rr2}", fmt=PCT6)
    put(ws, rr2, sc + 4, f"={CL(sc+3)}{rr2}/{final_cell}", fmt="0.00%")
    put(ws, rr2 + 1, sc, "Max-win cap")
    put(ws, rr2 + 1, sc + 3, f"={c1}{rr+1}", fmt=SCI)
    put(ws, rr2 + 2, sc, "Total", bold=True)
    for k in (1, 2):
        put(ws, rr2 + 2, sc + k, f"=SUM({CL(sc+k)}{br+2}:{CL(sc+k)}{rr2})", fmt=PCT6, bold=True)
    put(ws, rr2 + 2, sc + 3, f"=SUM({CL(sc+3)}{br+2}:{CL(sc+3)}{rr2+1})", fmt=PCT6, bold=True)
    put(ws, rr2 + 3, sc, "Check vs final RTP")
    put(ws, rr2 + 3, sc + 3, f"={CL(sc+3)}{rr2+2}-{final_cell}", fmt=SCI)

    # ---------------- Python-only statistics
    pr0 = rr2 + 6
    for i in range(5): ws.cell(pr0, sc + i).fill = fill_sec
    ws.cell(pr0, sc, "DISTRIBUTION & VOLATILITY (Python: exact full cycle + 250M-round simulation)").font = Font(name=F, size=11, bold=True)
    hdr(ws, pr0 + 1, sc, ["Statistic", "Exact", "Simulated", "Notes"])
    stats_rows = [
        ("RTP", ex["rtp"], sm["rtp"], PCT6, f"{sm['spins']:,} rounds; z = {sm['z_vs_exact']:+.2f} vs exact"),
        ("Simulated RTP 95% CI", None, f"{sm['ci95'][0]:.4%} – {sm['ci95'][1]:.4%}", None, "exact inside CI" if sm["exact_in_ci95"] else "exact OUTSIDE CI"),
        ("Hit frequency (any win)", ex["round_hit_freq"], sm["hit_freq"], PCT, f"1 in {1/ex['round_hit_freq']:.3f}"),
        ("Feature trigger frequency", ex["p_trigger"], sm["trigger_freq"], PR, f"1 in {1/ex['p_trigger']:.1f}"),
        ("Free spins per feature", ex["E_spins"], sm["spins_per_feature"], "0.0000", None),
        ("Std deviation per round (x bet)", ex["sd"], sm["sd"], "0.0000", None),
        ("Volatility index (90%, 1.645 x SD)", ex["vi90"], sm["vi90"], "0.0000", None),
        ("Base game max win (x bet)", ex["base_max_win_x"], None, "0.00", None),
        ("Max free spin raw win (x bet, before x3)", ex["fs_spin_max_raw_x"], None, "0.00", None),
        ("P(round hits 5,000x cap)", ex["p_cap"], sm["cap_hits"] / sm["spins"], SCI, f"sim cap hits: {sm['cap_hits']}"),
        ("Largest simulated round win (x bet)", None, sm["max_round_win_x"], "#,##0.00", None),
    ]
    for i, (lab, e, s_, fmt, note) in enumerate(stats_rows):
        rr3 = pr0 + 2 + i
        put(ws, rr3, sc, lab)
        if e is not None: put(ws, rr3, sc + 1, e, f_py, fmt=fmt)
        if s_ is not None: put(ws, rr3, sc + 2, s_, f_py, fmt=fmt)
        if note: put(ws, rr3, sc + 3, note)
    # buckets
    b0 = pr0 + 3 + len(stats_rows)
    hdr(ws, b0, sc, ["Round win (x total bet)", "Exact prob", "Simulated prob", "Exact 1 in"])
    for i, (lab, p) in enumerate(ex["buckets"].items()):
        rr4 = b0 + 1 + i
        put(ws, rr4, sc, lab)
        put(ws, rr4, sc + 1, p, f_py, fmt=PR)
        put(ws, rr4, sc + 2, sm["buckets_sim"][lab], f_py, fmt=PR)
        put(ws, rr4, sc + 3, (1 / p) if p > 0 else "-", f_py, fmt="#,##0.0")
    # CI table (live formulas from SD)
    c0r = b0 + 2 + len(ex["buckets"])
    hdr(ws, c0r, sc, ["Spins played", "90% band ±", "95% band ±", "RTP 95% range"])
    sdc = f"{CL(sc+1)}{pr0+2+5}"
    for i, n in enumerate([1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]):
        rr5 = c0r + 1 + i
        put(ws, rr5, sc, n, f_in, fmt=INT)
        put(ws, rr5, sc + 1, f"=1.645*{sdc}/SQRT({CL(sc)}{rr5})", fmt="0.00%")
        put(ws, rr5, sc + 2, f"=1.96*{sdc}/SQRT({CL(sc)}{rr5})", fmt="0.00%")
        put(ws, rr5, sc + 3, f'=TEXT({final_cell}-{CL(sc+2)}{rr5},"0.00%")&" – "&TEXT({final_cell}+{CL(sc+2)}{rr5},"0.00%")')

    ws.column_dimensions["A"].width = 30
    for c in range(2, 14): ws.column_dimensions[CL(c)].width = 13
    ws.column_dimensions["D"].width = 17
    ws.column_dimensions[CL(sc)].width = 40
    for k in range(1, 5): ws.column_dimensions[CL(sc + k)].width = 18
    ws.freeze_panes = "B4"
    return final_cell, R, c1, b_rows, ptrig


finals = {}
for v in VARS:
    finals[v] = build_par(v)

# ============================================================================ Compliance
wc = wb.create_sheet("Compliance")
wc["A1"] = "Compliance checks"; wc["A1"].font = f_title
hdr(wc, 3, 1, ["Jurisdiction", "Min RTP", "Max RTP", "Source"] + [f"{v}% variant" for v in VARS])
juris = [("Nevada (NGC Reg. 14.040)", 0.75, None, "Nevada Gaming Commission Regulation 14.040: >= 75% of amounts wagered"),
         ("Mississippi (13 Miss. Code R. 7-12.5)", 0.80, 1.00, "80%-100% for each wager available"),
         ("New Jersey (N.J.A.C. 13:69E-1.28A)", 0.83, None, ">= 83%; no play with odds > 100 million to 1"),
         ("Pennsylvania (4 Pa.C.S. 1207(10))", 0.85, None, "theoretical payout no less than 85%")]
for i, (j, mn, mx, src) in enumerate(juris):
    rr = 4 + i
    put(wc, rr, 1, j); put(wc, rr, 2, mn, f_in, fmt="0%"); put(wc, rr, 3, mx if mx else "-", f_in, fmt="0%"); put(wc, rr, 4, src)
    for k, v in enumerate(VARS):
        fc = f"'PAR_{v}'!{finals[v][0]}"
        mxc = f'AND(ISNUMBER($C{rr}),{fc}>$C{rr})'
        put(wc, rr, 5 + k, f'=IF(AND({fc}>=$B{rr},NOT({mxc})),"PASS ("&TEXT({fc},"0.00%")&")","FAIL")')
r = 10
section(wc, r, "Max-win cap and top-award odds", 7)
hdr(wc, r + 1, 1, ["Check", "Limit", "", "Basis"] + [f"{v}% variant" for v in VARS])
put(wc, r + 2, 1, "Round win never exceeds cap (x bet)"); put(wc, r + 2, 2, f"={CAPX}", f_link, fmt="#,##0")
put(wc, r + 2, 4, "Enforced in game logic; max simulated round win shown")
for k, v in enumerate(VARS):
    put(wc, r + 2, 5 + k, f'=IF({sim[v]["max_round_win_x"]}<=$B{r+2},"PASS (max seen "&TEXT({sim[v]["max_round_win_x"]},"#,##0.0")&"x)","FAIL")')
put(wc, r + 3, 1, "Rarest pay-table line combo odds (1 in, per line)"); put(wc, r + 3, 2, 100_000_000, f_in, fmt="#,##0")
put(wc, r + 3, 4, "NJ: no play with odds > 100M:1 (per-line odds are a conservative bound)")
for k, v in enumerate(VARS):
    rows = finals[v][3]
    rng = f"'PAR_{v}'!$E${rows[0]}:$E${rows[-1]}"
    put(wc, r + 3, 5 + k, f'=IF(1/MIN({rng})<=$B{r+3},"PASS (1 in "&TEXT(1/MIN({rng}),"#,##0")&")","FAIL")')
put(wc, r + 4, 1, "Feature trigger reachable on every wager"); put(wc, r + 4, 4, "P(trigger) > 0 from strip counts")
for k, v in enumerate(VARS):
    put(wc, r + 4, 5 + k, f"=IF('PAR_{v}'!{finals[v][4]}>0,\"PASS\",\"FAIL\")")
put(wc, r + 5, 1, "P(round reaches 5,000x cap)")
put(wc, r + 5, 4, "Exact (Python DP). Cap is a safety limit, not an advertised pay-table award.")
for k, v in enumerate(VARS):
    put(wc, r + 5, 5 + k, exact[v]["p_cap"], f_py, fmt=SCI)

r = 18
section(wc, r, "RNG / implementation chi-square tests (Python; alpha = 0.01 per test)", 7)
hdr(wc, r + 1, 1, ["Test", "Variant", "Chi-square", "df", "p-value", "Result"])
rr = r + 2
for v in VARS:
    for name, t in sim[v]["chi_square"].items():
        put(wc, rr, 1, name.replace("_", " ")); put(wc, rr, 2, f"{v}%")
        put(wc, rr, 3, t["chi2"], f_py, fmt="0.00"); put(wc, rr, 4, t["df"], f_py)
        put(wc, rr, 5, t["p"], f_py, fmt="0.0000")
        put(wc, rr, 6, f'=IF(E{rr}>=0.01,"PASS","FAIL")')
        rr += 1
for name, t in sim["raw_rng"].items():
    put(wc, rr, 1, name.replace("_", " ")); put(wc, rr, 2, "raw PCG64 stream")
    if "chi2" in t:
        put(wc, rr, 3, t["chi2"], f_py, fmt="0.00"); put(wc, rr, 4, t["df"], f_py)
    else:
        put(wc, rr, 3, t["z"], f_py, fmt="0.000"); put(wc, rr, 4, "z")
    put(wc, rr, 5, t["p"], f_py, fmt="0.0000"); put(wc, rr, 6, f'=IF(E{rr}>=0.01,"PASS","FAIL")')
    rr += 1
put(wc, rr + 1, 1, "With this many independent tests, about 1% are expected to fall below 0.01 by chance alone.")
wc.cell(rr + 1, 1).font = Font(name=F, size=9, italic=True)
wc.column_dimensions["A"].width = 42; wc.column_dimensions["D"].width = 58
for c in "BCEFG": wc.column_dimensions[c].width = 20

# ============================================================================ Summary (first tab)
su = wb.create_sheet("Summary", 0)
su["A1"] = "Lucky Sevens 20 — PAR summary (5x3, 20 lines, wild reels 2-4, STAR free spins x3)"; su["A1"].font = f_title
su["A2"] = "Variants differ only in base-game reel strips; pay table, features and free-spin strips are identical."
su["A2"].font = Font(name=F, size=9, italic=True)
hdr(su, 4, 1, ["Metric"] + [f"{v}% variant" for v in VARS])
metrics = [("Final theoretical RTP (Excel, live)", lambda v: f"='PAR_{v}'!{finals[v][0]}", PCT6, f_link),
           ("Python exact RTP (full cycle + DP)", lambda v: exact[v]["rtp"], PCT6, f_py),
           ("Excel – Python (uncapped theoretical)", lambda v: f"='{check_cells[v][0]}'!{check_cells[v][2]}", SCI, f_link),
           ("Base game RTP", lambda v: f"='PAR_{v}'!{finals[v][2]}{finals[v][1]['Base game RTP']}", PCT, f_link),
           ("Free-spin feature RTP", lambda v: f"='PAR_{v}'!{finals[v][2]}{finals[v][1]['Free-spin feature RTP']}", PCT, f_link),
           ("Trigger frequency (1 in)", lambda v: f"=1/'PAR_{v}'!{finals[v][2]}{finals[v][1]['P(trigger) per base spin']}", "#,##0.0", f_link),
           ("Hit frequency", lambda v: exact[v]["round_hit_freq"], PCT, f_py),
           ("Volatility index (90%)", lambda v: exact[v]["vi90"], "0.00", f_py),
           ("Simulated rounds", lambda v: sim[v]["spins"], INT, f_py),
           ("Simulated RTP", lambda v: sim[v]["rtp"], PCT, f_py),
           ("Simulated RTP 95% CI low", lambda v: sim[v]["ci95"][0], PCT, f_py),
           ("Simulated RTP 95% CI high", lambda v: sim[v]["ci95"][1], PCT, f_py),
           ("Base strip lengths", lambda v: " / ".join(map(str, exact[v]["base_lens"])), None, f_py),
           ("Base cycle size", lambda v: exact[v]["N_base"], INT, f_py)]
for i, (lab, fn, fmt, font) in enumerate(metrics):
    put(su, 5 + i, 1, lab)
    for k, v in enumerate(VARS):
        put(su, 5 + i, 2 + k, fn(v), font, fmt=fmt)
su.column_dimensions["A"].width = 40
for c in "BCD": su.column_dimensions[c].width = 20
su["A21"] = "Colour key: black = formula, blue = input, green = cross-tab link, purple italic = imported from Python."
su["A21"].font = Font(name=F, size=9, italic=True)

wb.save("LuckySevens20_PAR.xlsx")
json.dump(check_cells, open("check_cells.json", "w"))
print("saved")
