#!/usr/bin/env python3
"""Analyze the SRC DRT sweep against the non-forgetting SRAM baselines.

Configurations per benchmark (3 GHz, 1 MiB L2, 64-set L1D, no prefetch):
  SRAM 32 KiB 8-way   sram_mpki_sweep/runs/<b>/sp_<i>/l1d_32k
  SRC  48 KiB 12-way  src_sweep/runs/<b>/sp_<i>/drt_<N>us   (N = 5, 10, 20)
  SRAM 48 KiB 12-way  sram_mpki_sweep/runs/<b>/sp_<i>/l1d_48k

SimPoint weighting and the base metrics (MPKI, miss rate, IPC, L2 APKI/MPKI,
DRAM GB/s) are exactly those of sram_mpki_sweep/analyze.py, imported from it.
SRC metrics are weighted per kilo-instruction the same way:
  retention-miss fraction = retentionMisses / demandAccesses
  refreshes/kinst (forced, opportunistic, inline), refresh stall cycles/kinst
Backdoor counters (lazy writebacks, expired in-flight hits, invariant
violations, ...) are also summed as raw counts over all SimPoints.

"gain kept" = (MPKI_32 - MPKI_SRC) / (MPKI_32 - MPKI_48): the share of the
SRAM 32->48 KiB MPKI reduction that SRC 48 KiB keeps (shown only where the
32->48 reduction is at least MIN_GAIN MPKI).

Writes results/results.csv and results/*.png, prints the tables.
Env SRC_RUNS / SRC_RESULTS override the SRC runs / output dirs (testing).
Env SRC_EXCLUDE=b1,b2 leaves those benchmarks out (e.g. runs still going).
"""
import csv
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_RUNS = os.environ.get("SRC_RUNS", os.path.join(HERE, "runs"))
SRAM_RUNS = os.path.join(ROOT, "sram_mpki_sweep", "runs")
RESULTS = os.environ.get("SRC_RESULTS", os.path.join(HERE, "results"))
DRTS_US = [5, 10, 20]
EXCLUDE = {b for b in os.environ.get("SRC_EXCLUDE", "").split(",") if b}
MIN_GAIN = 0.5   # MPKI

_spec = importlib.util.spec_from_file_location(
    "sram_analyze", os.path.join(ROOT, "sram_mpki_sweep", "analyze.py"))
sram = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sram)

# (key, label, run subdirectory, DRT in us or None)
CONFIGS = ([("sram32", "SRAM 32 KiB", "l1d_32k", None)] +
           [(f"src{d}", f"SRC 48 KiB @ {d} us", f"drt_{d}us", d)
            for d in DRTS_US] +
           [("sram48", "SRAM 48 KiB", "l1d_48k", None)])

R = "board.cache_hierarchy.l1dcache.retention."
# Weighted per kinst
SRC_PKI = {
    "rmiss_pki": "retentionMisses",
    "force_pki": "forceRefresh",
    "opp_pki": "oppRefresh",
    "inline_pki": "refreshInlineWrite",
    "inline_rd_pki": "refreshInlineRead",
    "stall_pki": "refreshStallCycles",
}
# Raw counts summed over SimPoints (expected 0, except clean evictions)
SRC_SUM = ["lazyWritebacks", "lazyWritebacksRead", "lazyWritebacksWrite",
           "expiredInflightHits", "expiredDirtyEvictions",
           "expiredFunctional", "expiredSnoops", "daemonRevivedDirty",
           "invariantViolations", "inlineTooLate"]
# All L1D writebacks (normal ones included), the scale for the backdoors
WB = "board.cache_hierarchy.l1dcache.writebacks::total"


def run_dir(bench, i, cfg):
    _, _, sub, drt = cfg
    base = SRC_RUNS if drt else SRAM_RUNS
    return os.path.join(base, bench, f"sp_{i}", sub)


