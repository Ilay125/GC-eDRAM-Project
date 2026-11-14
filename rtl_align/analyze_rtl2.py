#!/usr/bin/env python3
"""The 2-bank RTL controller (RTL2) against the earlier RTL-aligned SRC, one
change at a time (rtl_align/run_sweep.sh SWEEP_CFG="RTL-F27 RTL2-SET RTL2"):

  RTL       8 banks, set scanner, F 29 (T_sweep 256)     rtl_align/sweep/RTL
  RTL-F27   RTL with F 27 given                          .../RTL-F27
  RTL2-SET  RTL-F27 with 2 banks (set scanner)           .../RTL2-SET
  RTL2      2 banks, one line scanner per bank, a 4-cycle line budget
            (T_sweep 1920, T_guard 1924, F 27 derived)   .../RTL2
  RTL-B2    side point: 2 banks, set scanner, F 28       .../RTL-B2

So RTL-F27 vs RTL is the deadline (F 29 -> 27), RTL2-SET vs RTL-F27 the
banks (8 -> 2), RTL2 vs RTL2-SET the scanner. SimPoint-weighted with the
aggregation of analyze_sweep.py, against SRAM 32 KiB (A) and SRAM 48 KiB
(C0). Per-run means (act age, revisit interval) are SimPoint-weighted means
of the per-run means. A benchmark is reported once every SimPoint of every
config is done. Writes rtl_align/sweep/results_rtl2/{results.csv,report.md}.

  venv/bin/python rtl_align/analyze_rtl2.py
"""
import csv
import os

import analyze_sweep as asw

RESULTS = os.path.join(asw.HERE, "sweep", "results_rtl2")
SRC = ["RTL", "RTL-F27", "RTL2-SET", "RTL2", "RTL-B2"]
CONFIGS = ["A", "C0"] + SRC
NAME = {"RTL": "8b set F29", "RTL-F27": "8b set F27",
        "RTL2-SET": "2b set F27", "RTL2": "2b line F27",
        "RTL-B2": "2b set F28"}
# (label, from, to): each step changes one thing
STEPS = [("F 29→27", "RTL", "RTL-F27"), ("8→2 banks", "RTL-F27", "RTL2-SET"),
         ("line scanner", "RTL2-SET", "RTL2"), ("total", "RTL", "RTL2")]
EXTRA = {
    # name: (stat, kind) — kind "pki" per kinst, "mean" weighted mean
    "force_pki": ("forceRefresh", "pki"),
    "opp_pki": ("oppRefresh", "pki"),
    "clean_drop_pki": ("activeInvalidations", "pki"),
    "dirty_drop_pki": ("coldDirtyWritebacks", "pki"),
    "early_miss_pki": ("activeInvalidateEarlyMisses", "pki"),
    "opp_replaced_pki": ("oppReplaced", "pki"),
    "slot_wait_pki": ("scanSlotWaitCycles", "pki"),
    "drop_age": ("ageAtActiveInvalidate::mean", "mean"),
    "force_age": ("ageAtForceRefresh::mean", "mean"),
    "revisit": ("setVisitInterval::mean", "mean"),
    "revisit_max": ("maxSetVisitCycles", "max"),
}

_run_dir = asw.run_dir


def run_dir(cfg, bench):
    if cfg in SRC and cfg != "RTL":
        return os.path.join(asw.HERE, "sweep", cfg, "runs", bench)
    return _run_dir(cfg, bench)


asw.run_dir = run_dir


def extra(bench, cfg, weights):
    out = {k: 0.0 for k in EXTRA}
    wsum = {k: 0.0 for k in EXTRA}
    for i, w in enumerate(weights):
        p = os.path.join(run_dir(cfg, bench), f"sp_{i}", "stats.txt")
        st = asw.sram.read_second_dump(p)
        k = asw.sram.run_metrics(st)["insts"] / 1e3
        for key, (name, kind) in EXTRA.items():
            v = st.get(asw.R + name)
            if v is None:
                continue
            if kind == "pki":
                out[key] += w * v / k
                wsum[key] += w
            elif kind == "mean":
                out[key] += w * v
                wsum[key] += w
            else:
                out[key] = max(out[key], v)
                wsum[key] = 1.0
    return {k: (out[k] / wsum[k] if wsum[k] else None) for k in EXTRA}


