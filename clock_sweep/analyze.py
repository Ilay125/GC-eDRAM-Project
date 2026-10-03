#!/usr/bin/env python3
"""Analyze the CLOCK keep-rule sweep (clock_sweep/run_sweep.sh).

  A    SRAM 32 KiB 4c                       alecto_sweep_notso/A/runs
  C0   SRAM 48 KiB 5c                       alecto_sweep_notso/C0/runs
  C1   SRC 48 KiB 5c, top-4 MRU + dirty     alecto_sweep_notso/C1/runs
  CLK, CLK25, CLK50                         clock_sweep/<cfg>/runs
       SRC 48 KiB 5c, active invalidation, reference bit, top_mru 0, bit
       also cleared at 0 / 25% / 50% of DRT

SimPoint weighting and base metrics come from sram_mpki_sweep/analyze.py.
"Gain kept" = (MPKI_A - MPKI_X) / (MPKI_A - MPKI_C0) on primary MPKI
(demand MSHR misses): the share of the 32 -> 48 KiB SRAM miss reduction a
configuration keeps. Benchmarks whose 32 -> 48 KiB gap is below
MIN_GAP_PKI have no meaningful gain and get none. "All" rows: refreshes
are the mean over benchmarks, gain kept is sum(A - X) / sum(A - C0) over
the benchmarks with a gap, IPC is the geomean ratio.

Writes clock_sweep/results/{results.csv,report.md,tradeoff.png}.
Partial sweeps work: a benchmark is used once all its SimPoints are done
in every configuration.
"""
import csv
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(HERE, "results")
BASE = os.path.join(ROOT, "alecto_sweep_notso")
BENCHES = ["palm_r", "flightdm_r", "femflow_r", "cactus_r", "fotonik3d_r",
           "cpython_r", "sqlite_r", "roms_r", "nest_r", "zstd_r",
           "sealcrypto_r"]
CONFIGS = [("A", BASE), ("C0", BASE), ("C1", BASE), ("CLK", HERE),
           ("CLK05", HERE), ("CLK10", HERE), ("CLK15", HERE),
           ("CLK25", HERE), ("CLK50", HERE)]
# The finer clear ages (second run) are used once they are complete
OPTIONAL = {"CLK05", "CLK10", "CLK15"}
# CLOCK configs in clear-age order, with their age
AGES = [("CLK", 0.0), ("CLK05", 0.05), ("CLK10", 0.10), ("CLK15", 0.15),
        ("CLK25", 0.25), ("CLK50", 0.5)]
# femflow sp_0 crashed in the first run (write buffer, fixed): its first-run
# configs come from the rerun with the fixed binary
WBFIX = os.path.join(HERE, "wbfix")
RERUN = {("femflow_r", c) for c in ("CLK", "CLK25", "CLK50")}
MIN_GAP_PKI = 0.1

_spec = importlib.util.spec_from_file_location(
    "sram_analyze", os.path.join(ROOT, "sram_mpki_sweep", "analyze.py"))
sram = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sram)

R = "board.cache_hierarchy.l1dcache.retention."
SRC_PKI = {
    "refresh_pki": ["totalRefreshes"],
    "refresh_dirty_pki": ["refreshDirty"],
    "refresh_clean_pki": ["refreshClean"],
    "wasted_pki": ["refreshDeadClean", "refreshDeadDirty"],
    "needed_pki": ["refreshNeededClean", "refreshNeededDirty"],
    "inval_pki": ["activeInvalidations"],
    "coldwb_pki": ["coldDirtyWritebacks"],
    "early_miss_pki": ["activeInvalidateEarlyMisses"],
    "rmiss_pki": ["retentionMisses"],
    "stall_pki": ["refreshStallCycles"],
}
# Must be 0 everywhere (sums over SimPoints)
MUST_BE_ZERO = ["invariantViolations", "lazyWritebacks",
                "expiredDirtyEvictions", "daemonRevivedDirty",
                "visitIntervalOverruns"]


def aggregate(bench, cfg, root, weights):
    runs = []
    for i, w in enumerate(weights):
        p = os.path.join(root, cfg, "runs", bench, f"sp_{i}", "stats.txt")
        stats = sram.read_second_dump(p) if os.path.exists(p) else None
        if stats is None:
            return None
        m = sram.run_metrics(stats)
        for k, names in SRC_PKI.items():
            m[k] = sum(stats.get(R + n, 0.0) for n in names) / m["insts"] * 1e3
        for n in MUST_BE_ZERO:
            m[n] = stats.get(R + n, 0.0)
        runs.append((w, m))
    cov = sum(w for w, _ in runs)

    def wsum(key):
        return sum(w * m[key] for w, m in runs) / cov

    row = {"bench": bench, "config": cfg, "ipc": 1.0 / wsum("cpi"),
           "mpki_primary": wsum("mpki_mshr"), "l2_mpki": wsum("l2_mpki")}
    for k in SRC_PKI:
        row[k] = wsum(k)
    for n in MUST_BE_ZERO:
        row[n] = sum(m[n] for _, m in runs)
    return row


