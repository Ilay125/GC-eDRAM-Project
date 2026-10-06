#!/usr/bin/env python3
"""RTL-aligned SRC with 8 vs 4 data-array banks (SimPoint-weighted).

  B8  rtl_align/sweep/RTL/runs     (T_sweep 256, T_guard 258, F 29)
  B4  rtl_align/sweep/RTL-B4/runs  (T_sweep 448, T_guard 450, F 28)
  A   SRAM 32 KiB, C0 SRAM 48 KiB (as in analyze_sweep.py)

Writes rtl_align/sweep/results/banks.md and prints it.

  venv/bin/python rtl_align/compare_banks.py
"""
import math
import os

import analyze_sweep as an

HERE = os.path.dirname(os.path.abspath(__file__))
R = an.R
EXTRA = {"force_pki": ["forceRefresh"], "opp_pki": ["oppRefresh"],
         "fallback_pki": ["activeWbFullKept"],
         "clean_drop_pki": ["activeInvalidations"],
         "dirty_drop_pki": ["coldDirtyWritebacks"]}


def load(cfg, bench):
    """Weighted metrics of one config, or None if a SimPoint is missing."""
    d = {"B8": os.path.join(HERE, "sweep", "RTL", "runs", bench),
         "B4": os.path.join(HERE, "sweep", "RTL-B4", "runs", bench)}.get(
        cfg) or an.run_dir(cfg, bench)
    runs = []
    for i, w in enumerate(an.sram.load_weights(bench)):
        p = os.path.join(d, f"sp_{i}", "stats.txt")
        st = an.sram.read_second_dump(p) if os.path.exists(p) else None
        if st is None:
            return None
        m = an.sram.run_metrics(st)
        k = m["insts"] / 1e3
        for key, names in {**an.SRC_PKI, **EXTRA}.items():
            m[key] = sum(st.get(R + n, 0.0) for n in names) / k
        m["checkers"] = sum(st.get(R + n, 0.0) for n in an.CHECKERS)
        runs.append((w, m))
    cov = sum(w for w, _ in runs)

    def ws(key):
        return sum(w * m[key] for w, m in runs) / cov

    out = {"ipc": 1.0 / ws("cpi"), "mpki_primary": ws("mpki_mshr"),
           "checkers": sum(m["checkers"] for _, m in runs)}
    for key in list(an.SRC_PKI) + list(EXTRA):
        out[key] = ws(key)
    return out


def main():
    rows, missing = {}, []
    for b in an.BENCHES:
        r = {c: load(c, b) for c in ("A", "C0", "B8", "B4")}
        if any(v is None for v in r.values()):
            missing.append(b)
        else:
            rows[b] = r
    done = list(rows)

    def pct(x, y):
        return 100.0 * (x / y - 1)

    md = ["# RTL-aligned SRC: 8 vs 4 data-array banks (SimPoint-weighted)", "",
          f"Benchmarks complete: {len(done)} of {len(an.BENCHES)}" +
          (f" (incomplete: {', '.join(missing)})" if missing else ""), "",
          "B8: T_sweep 256, T_guard 258, F 29 (acts at 95.5-99.7% of DRT). "
          "B4: T_sweep 448, T_guard 450, F 28 (92.1-97.0%). Both CLOCK keep "
          "rule, 5-bit epoch stamps, CleanEvicts on.", "",
          "| bench | B8 vs A | B4 vs A | **B4 vs B8** | pMPKI B8 | B4 | "
          "refr B8 (forced) | B4 (forced) | drops B8 | B4 | fallback B8 | B4 | "
          "stall cyc B8 | B4 | checkers B4 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    g = {"B8": [], "B4": [], "B4/B8": []}
    for b in done:
        a, b8, b4 = rows[b]["A"], rows[b]["B8"], rows[b]["B4"]
        g["B8"].append(b8["ipc"] / a["ipc"])
        g["B4"].append(b4["ipc"] / a["ipc"])
        g["B4/B8"].append(b4["ipc"] / b8["ipc"])
        drops = [x["clean_drop_pki"] + x["dirty_drop_pki"] for x in (b8, b4)]
        md.append(
            f"| {b} | {pct(b8['ipc'], a['ipc']):+.2f}% | "
            f"{pct(b4['ipc'], a['ipc']):+.2f}% | "
            f"**{pct(b4['ipc'], b8['ipc']):+.2f}%** | "
            f"{b8['mpki_primary']:.2f} | {b4['mpki_primary']:.2f} | "
            f"{b8['refresh_pki']:.2f} ({b8['force_pki']:.2f}) | "
            f"{b4['refresh_pki']:.2f} ({b4['force_pki']:.2f}) | "
            f"{drops[0]:.2f} | {drops[1]:.2f} | {b8['fallback_pki']:.3f} | "
            f"{b4['fallback_pki']:.3f} | {b8['stall_pki']:.2f} | "
            f"{b4['stall_pki']:.2f} | {b4['checkers']:.0f} |")
    if done:
        gm = {k: 100 * (math.exp(sum(map(math.log, v)) / len(v)) - 1)
              for k, v in g.items()}
        tot = {c: sum(rows[b][c]["mpki_primary"] for b in done)
               for c in ("A", "C0", "B8", "B4")}
        md += [f"| **geomean** | {gm['B8']:+.2f}% | {gm['B4']:+.2f}% | "
               f"**{gm['B4/B8']:+.2f}%** | | | | | | | | | | | |", "",
               "Primary-MPKI gain kept, (A - X) / (A - C0) summed over the "
               f"benchmarks: B8 {100 * (tot['A'] - tot['B8']) / (tot['A'] - tot['C0']):.0f}%, "
               f"B4 {100 * (tot['A'] - tot['B4']) / (tot['A'] - tot['C0']):.0f}%."]
    os.makedirs(an.RESULTS, exist_ok=True)
    open(os.path.join(an.RESULTS, "banks.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
