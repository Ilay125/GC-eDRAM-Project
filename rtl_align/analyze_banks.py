#!/usr/bin/env python3
"""RTL-aligned SRC at 8 / 4 / 2 / 1 refresh banks (rtl_align/sweep/{RTL,
RTL-B4,RTL-B2,RTL-B1}, run_sweep.sh SWEEP_CFG=...), SimPoint-weighted with the aggregation of
analyze_sweep.py, against SRAM 32 KiB (A) and SRAM 48 KiB (C0). A benchmark
is reported once every SimPoint of every bank count is done. Writes
rtl_align/sweep/results_banks/{results.csv,report.md}.

  venv/bin/python rtl_align/analyze_banks.py
"""
import csv
import os

import analyze_sweep as asw

RESULTS = os.path.join(asw.HERE, "sweep", "results_banks")
SRC = ["RTL", "RTL-B4", "RTL-B2", "RTL-B1"]
CONFIGS = ["A", "C0"] + SRC
NAME = {"RTL": "8 banks", "RTL-B4": "4 banks", "RTL-B2": "2 banks",
        "RTL-B1": "1 bank"}
SHORT = {"RTL": "8b", "RTL-B4": "4b", "RTL-B2": "2b", "RTL-B1": "1b"}
FEWER = SRC[1:]

_run_dir = asw.run_dir


def run_dir(cfg, bench):
    if cfg in FEWER:
        return os.path.join(asw.HERE, "sweep", cfg, "runs", bench)
    return _run_dir(cfg, bench)


asw.run_dir = run_dir


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
            rows[(b, c)] = r[c]
    done = [b for b in asw.BENCHES if b not in missing]

    with open(os.path.join(RESULTS, "results.csv"), "w", newline="") as f:
        keys = list(next(iter(rows.values())).keys()) if rows else []
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows.values())

    def g(b, c, k):
        return rows[(b, c)][k]

    md = ["# RTL-aligned SRC: 8 vs 4 vs 2 vs 1 refresh banks "
          "(SimPoint-weighted)", "",
          "Only `--refresh_banks` differs (T_sweep 256 / 448 / 832 / 1600 "
          "cycles, deadline F 29 / 28 / 28 / 27). A = SRAM 32 KiB 4c, "
          "C0 = SRAM 48 KiB 5c.", ""]
    if missing:
        md += [f"Not complete yet (skipped): {', '.join(missing)}", ""]

    cols = ["C0"] + SRC
    md += ["## IPC", "",
           "| bench | IPC A | " + " | ".join(
               ("C0" if c == "C0" else SHORT[c]) + " vs A" for c in cols) +
           " | " + " | ".join(f"**{SHORT[c]} vs 8b**" for c in FEWER) + " |",
           "|---" * (2 + len(cols) + len(FEWER)) + "|"]
    ratio = {k: [] for k in cols + [c + "/8" for c in FEWER]}
    for b in done:
        a = g(b, "A", "ipc")
        r8 = g(b, "RTL", "ipc")
        for c in cols:
            ratio[c].append(g(b, c, "ipc") / a)
        for c in FEWER:
            ratio[c + "/8"].append(g(b, c, "ipc") / r8)
        md.append(f"| {b} | {a:.4f} | " + " | ".join(
            asw.fp(asw.pct(g(b, c, "ipc"), a)) for c in cols) + " | " +
            " | ".join(f"**{asw.fp(asw.pct(g(b, c, 'ipc'), r8))}**"
                       for c in FEWER) + " |")
    gm = {k: asw.geomean(v) for k, v in ratio.items()}

    def gfp(k):
        return asw.fp(None if gm[k] is None else 100 * (gm[k] - 1))
    md.append("| **geomean** | | " + " | ".join(gfp(c) for c in cols) +
              " | " + " | ".join(f"**{gfp(c + '/8')}**" for c in FEWER) +
              " |")

    md += ["", "## Primary MPKI and gain kept", "",
           "Gain kept = (A − SRC) / (A − C0), from summed primary MPKI.", "",
           "| bench | A | C0 | " + " | ".join(SHORT[c] for c in SRC) + " | " +
           " | ".join(f"kept {SHORT[c]}" for c in SRC) + " |",
           "|---" * (3 + 2 * len(SRC)) + "|"]
    tot = {c: 0.0 for c in CONFIGS}

    def kept(a, c0, s):
        return "–" if a - c0 < 0.05 else f"{100 * (a - s) / (a - c0):.0f}%"

    for b in done:
        v = {c: g(b, c, "mpki_primary") for c in CONFIGS}
        for c in CONFIGS:
            tot[c] += v[c]
        md.append(f"| {b} | " + " | ".join(f"{v[c]:.2f}" for c in CONFIGS)
                  + " | " + " | ".join(kept(v["A"], v["C0"], v[c])
                                       for c in SRC) + " |")
    if done:
        md.append("| **sum** | " + " | ".join(f"{tot[c]:.1f}"
                                              for c in CONFIGS) + " | " +
                  " | ".join(f"**{kept(tot['A'], tot['C0'], tot[c])}**"
                             for c in SRC) + " |")

    md += ["", "## SRC activity per kilo-instruction (8b / 4b / 2b / 1b)",
           "",
           "| bench | refreshes | drops (clean + dirty wb) | hit stall cycles "
           "| L2 bus pkts | checkers |", "|---|---|---|---|---|---|"]
    for b in done:
        def trio(k, d=2):
            return " / ".join(f"{g(b, c, k):.{d}f}" for c in SRC)
        md.append(f"| {b} | {trio('refresh_pki')} | {trio('drop_pki')} | "
                  f"{trio('stall_pki')} | {trio('l2bus_pki', 1)} | "
                  f"{trio('checkers', 0)} |")

    open(os.path.join(RESULTS, "report.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
