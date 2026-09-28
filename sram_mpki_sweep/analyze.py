#!/usr/bin/env python3
"""Analyze the SRAM (DRT=0) L1D MPKI sweep (runs/<bench>/sp_<i>/l1d_<N>k/stats.txt).

Per benchmark and L1D size, aggregates the SimPoints with their weights:
  - L1D MPKI   = l1dcache.demandMisses::total / simInsts * 1000
  - L1D APKI   = l1dcache.demandAccesses::total / simInsts * 1000
  - miss rate  = demandMisses / demandAccesses (SimPoint-weighted per inst)
  - mpki_mshr  = l1dcache.demandMshrMisses::total / simInsts * 1000
                 (secondary, CSV only: excludes accesses that merged into an
                 in-flight miss)
  - IPC        = 1 / (weighted CPI)
  - L2 APKI    = l2cache.demandAccesses::total / simInsts * 1000
  - L2 MPKI    = l2cache.demandMisses::total / simInsts * 1000
  - DRAM GB/s  = weighted DRAM bytes / weighted simulated seconds
Only the second stats dump (the 100M measurement window) is used.

Writes results/results.csv and results/mpki_vs_size.png, prints a table with the 32->48 KiB deltas.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KNEE = os.path.join(HERE, "runs")
RESULTS = os.path.join(HERE, "results")
SIZES = [16, 32, 48, 64, 96]

ROLES = {
    "target": ["palm_r", "flightdm_r", "femflow_r", "cactus_r", "fotonik3d_r",
               "cpython_r", "sqlite_r", "roms_r"],
    "control": ["lbm_r", "nest_r"],
    "excluded": ["zstd_r", "sealcrypto_r"],
}
ROLE_OF = {b: r for r, bs in ROLES.items() for b in bs}
BENCH_ORDER = [b for r in ("target", "control", "excluded") for b in ROLES[r]]

STAT_RE = re.compile(r"^(\S+)\s+(\S+)")


def read_second_dump(path):
    """Return {stat_name: float} for the second stats dump in path."""
    stats, dump = {}, 0
    with open(path) as f:
        for line in f:
            if "Begin Simulation Statistics" in line:
                dump += 1
                continue
            if dump != 2:
                continue
            m = STAT_RE.match(line)
            if not m:
                continue
            try:
                stats[m.group(1)] = float(m.group(2))
            except ValueError:
                pass
    return stats if dump >= 2 else None


def run_metrics(stats):
    insts = stats["simInsts"]
    secs = stats["simSeconds"]
    dram_bw = sum(v for k, v in stats.items()
                  if re.match(r"board\.memory\.mem_ctrl\d+\.dram\.bwTotal::total$", k))
    hier = "board.cache_hierarchy."
    return {
        "insts": insts,
        "cpi": stats["board.processor.cores.core.numCycles"] / insts,
        "mpki": stats[hier + "l1dcache.demandMisses::total"] / insts * 1e3,
        "apki": stats[hier + "l1dcache.demandAccesses::total"] / insts * 1e3,
        "mpki_mshr": stats[hier + "l1dcache.demandMshrMisses::total"]
                     / insts * 1e3,
        "l2_apki": stats[hier + "l2cache.demandAccesses::total"] / insts * 1e3,
        "l2_mpki": stats[hier + "l2cache.demandMisses::total"]
                   / insts * 1e3,
        "secs": secs,
        "dram_bytes": dram_bw * secs,
    }


def load_weights(bench):
    path = os.path.join(ROOT, "spec_tests", f"{bench}_train", "simpoints.json")
    with open(path) as f:
        sp = json.load(f)
    return sp["weight_list"]


def aggregate(bench, size, weights, warnings):
    runs = []
    for i, w in enumerate(weights):
        p = os.path.join(KNEE, bench, f"sp_{i}", f"l1d_{size}k", "stats.txt")
        stats = read_second_dump(p) if os.path.exists(p) else None
        if stats is None:
            warnings.append(f"{bench} sp_{i} {size}k: missing/incomplete")
            continue
        runs.append((w, run_metrics(stats)))
    cov = sum(w for w, _ in runs)
    if cov < 0.99:
        warnings.append(f"{bench} {size}k: SimPoint coverage {cov:.3f} < 0.99")
    if not runs:
        return None
    wsum = lambda key: sum(w * m[key] for w, m in runs) / cov
    return {
        "bench": bench, "role": ROLE_OF.get(bench, "?"), "l1d_kib": size,
        "n_sp": len(runs), "coverage": round(cov, 4),
        "mpki": wsum("mpki"), "apki": wsum("apki"),
        "miss_rate": wsum("mpki") / wsum("apki"),
        "mpki_mshr": wsum("mpki_mshr"),
        "ipc": 1.0 / wsum("cpi"),
        "l2_apki": wsum("l2_apki"), "l2_mpki": wsum("l2_mpki"),
        "dram_gbps": wsum("dram_bytes") / wsum("secs") / 1e9,
        "_per_sp": [(w, m["mpki"]) for w, m in runs],
    }


def plot(rows, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    color = {"target": "#2a78d6", "control": "#1baf7a", "excluded": "#9a9a96"}
    ink, muted, grid = "#1f1f1e", "#6b6b68", "#e4e4e1"
    benches = [b for b in BENCH_ORDER if any(r["bench"] == b for r in rows)]
    ncol = 4
    nrow = (len(benches) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(12, 2.7 * nrow),
                             squeeze=False)
    fig.patch.set_facecolor("#fcfcfb")
    for ax, b in zip(axes.flat, benches):
        pts = sorted((r["l1d_kib"], r["mpki"]) for r in rows if r["bench"] == b)
        xs, ys = zip(*pts)
        role = ROLE_OF.get(b, "?")
        ax.set_facecolor("#fcfcfb")
        ax.axvspan(32, 48, color=grid, alpha=0.7, lw=0, zorder=0)
        ax.plot(xs, ys, color=color[role], lw=2, marker="o", ms=5,
                markeredgecolor="#fcfcfb", markeredgewidth=1.5, zorder=3)
        d = dict(pts)
        if 32 in d and 48 in d:
            # Improvement: MPKI reduction relative to 32 KiB (> 0 = fewer misses)
            impr = round((d[32] - d[48]) / d[32] * 100, 1) + 0.0 if d[32] else 0.0
            ax.set_title(f"{b}  ({role})\nΔMPKI 32→48 = {d[48] - d[32]:+.2f}"
                         f"  ({impr:.1f}%)",
                         fontsize=9, color=ink, loc="left")
        else:
            ax.set_title(f"{b}  ({role})", fontsize=9, color=ink, loc="left")
        ax.set_xticks(SIZES)
        ax.set_ylim(bottom=0)
        ax.tick_params(colors=muted, labelsize=8, length=0)
        ax.grid(axis="y", color=grid, lw=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(grid)
    for ax in axes.flat[len(benches):]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("L1D demand MPKI", fontsize=8, color=muted)
    for ax in axes[-1, :]:
        ax.set_xlabel("L1D size (KiB, 64 sets)", fontsize=8, color=muted)
    fig.suptitle("L1D MPKI vs. size, SimPoint-weighted (3 GHz, 1 MiB L2, "
                 "no prefetch); shaded = SRC window 32→48 KiB",
                 fontsize=10, color=ink, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_png, dpi=150)


def main():
    rows, warnings = [], []
    benches = sorted(d for d in os.listdir(KNEE)
                     if os.path.isdir(os.path.join(KNEE, d)))
    benches.sort(key=lambda b: BENCH_ORDER.index(b) if b in BENCH_ORDER else 99)
    for b in benches:
        weights = load_weights(b)
        per_size = []
        for s in SIZES:
            r = aggregate(b, s, weights, warnings)
            if r:
                rows.append(r)
                per_size.append(r)
        # Non-monotonic MPKI: a bigger cache should not miss more.
        for a, c in zip(per_size, per_size[1:]):
            if c["mpki"] > a["mpki"] * 1.01 + 0.01:
                warnings.append(f"{b}: weighted MPKI rises {a['l1d_kib']}k->"
                                f"{c['l1d_kib']}k ({a['mpki']:.3f}->{c['mpki']:.3f})")
        # Per-SimPoint non-monotonicity (informational).
        by_sp = {}
        for r in per_size:
            for i, (w, m) in enumerate(r["_per_sp"]):
                by_sp.setdefault(i, []).append((r["l1d_kib"], m, w))
        for i, seq in by_sp.items():
            for (s1, m1, w), (s2, m2, _) in zip(seq, seq[1:]):
                if m2 > m1 * 1.05 + 0.05 and w >= 0.05:
                    warnings.append(f"{b} sp_{i} (w={w:.2f}): MPKI rises "
                                    f"{s1}k->{s2}k ({m1:.2f}->{m2:.2f})")

    fields = ["bench", "role", "l1d_kib", "n_sp", "coverage", "mpki",
              "apki", "miss_rate", "mpki_mshr", "ipc", "l2_apki", "l2_mpki", "dram_gbps"]
    out_csv = os.path.join(RESULTS, "results.csv")
    with open(out_csv, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                         for k, v in r.items()})

    # Console table: MPKI per size + the SRC-window deltas.
    get = {(r["bench"], r["l1d_kib"]): r for r in rows}
    hdr = (f"{'bench':<13}{'role':<8}" + "".join(f"{s:>7}k" for s in SIZES)
           + f"{'dMPKI32>48':>11}{'dIPC32>48':>10}{'dMPKI48>64':>11}"
           + f"{'MR32':>7}{'MR48':>7}{'IPC32':>7}{'L2APKI32':>9}{'L2APKI48':>9}{'DRAM32':>8}")
    print("L1D demand MPKI (demandMisses/kinst), SimPoint-weighted")
    print(hdr)
    print("-" * len(hdr))
    for b in benches:
        if (b, 32) not in get or (b, 48) not in get:
            continue
        r32, r48 = get[(b, 32)], get[(b, 48)]
        line = f"{b:<13}{ROLE_OF.get(b, '?'):<8}"
        line += "".join(f"{get[(b, s)]['mpki']:>8.2f}" if (b, s) in get
                        else f"{'-':>8}" for s in SIZES)
        d_ipc = (r48["ipc"] / r32["ipc"] - 1) * 100
        d64 = (get[(b, 64)]["mpki"] - r48["mpki"]) if (b, 64) in get else float("nan")
        line += (f"{r48['mpki'] - r32['mpki']:>11.2f}{d_ipc:>9.2f}%"
                 f"{d64:>11.2f}{r32['miss_rate'] * 100:>6.2f}%"
                 f"{r48['miss_rate'] * 100:>6.2f}%{r32['ipc']:>7.3f}{r32['l2_apki']:>9.1f}"
                 f"{r48['l2_apki']:>9.1f}{r32['dram_gbps']:>8.2f}")
        print(line)

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print("  " + w)
    else:
        print("\nno warnings")

    out_png = os.path.join(RESULTS, "mpki_vs_size.png")
    plot(rows, out_png)
    print(f"\nwrote {out_csv}\nwrote {out_png}")


if __name__ == "__main__":
    sys.exit(main())