def aggregate(bench, cfg, weights, warnings):
    runs = []
    for i, w in enumerate(weights):
        p = os.path.join(run_dir(bench, i, cfg), "stats.txt")
        stats = sram.read_second_dump(p) if os.path.exists(p) else None
        if stats is None:
            warnings.append(f"{bench} sp_{i} {cfg[0]}: missing/incomplete")
            continue
        m = sram.run_metrics(stats)
        if cfg[3]:
            for k, name in SRC_PKI.items():
                m[k] = stats.get(R + name, 0.0) / m["insts"] * 1e3
            for name in SRC_SUM:
                m[name] = stats.get(R + name, 0.0)
            m["l1d_writebacks"] = stats.get(WB, 0.0)
        runs.append((w, m))
    if not runs:
        return None
    cov = sum(w for w, _ in runs)
    if cov < 0.99:
        warnings.append(f"{bench} {cfg[0]}: SimPoint coverage {cov:.3f}")

    def wsum(key):
        return sum(w * m[key] for w, m in runs) / cov

    row = {
        "bench": bench, "role": sram.ROLE_OF.get(bench, "?"),
        "config": cfg[0], "drt_us": cfg[3] or 0,
        "n_sp": len(runs), "coverage": round(cov, 4),
        "ipc": 1.0 / wsum("cpi"),
        "mpki": wsum("mpki"), "apki": wsum("apki"),
        "miss_rate": wsum("mpki") / wsum("apki"),
        "mpki_mshr": wsum("mpki_mshr"),
        "l2_apki": wsum("l2_apki"), "l2_mpki": wsum("l2_mpki"),
        "dram_gbps": wsum("dram_bytes") / wsum("secs") / 1e9,
    }
    if cfg[3]:
        for k in SRC_PKI:
            row[k] = wsum(k)
        row["refresh_pki"] = row["force_pki"] + row["opp_pki"] + \
            row["inline_pki"] + row["inline_rd_pki"]
        row["rmiss_frac"] = row["rmiss_pki"] / row["apki"]
        for name in SRC_SUM + ["l1d_writebacks"]:
            row[name] = sum(m[name] for _, m in runs)
        if row["invariantViolations"] > 0:
            warnings.append(f"{bench} {cfg[0]}: "
                            f"{row['invariantViolations']:.0f} invariant "
                            f"violations")
    return row


def gain_kept(g, b, key):
    m32, m48 = g[(b, "sram32")]["mpki"], g[(b, "sram48")]["mpki"]
    if (b, key) not in g or m32 - m48 < MIN_GAIN:
        return None
    return (m32 - g[(b, key)]["mpki"]) / (m32 - m48)


# ---------------------------------------------------------------- plots
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#1f1f1e", "#6b6b68", "#e4e4e1"
# Reference palette slots 1-3 (validated all-pairs): one hue per DRT,
# the same in every chart
DRT_COLOR = {5: "#2a78d6", 10: "#eb6834", 20: "#1baf7a"}