def main():
    global CONFIGS, SRC
    os.makedirs(RESULTS, exist_ok=True)
    rows, skipped = {}, []
    for b in BENCHES:
        w = sram.load_weights(b)
        got = {c: aggregate(b, c, WBFIX if (b, c) in RERUN else root, w)
               for c, root in CONFIGS}
        if any(v is None for c, v in got.items() if c not in OPTIONAL):
            skipped.append(b)
            continue
        rows[b] = got
    if not rows:
        print("no benchmark complete yet")
        return
    # An optional config is shown only if it is complete everywhere
    have = {c for c, _ in CONFIGS
            if all(rows[b][c] is not None for b in rows)}
    CONFIGS = [(c, r) for c, r in CONFIGS if c in have]
    SRC = ["C1"] + [c for c, _ in AGES if c in have]
    for b in rows:
        rows[b] = {c: v for c, v in rows[b].items() if c in have}

    # Gain kept per benchmark
    for b, got in rows.items():
        gap = got["A"]["mpki_primary"] - got["C0"]["mpki_primary"]
        for c, r in got.items():
            r["gap"] = gap
            r["gain_kept"] = ((got["A"]["mpki_primary"] - r["mpki_primary"])
                              / gap if gap >= MIN_GAP_PKI else None)
            r["ipc_vs_C1"] = r["ipc"] / got["C1"]["ipc"]
            r["ipc_vs_C0"] = r["ipc"] / got["C0"]["ipc"]

    with open(os.path.join(RESULTS, "results.csv"), "w", newline="") as f:
        keys = list(next(iter(rows.values()))["CLK"].keys())
        wr = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        wr.writeheader()
        for got in rows.values():
            for r in got.values():
                wr.writerow(r)

    # Aggregates over benchmarks
    agg = {}
    gapped = [b for b in rows if rows[b]["A"]["gap"] >= MIN_GAP_PKI]
    for c, _ in CONFIGS:
        rs = [rows[b][c] for b in rows]
        agg[c] = {
            "refresh_pki": sum(r["refresh_pki"] for r in rs) / len(rs),
            "wasted_pki": sum(r["wasted_pki"] for r in rs) / len(rs),
            "gain_kept": (sum(rows[b]["A"]["mpki_primary"] -
                              rows[b][c]["mpki_primary"] for b in gapped) /
                          sum(rows[b]["A"]["gap"] for b in gapped)
                          if gapped else None),
            "ipc_vs_C1": math.exp(sum(math.log(r["ipc_vs_C1"]) for r in rs)
                                  / len(rs)),
            "ipc_vs_C0": math.exp(sum(math.log(r["ipc_vs_C0"]) for r in rs)
                                  / len(rs)),
        }

    def pct(x, signed=False):
        if x is None:
            return "–"
        return f"{(x - 1) * 100:+.2f}%" if signed else f"{x * 100:.0f}%"

    out = []
    out.append("# CLOCK keep-rule sweep\n")
    out.append(f"Benchmarks complete: {len(rows)} of {len(BENCHES)}"
               + (f" (pending: {', '.join(skipped)})" if skipped else "")
               + "\n")
    out.append("## Trade-off: refreshes vs MPKI gain kept\n")
    out.append("| bench | 32→48 gap (PKI) | " + " | ".join(
        f"{c} refr / kept" for c in SRC) + " |")
    out.append("|---|---|" + "---|" * len(SRC))
    for b, got in rows.items():
        cells = [f"{got[c]['refresh_pki']:.1f} / {pct(got[c]['gain_kept'])}"
                 for c in SRC]
        out.append(f"| {b} | {got['A']['gap']:.2f} | " + " | ".join(cells)
                   + " |")
    out.append("| **all** | | " + " | ".join(
        f"**{agg[c]['refresh_pki']:.1f} / {pct(agg[c]['gain_kept'])}**"
        for c in SRC) + " |")
    out.append("\n## IPC vs C1 and vs SRAM 48 KiB (C0)\n")
    out.append("| bench | " + " | ".join(
        f"{c} vs C1 / vs C0" for c in SRC[1:]) + " |")
    out.append("|---|" + "---|" * len(SRC[1:]))
    for b, got in rows.items():
        out.append(f"| {b} | " + " | ".join(
            f"{pct(got[c]['ipc_vs_C1'], True)} / "
            f"{pct(got[c]['ipc_vs_C0'], True)}" for c in SRC[1:]) + " |")
    out.append("| **geomean** | " + " | ".join(
        f"**{pct(agg[c]['ipc_vs_C1'], True)} / "
        f"{pct(agg[c]['ipc_vs_C0'], True)}**" for c in SRC[1:]) + " |")
    out.append("\n## Details per configuration (per kilo-instruction)\n")
    keys = ["refresh_pki", "refresh_dirty_pki", "refresh_clean_pki",
            "wasted_pki", "needed_pki", "inval_pki", "coldwb_pki",
            "early_miss_pki", "rmiss_pki", "stall_pki", "mpki_primary",
            "l2_mpki"]
    for b, got in rows.items():
        out.append(f"\n### {b}\n")
        out.append("| | " + " | ".join(c for c, _ in CONFIGS) + " |")
        out.append("|---|" + "---|" * len(CONFIGS))
        for k in keys:
            out.append(f"| {k} | " + " | ".join(
                f"{got[c][k]:.3f}" for c, _ in CONFIGS) + " |")
    out.append("\n## Must be 0 (sums over SimPoints)\n")
    bad = [(b, c, n, rows[b][c][n]) for b in rows for c in SRC
           for n in MUST_BE_ZERO if rows[b][c][n] > 0]
    out.append("All 0." if not bad else "\n".join(
        f"- {b} {c}: {n} = {v:.0f}" for b, c, n, v in bad))
    report = "\n".join(out) + "\n"
    open(os.path.join(RESULTS, "report.md"), "w").write(report)
    print(report)
    plot(rows, agg, gapped)


