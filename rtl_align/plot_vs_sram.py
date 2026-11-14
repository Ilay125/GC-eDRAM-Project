#!/usr/bin/env python3
"""RTL-aligned SRC 48 KiB vs SRAM 32 KiB (and SRAM 48 KiB, the ideal 48 KiB)
on the smoke SimPoints. Alecto core, no TSO, L2 256 KiB, 3 GHz.

  A   SRAM 32 KiB 8-way, 4-cycle L1D   spec_add/A/runs (fixed binary)
  C0  SRAM 48 KiB 12-way, 5-cycle L1D  alecto_sweep_notso/C0/runs
  RTL SRC 48 KiB 12-way, 5-cycle, 10 us, CLK + silent drops + quantized
      ages (F 29)                      rtl_align/smoke/CLK-RTL

Writes rtl_align/smoke/vs_sram.png and vs_sram.md.

  venv/bin/python rtl_align/plot_vs_sram.py
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from plot_compare import GRID, SURFACE, TEXT, TEXT2, short  # noqa: E402
from smoke_report import H, R, RUNS, SMOKE, load  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Color follows the entity: RTL keeps slot 2 (orange) from compare.png,
# SRAM 48 KiB takes slot 3 (aqua); slots 1-3 validate all-pairs
SERIES = {"C0": "#1baf7a", "RTL": "#eb6834"}
LABEL = {"C0": "SRAM 48 KiB, 5-cycle (ideal 48 KiB)",
         "RTL": "SRC 48 KiB, RTL-aligned (CLK + silent drops + epochs)"}


def path(cfg, run):
    b, sp = run.rsplit("_sp", 1)
    if cfg == "A":
        return os.path.join(ROOT, "spec_add/A/runs", b, f"sp_{sp}")
    if cfg == "C0":
        return os.path.join(ROOT, "alecto_sweep_notso/C0/runs", b, f"sp_{sp}")
    return os.path.join(SMOKE, "CLK-RTL", run)


def metrics(s):
    k = s["simInsts"] / 1000.0
    return {
        "IPC": s["board.processor.cores.core.ipc"],
        "L1D primary MPKI": s[H + "l1dcache.demandMshrMisses::total"] / k,
        "L1D demand MPKI": s[H + "l1dcache.demandMisses::total"] / k,
        "L2 accesses /kinst": s[H + "l2cache.overallAccesses::total"] / k,
        "L2 bus packets /kinst": s[H + "l2bus.pktCount::total"] / k,
        "refreshes /kinst": (s.get(R + "forceRefresh", 0) +
                             s.get(R + "oppRefresh", 0)) / k,
    }


def main():
    d = {c: {r: metrics(load(os.path.join(path(c, r), "stats.txt")))
             for r in RUNS} for c in ("A", "C0", "RTL")}
    names = list(d["A"][RUNS[0]])

    md = ["# SRC 48 KiB (RTL-aligned) vs SRAM 32 KiB", "",
          "A = SRAM 32 KiB 8-way 4-cycle (baseline, iso-area with the SRC). "
          "C0 = SRAM 48 KiB 12-way 5-cycle (ideal 48 KiB). RTL = SRC 48 KiB "
          "12-way 5-cycle, DRT 10 µs, CLK + silent clean drops + quantized "
          "ages (F 29). Δ = change vs A. Single SimPoints, not weighted.", ""]
    for n in names[:-1]:
        md += [f"## {n}", "", "| SimPoint | A (SRAM 32) | C0 (SRAM 48) | "
               "RTL (SRC 48) | Δ C0 | Δ RTL |", "|---|---|---|---|---|---|"]
        f = "{:.4f}" if n == "IPC" else "{:.3f}"
        for r in RUNS:
            a, c0, rt = (d[c][r][n] for c in ("A", "C0", "RTL"))
            md.append(f"| {short(r)} | {f.format(a)} | {f.format(c0)} | "
                      f"{f.format(rt)} | {100 * (c0 - a) / a:+.2f}% | "
                      f"{100 * (rt - a) / a:+.2f}% |")
        md.append("")
    md += ["## MPKI gain kept by the SRC (primary MPKI)", "",
           "(A − RTL) / (A − C0): the share of the ideal 32→48 KiB miss "
           "reduction the SRC keeps.", "",
           "| SimPoint | A − C0 | A − RTL | kept |", "|---|---|---|---|"]
    kept = {}
    for r in RUNS:
        a, c0, rt = (d[c][r]["L1D primary MPKI"] for c in ("A", "C0", "RTL"))
        gap = a - c0
        kept[r] = 100 * (a - rt) / gap if gap > 0.05 else None
        md.append(f"| {short(r)} | {gap:.3f} | {a - rt:.3f} | " +
                  (f"{kept[r]:.0f}%" if kept[r] is not None else
                   "– (no gap)") + " |")
    open(os.path.join(SMOKE, "vs_sram.md"), "w").write("\n".join(md) + "\n")

    panels = ["IPC", "L1D primary MPKI", "L1D demand MPKI",
              "L2 accesses /kinst", "L2 bus packets /kinst", "kept"]
    fig, axes = plt.subplots(2, 3, figsize=(18, 8.8), facecolor=SURFACE)
    labels = [short(r) for r in RUNS]
    for ax, n in zip(axes.flat, panels):
        ax.set_facecolor(SURFACE)
        if n == "kept":
            cfgs = ["RTL"]
            vals = {"RTL": [kept[r] if kept[r] is not None else 0.0
                            for r in RUNS]}
            title = "primary-MPKI gain kept vs SRAM 48 KiB (%)"
        else:
            cfgs = ["C0", "RTL"]
            vals = {c: [100 * (d[c][r][n] - d["A"][r][n]) / d["A"][r][n]
                        for r in RUNS] for c in cfgs}
            title = f"{n}  (change vs SRAM 32 KiB)"
        w = 0.8 / len(cfgs)
        for j, c in enumerate(cfgs):
            xs = [i + (j - (len(cfgs) - 1) / 2) * w for i in range(len(RUNS))]
            ax.bar(xs, vals[c], w - 0.03, color=SERIES[c], zorder=2)
            for i, (xi, v) in enumerate(zip(xs, vals[c])):
                if n == "kept":
                    txt = "no gap" if kept[RUNS[i]] is None else f"{v:.0f}%"
                elif abs(v) < 0.05:
                    txt = "0%"
                else:
                    txt = f"{v:+.0f}%" if abs(v) >= 10 else f"{v:+.1f}%"
                ax.annotate(txt, (xi, v), xytext=(0, 3 if v >= 0 else -3),
                            textcoords="offset points", ha="center",
                            va="bottom" if v >= 0 else "top", fontsize=7.5,
                            color=TEXT2)
        ax.axhline(0, color=TEXT2, lw=0.8, zorder=3)
        if n == "kept":
            ax.axhline(100, color=SERIES["C0"], lw=1, ls="--", zorder=1)
            ax.annotate("SRAM 48 KiB = 100%", (len(RUNS) - 0.5, 100),
                        xytext=(0, 3), textcoords="offset points",
                        ha="right", fontsize=8, color=TEXT2)
        ax.set_title(title, fontsize=10.5, color=TEXT, loc="left")
        ax.set_xticks(range(len(RUNS)))
        ax.set_xticklabels(labels, fontsize=8.5, color=TEXT2)
        ax.tick_params(axis="y", labelsize=8, colors=TEXT2)
        fmt = (lambda v, _: f"{v:.0f}%") if n == "kept" else \
            (lambda v, _: f"{v:+.0f}%" if abs(v) >= 1 or v == 0
             else f"{v:+.1f}%")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt))
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(GRID)
        lo, hi = ax.get_ylim()
        pad = 0.12 * (hi - lo)
        ax.set_ylim(lo - (pad if lo < 0 else 0), hi + pad)

    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[c])
               for c in ("C0", "RTL")]
    fig.legend(handles, [LABEL["C0"], LABEL["RTL"]], loc="upper center",
               ncol=2, frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.995),
               labelcolor=TEXT)
    fig.suptitle("48 KiB L1D vs SRAM 32 KiB baseline (4-cycle): Alecto core, "
                 "DRT 10 µs, 5 single SimPoints", y=1.03, fontsize=12.5,
                 color=TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(SMOKE, "vs_sram.png")
    fig.savefig(out, dpi=140, bbox_inches="tight", facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()