def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def plot_mpki(g, benches, out):
    plt = _plt()
    ncol = 4
    nrow = (len(benches) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(12, 2.8 * nrow),
                             squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    for ax, b in zip(axes.flat, benches):
        _style(ax)
        pts = [(d, g[(b, f"src{d}")]["mpki"]) for d in DRTS_US
               if (b, f"src{d}") in g]
        m32, m48 = g[(b, "sram32")]["mpki"], g[(b, "sram48")]["mpki"]
        ax.axhline(m32, color=MUTED, lw=1.2, ls="--", zorder=1)
        ax.axhline(m48, color=MUTED, lw=1.2, ls=":", zorder=1)
        lo = min([m48] + [y for _, y in pts])
        hi = max([m32] + [y for _, y in pts])
        if pts:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, color=MUTED, lw=1.5, zorder=2)
            ax.scatter(xs, ys, c=[DRT_COLOR[d] for d in xs], s=50,
                       edgecolors=SURFACE, linewidths=1.5, zorder=3)
            # Each dot: the share of the SRAM 32->48 KiB reduction kept
            for d, y in pts:
                k = gain_kept(g, b, f"src{d}")
                if k is None:
                    continue
                ax.annotate(f"{k * 100:.0f}%", (d, y), xytext=(0, 7),
                            textcoords="offset points", ha="center",
                            fontsize=7.5, color=DRT_COLOR[d],
                            fontweight="bold", zorder=4)
        if m32 - m48 < MIN_GAIN:
            ax.text(0.98, 0.95, f"no %: SRAM 32->48K gain\n< {MIN_GAIN} MPKI",
                    transform=ax.transAxes, ha="right", va="top",
                    fontsize=7, color=MUTED)
        ax.set_title(f"{b} ({sram.ROLE_OF.get(b, '?')})", fontsize=9,
                     color=INK, loc="left")
        ax.set_xscale("log", base=2)
        ax.set_xticks(DRTS_US)
        ax.set_xticklabels([f"{d}" for d in DRTS_US])
        ax.set_xlim(DRTS_US[0] / 1.25, DRTS_US[-1] * 1.25)
        pad = max((hi - lo) * 0.25, 0.05 * hi, 0.01)
        ax.set_ylim(max(0, lo - pad), hi + pad)
    for ax in axes.flat[len(benches):]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("L1D demand MPKI", fontsize=8, color=MUTED)
    for ax in axes[-1, :]:
        ax.set_xlabel("DRT (us)", fontsize=8, color=MUTED)
    fig.suptitle("SRC 48 KiB L1D demand MPKI vs. DRT, SimPoint-weighted "
                 "(3 GHz, 1 MiB L2, no prefetch). Dashed: SRAM 32 KiB, "
                 "dotted: SRAM 48 KiB", fontsize=10, color=INK, x=0.01,
                 y=0.995, ha="left")
    fig.text(0.01, 0.962,
             "% at each dot = gain kept = (MPKI_SRAM32 - MPKI_SRC) / "
             "(MPKI_SRAM32 - MPKI_SRAM48): the share of the misses that "
             "going from SRAM 32 KiB to 48 KiB removes, which SRC 48 KiB "
             "still removes at that DRT.\n"
             "100% = as good as SRAM 48 KiB, 0% = no better than SRAM "
             "32 KiB. Above 100% at 5 us (femflow, roms) is a timing "
             "artifact: refresh stalls cut secondary misses to lines "
             "already in flight.",
             fontsize=8, color=MUTED, ha="left", va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _grouped(ax, benches, values, ylabel):
    """values[d] = list per bench (None = missing). Bars from zero."""
    n = len(DRTS_US)
    width = 0.8 / n
    for j, d in enumerate(DRTS_US):
        xs = [i + (j - (n - 1) / 2) * width for i in range(len(benches))]
        ys = [v if v is not None else 0.0 for v in values[d]]
        ax.bar(xs, ys, width=width - 0.03, color=DRT_COLOR[d],
               label=f"SRC @ {d} us", zorder=2, linewidth=0)
    ax.axhline(0, color=MUTED, lw=0.8, zorder=2)
    ax.set_xticks(range(len(benches)))
    ax.set_xticklabels([b.replace("_r", "") for b in benches], fontsize=8,
                       rotation=30, ha="right")
    ax.set_ylabel(ylabel, fontsize=8, color=MUTED)


def plot_ipc(g, benches, out):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(12, 5.5))
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    base = {b: g[(b, "sram32")]["ipc"] for b in benches}
    vals = {d: [(g[(b, f"src{d}")]["ipc"] / base[b] - 1) * 100
                if (b, f"src{d}") in g else None for b in benches]
            for d in DRTS_US}
    _grouped(ax, benches, vals, "IPC change vs. SRAM 32 KiB (%, symlog)")
    # Changes span 0.01% to 40%: log beyond +-0.1%, linear inside it
    ax.set_yscale("symlog", linthresh=0.1, linscale=0.5)
    ticks = [-50, -20, -10, -5, -2, -1, -0.5, -0.2, -0.1, 0, 0.1, 0.5]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t:g}%" for t in ticks])
    ax.set_ylim(-60, 1)
    ax.grid(axis="y", which="minor", visible=False)
    n = len(DRTS_US)
    width = 0.8 / n
    for j, d in enumerate(DRTS_US):
        for i, v in enumerate(vals[d]):
            if v is None:
                continue
            x = i + (j - (n - 1) / 2) * width
            ax.text(x, v * 1.12 if v < -0.1 else v - 0.03,
                    f"{v:.1f}" if abs(v) >= 0.95 else f"{v:.2f}",
                    ha="center", va="top", fontsize=6, color=INK,
                    rotation=90)
    # SRAM 48 KiB: a neutral tick across each benchmark's group
    for i, b in enumerate(benches):
        v = (g[(b, "sram48")]["ipc"] / base[b] - 1) * 100
        ax.plot([i - 0.42, i + 0.42], [v, v], color=INK, lw=1.5, zorder=4,
                label="SRAM 48 KiB" if i == 0 else None)
    ax.legend(fontsize=8, frameon=False, ncol=4, loc="lower right",
              labelcolor=INK)
    ax.set_title("IPC of SRC 48 KiB and SRAM 48 KiB relative to SRAM 32 KiB "
                 "(same area as SRC 48 KiB), SimPoint-weighted. Log axis "
                 "beyond +-0.1%, linear inside", fontsize=10,
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_refresh(g, benches, out):
    plt = _plt()
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, key, ylabel, title in (
            (axes[0], "refresh_pki", "refreshes / kinst",
             "Line refreshes per kilo-instruction (forced + opportunistic + "
             "inline)"),
            (axes[1], "stall_pki", "stall cycles / kinst",
             "Cycles demand hits waited for a refresh, per "
             "kilo-instruction")):
        _style(ax)
        vals = {d: [g[(b, f"src{d}")][key] if (b, f"src{d}") in g else None
                    for b in benches] for d in DRTS_US}
        _grouped(ax, benches, vals, ylabel)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
    axes[0].legend(fontsize=8, frameon=False, ncol=3, loc="upper right",
                   labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


# Backdoor grid: (label, key, True if a nonzero count loses dirty data)
BACKDOORS = [
    ("lazy WB\n(read)", "lazyWritebacksRead", True),
    ("lazy WB\n(write)", "lazyWritebacksWrite", True),
    ("expired dirty\nevictions", "expiredDirtyEvictions", True),
    ("daemon revived\ndirty", "daemonRevivedDirty", True),
    ("invariant\nviolations", "invariantViolations", True),
    ("expired\nin-flight hits", "expiredInflightHits", False),
    ("inline\ntoo late", "inlineTooLate", False),
    ("expired\nsnoops", "expiredSnoops", False),
    ("expired\nfunctional", "expiredFunctional", False),
]
BAD, WARN = "#d6453d", "#e8a33a"


def _count(v):
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e4:
        return f"{v / 1e3:.0f}K"
    return f"{v:.0f}"


def plot_backdoors(g, benches, out):
    """Raw counts, summed over every SimPoint, one cell per bench x DRT."""
    plt = _plt()
    groups = [("all L1D\nwritebacks", "l1d_writebacks", None)] + BACKDOORS
    nd = len(DRTS_US)
    ncols = len(groups) * nd
    fig, ax = plt.subplots(figsize=(15, 0.42 * len(benches) + 2.6))
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    gap = 0.35
    xpos = {}
    for gi, (_, key, _) in enumerate(groups):
        for j, d in enumerate(DRTS_US):
            xpos[(key, d)] = gi * (nd + gap) + j
    for bi, b in enumerate(benches):
        for _, key, loses in groups:
            for d in DRTS_US:
                r = g.get((b, f"src{d}"))
                x, y = xpos[(key, d)], bi
                if r is None:
                    ax.text(x, y, "-", ha="center", va="center",
                            fontsize=7, color=MUTED)
                    continue
                v = r[key]
                if loses is None:
                    face, ink = "#eeeeec", INK
                elif v == 0:
                    face, ink = SURFACE, "#b5b5b1"
                else:
                    face, ink = (BAD if loses else WARN), "white"
                ax.add_patch(plt.Rectangle((x - 0.48, y - 0.45), 0.96, 0.9,
                                           facecolor=face, edgecolor=GRID,
                                           lw=0.6))
                ax.text(x, y, _count(v), ha="center", va="center",
                        fontsize=7, color=ink,
                        fontweight="normal" if v == 0 else "bold")
    for gi, (label, key, loses) in enumerate(groups):
        x0 = xpos[(key, DRTS_US[0])]
        ax.text(x0 + (nd - 1) / 2, -1.25, label, ha="center", va="bottom",
                fontsize=8, color=BAD if loses else INK)
    ax.set_xticks([xpos[(k, d)] for _, k, _ in groups for d in DRTS_US])
    ax.set_xticklabels([f"{d}" for _ in groups for d in DRTS_US],
                       fontsize=7, color=MUTED)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(benches)))
    ax.set_yticklabels([f"{b.replace('_r', '')} ({sram.ROLE_OF.get(b, '?')})"
                        for b in benches], fontsize=8, color=INK)
    ax.set_xlim(-0.6, ncols + (len(groups) - 1) * gap - 0.4)
    ax.set_ylim(len(benches) - 0.5, -2.1)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("SRC 48 KiB backdoor counters, raw counts summed over all "
                 "SimPoints (each 100M instructions measured). Column = "
                 "DRT in us", fontsize=10, color=INK, loc="left", pad=6)
    fig.text(0.01, 0.01,
             "Red headers: a nonzero count means dirty data was lost or "
             "resurrected (should be 0). Black headers: expired clean data "
             "was used or a store came too late (no data loss while "
             "invariant violations = 0). Grey column: all L1D writebacks, "
             "for scale.", fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    os.makedirs(RESULTS, exist_ok=True)
    warnings, rows = [], []
    benches = [b for b in sram.BENCH_ORDER
               if os.path.isdir(os.path.join(SRC_RUNS, b))
               and b not in EXCLUDE]
    if EXCLUDE:
        print(f"excluded: {', '.join(sorted(EXCLUDE))}\n")
    for b in benches:
        weights = sram.load_weights(b)
        for cfg in CONFIGS:
            r = aggregate(b, cfg, weights, warnings)
            if r:
                rows.append(r)
    g = {(r["bench"], r["config"]): r for r in rows}
    benches = [b for b in benches
               if (b, "sram32") in g and (b, "sram48") in g]

    fields = ["bench", "role", "config", "drt_us", "n_sp", "coverage", "ipc",
              "mpki", "apki", "miss_rate", "mpki_mshr", "l2_apki", "l2_mpki",
              "dram_gbps", "rmiss_frac", "refresh_pki"] + list(SRC_PKI) + \
        SRC_SUM + ["l1d_writebacks"]
    out_csv = os.path.join(RESULTS, "results.csv")
    with open(out_csv, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (round(v, 6) if isinstance(v, float) else v)
                         for k, v in r.items()})

    keys = [c[0] for c in CONFIGS]
    head = "".join(f"{k:>9}" for k in keys)

    print("IPC (1 / weighted CPI); SRC columns also show the change vs "
          "SRAM 32 KiB")
    print(f"{'bench':<13}{'role':<9}{head}" +
          "".join(f"{'d' + k:>9}" for k in keys[1:]))
    for b in benches:
        base = g[(b, "sram32")]["ipc"]
        line = f"{b:<13}{sram.ROLE_OF.get(b, '?'):<9}"
        line += "".join(f"{g[(b, k)]['ipc']:>9.3f}" if (b, k) in g
                        else f"{'-':>9}" for k in keys)
        line += "".join(f"{(g[(b, k)]['ipc'] / base - 1) * 100:>8.2f}%"
                        if (b, k) in g else f"{'-':>9}" for k in keys[1:])
        print(line)

    print("\nL1D demand MPKI, and the share of the SRAM 32->48 KiB MPKI "
          f"reduction SRC keeps (only if it is >= {MIN_GAIN} MPKI)")
    print(f"{'bench':<13}{head}" +
          "".join(f"{'kept' + str(d):>9}" for d in DRTS_US))
    for b in benches:
        line = f"{b:<13}" + "".join(
            f"{g[(b, k)]['mpki']:>9.2f}" if (b, k) in g else f"{'-':>9}"
            for k in keys)
        for d in DRTS_US:
            k = gain_kept(g, b, f"src{d}")
            line += f"{k * 100:>8.0f}%" if k is not None else f"{'-':>9}"
        print(line)

    print("\nSRC cost per DRT (weighted per kinst; retention-miss fraction "
          "of demand accesses)")
    print(f"{'bench':<13}{'DRT':>4}{'rMiss%':>8}{'force':>8}{'opp':>8}"
          f"{'inline':>8}{'stallCyc':>9}{'L2APKI':>8}{'DRAMGB/s':>9}"
          f"{'lazyWB':>7}{'inflt':>7}{'viol':>6}")
    for b in benches:
        for d in DRTS_US:
            r = g.get((b, f"src{d}"))
            if not r:
                continue
            print(f"{b:<13}{d:>4}{r['rmiss_frac'] * 100:>7.3f}%"
                  f"{r['force_pki']:>8.2f}{r['opp_pki']:>8.2f}"
                  f"{r['inline_pki']:>8.3f}{r['stall_pki']:>9.1f}"
                  f"{r['l2_apki']:>8.1f}{r['dram_gbps']:>9.2f}"
                  f"{r['lazyWritebacks']:>7.0f}"
                  f"{r['expiredInflightHits']:>7.0f}"
                  f"{r['invariantViolations']:>6.0f}")

    # Sanity: SRC should not miss more with a longer DRT
    for b in benches:
        seq = [(d, g[(b, f"src{d}")]["mpki"]) for d in DRTS_US
               if (b, f"src{d}") in g]
        for (d1, m1), (d2, m2) in zip(seq, seq[1:]):
            if m2 > m1 * 1.01 + 0.01:
                warnings.append(f"{b}: SRC MPKI rises {d1}->{d2} us "
                                f"({m1:.3f}->{m2:.3f})")

    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings:
            print("  " + w)
    else:
        print("\nno warnings")

    if benches:
        plot_mpki(g, benches, os.path.join(RESULTS, "mpki_vs_drt.png"))
        plot_ipc(g, benches, os.path.join(RESULTS, "ipc_vs_sram32.png"))
        plot_refresh(g, benches, os.path.join(RESULTS,
                                              "refresh_overhead.png"))
        plot_backdoors(g, benches, os.path.join(RESULTS, "backdoors.png"))
    print(f"\nwrote {out_csv} and 4 PNGs in {RESULTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