def plot(rows, agg, gapped):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Ordinal blue ramp for the clear age (palette steps 250-700, light =
    # no clear); C1 is a gray reference, not a series
    STEP = {"CLK": "#86b6ef", "CLK05": "#6da7ec", "CLK10": "#3987e5",
            "CLK15": "#256abf", "CLK25": "#184f95", "CLK50": "#0d366b"}
    clk = [c for c in SRC if c != "C1"]
    COL = {c: STEP[c] for c in clk}
    AGE = dict(AGES)
    LAB = {c: "no clear" if AGE[c] == 0 else f"clear {AGE[c]:.0%}"
           for c in clk}
    TXT = {c: "0" if AGE[c] == 0 else f"{AGE[c]:.2f}".lstrip("0").rstrip("0")
           for c in clk}
    INK, MUTED, GRID, SURF = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"

    panels = [("all benchmarks", agg)] + [
        (b.replace("_r", ""), rows[b]) for b in gapped]
    n = len(panels)
    ncol = 4
    nrow = math.ceil(n / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 2.9 * nrow),
                             sharey=True, facecolor=SURF)
    axes = axes.flatten()
    for ax, (title, d) in zip(axes, panels):
        ax.set_facecolor(SURF)
        xs = [d[c]["refresh_pki"] for c in clk]
        ys = [100 * d[c]["gain_kept"] for c in clk]
        ax.plot(xs, ys, color=STEP["CLK10"], lw=2, zorder=2)
        for c, x, y in zip(clk, xs, ys):
            ax.scatter([x], [y], s=64, color=COL[c], edgecolor=SURF,
                       linewidth=2, zorder=3)
        ax.scatter([d["C1"]["refresh_pki"]], [100 * d["C1"]["gain_kept"]],
                   s=64, marker="s", color=MUTED, edgecolor=SURF,
                   linewidth=2, zorder=3)
        ax.annotate("C1", (d["C1"]["refresh_pki"],
                           100 * d["C1"]["gain_kept"]),
                    textcoords="offset points", xytext=(6, -10),
                    fontsize=8, color=MUTED)
        for c, x, y in zip(clk, xs, ys):
            ax.annotate(TXT[c], (x, y), textcoords="offset points",
                        xytext=(6, 4), fontsize=8, color=INK)
        ax.axhline(100, color=GRID, lw=1, zorder=1)
        ax.axhline(0, color=MUTED, lw=1, zorder=1)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlim(left=0)
        ax.grid(axis="y", color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#c3c2b7")
        ax.tick_params(colors=MUTED, labelsize=8)
    for ax in axes[n:]:
        ax.axis("off")
    for ax in axes[::ncol]:
        ax.set_ylabel("MPKI gain kept (%)", fontsize=9, color=INK)
    for ax in axes[(nrow - 1) * ncol:]:
        ax.set_xlabel("refreshes per kilo-instruction", fontsize=9,
                      color=INK)
    handles = [plt.Line2D([], [], marker="o", ls="", color=COL[c],
                          markersize=7, label=LAB[c]) for c in COL]
    handles.append(plt.Line2D([], [], marker="s", ls="", color=MUTED,
                              markersize=7, label="C1 (top-4 MRU + dirty)"))
    fig.legend(handles=handles, loc="upper center",
               ncol=len(handles), frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("CLOCK reference bit, top_mru 0: refreshes vs share of the "
                 "32→48 KiB SRAM miss reduction kept (100% = SRAM 48 KiB, "
                 "0% = SRAM 32 KiB)", fontsize=10, color=INK, y=1.04)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS, "tradeoff.png"), dpi=160,
                bbox_inches="tight", facecolor=SURF)


if __name__ == "__main__":
    main()