def main():
    os.makedirs(RESULTS, exist_ok=True)
    rows, missing = {}, []
    for b in asw.BENCHES:
        w = asw.sram.load_weights(b)
        r = {c: asw.aggregate(b, c, w) for c in CONFIGS}
        if any(v is None for v in r.values()):
            missing.append(b)
            continue
        for c in CONFIGS:
            if c in SRC:
                r[c].update(extra(b, c, w))
            rows[(b, c)] = r[c]
    done = [b for b in asw.BENCHES if b not in missing]

    with open(os.path.join(RESULTS, "results.csv"), "w", newline="") as f:
        keys = sorted({k for r in rows.values() for k in r},
                      key=lambda k: (k not in ("bench", "config"), k))
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows.values())

    def g(b, c, k):
        return rows[(b, c)][k]

    md = ["# The 2-bank RTL controller, one change at a time "
          "(SimPoint-weighted)", "",
          "Configs: " + ", ".join(f"{c} = {NAME[c]}" for c in SRC) +
          ". A = SRAM 32 KiB 4c, C0 = SRAM 48 KiB 5c. Steps: "
          + "; ".join(f"**{s}** = {t} vs {f}" for s, f, t in STEPS[:3]) +
          ". RTL-B2 (F 28) is a side point: a 1-epoch step.", ""]
    if missing:
        md += [f"Not complete yet (skipped): {', '.join(missing)}", ""]

    # IPC
    md += ["## IPC", "",
           "| bench | IPC A | C0 vs A | " +
           " | ".join(f"{c} vs A" for c in SRC) + " | " +
           " | ".join(f"**{s}**" for s, _, _ in STEPS) + " |",
           "|---" * (3 + len(SRC) + len(STEPS)) + "|"]
    ratio = {k: [] for k in ["C0"] + SRC + [s for s, _, _ in STEPS]}
    for b in done:
        a = g(b, "A", "ipc")
        for c in ["C0"] + SRC:
            ratio[c].append(g(b, c, "ipc") / a)
        for s, f, t in STEPS:
            ratio[s].append(g(b, t, "ipc") / g(b, f, "ipc"))
        md.append(f"| {b} | {a:.4f} | " + " | ".join(
            asw.fp(asw.pct(g(b, c, "ipc"), a)) for c in ["C0"] + SRC) +
            " | " + " | ".join(
            f"**{asw.fp(asw.pct(g(b, t, 'ipc'), g(b, f, 'ipc')))}**"
            for _, f, t in STEPS) + " |")
    gm = {k: asw.geomean(v) for k, v in ratio.items()}

    def gfp(k):
        return asw.fp(None if gm[k] is None else 100 * (gm[k] - 1))
    md.append("| **geomean** | | " + " | ".join(
        gfp(c) for c in ["C0"] + SRC) + " | " +
        " | ".join(f"**{gfp(s)}**" for s, _, _ in STEPS) + " |")

    # Primary MPKI and gain kept
    md += ["", "## Primary MPKI and gain kept", "",
           "Gain kept = (A − SRC) / (A − C0), from summed primary MPKI; "
           "steps in points of gain kept.", "",
           "| bench | A | C0 | " + " | ".join(SRC) + " | " +
           " | ".join(f"kept {c}" for c in SRC) + " | " +
           " | ".join(f"**{s}**" for s, _, _ in STEPS) + " |",
           "|---" * (3 + 2 * len(SRC) + len(STEPS)) + "|"]
    tot = {c: 0.0 for c in CONFIGS}

    def kept(a, c0, s):
        return None if a - c0 < 0.05 else 100 * (a - s) / (a - c0)

    def kfmt(v):
        return "–" if v is None else f"{v:.0f}%"

    def dfmt(x, y):
        return "–" if x is None or y is None else f"{y - x:+.1f}"

    for b in done:
        v = {c: g(b, c, "mpki_primary") for c in CONFIGS}
        for c in CONFIGS:
            tot[c] += v[c]
        k = {c: kept(v["A"], v["C0"], v[c]) for c in SRC}
        md.append(f"| {b} | " + " | ".join(f"{v[c]:.2f}" for c in CONFIGS)
                  + " | " + " | ".join(kfmt(k[c]) for c in SRC) + " | " +
                  " | ".join(f"**{dfmt(k[f], k[t])}**" for _, f, t in STEPS)
                  + " |")
    if done:
        k = {c: kept(tot["A"], tot["C0"], tot[c]) for c in SRC}
        md.append("| **sum** | " + " | ".join(f"{tot[c]:.1f}"
                                              for c in CONFIGS) + " | " +
                  " | ".join(f"**{kfmt(k[c])}**" for c in SRC) + " | " +
                  " | ".join(f"**{dfmt(k[f], k[t])}**"
                             for _, f, t in STEPS) + " |")

    # Activity
    order = " / ".join(SRC[:4])
    md += ["", f"## SRC activity ({order})", "",
           "Per kilo-instruction unless noted. Ages are fractions of DRT "
           "(mean); revisit in cycles (mean, max).", "",
           "| bench | forced | opp | clean drops | dirty drops | early "
           "misses | hit stall cyc | drop age | force age | revisit | "
           "max revisit | opp replaced | slot wait cyc | checkers |",
           "|---" * 14 + "|"]
    for b in done:
        def q(k, d=2):
            vals = [g(b, c, k) for c in SRC[:4]]
            return " / ".join("–" if x is None else f"{x:.{d}f}"
                              for x in vals)
        md.append(f"| {b} | {q('force_pki')} | {q('opp_pki')} | "
                  f"{q('clean_drop_pki')} | {q('dirty_drop_pki')} | "
                  f"{q('early_miss_pki')} | {q('stall_pki')} | "
                  f"{q('drop_age', 3)} | {q('force_age', 3)} | "
                  f"{q('revisit', 0)} | {q('revisit_max', 0)} | "
                  f"{q('opp_replaced_pki', 3)} | {q('slot_wait_pki', 3)} | "
                  f"{q('checkers', 0)} |")

    open(os.path.join(RESULTS, "report.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
