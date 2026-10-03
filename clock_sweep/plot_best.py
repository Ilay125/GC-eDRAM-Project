#!/usr/bin/env python3
"""MPKI and IPC of one CLOCK point against SRAM 32 KiB (A) and 48 KiB (C0).

  venv/bin/python clock_sweep/analyze.py       # refreshes results.csv
  CLOCK_BEST=CLK25 venv/bin/python clock_sweep/plot_best.py

Writes clock_sweep/results/best_{mpki,ipc}_<cfg>.png. SPEC benchmarks
complete for every configuration (analyze.py), SimPoint-weighted. Style
follows alecto_sweep/plot_partial.py.
"""
import csv
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
BEST = os.environ.get("CLOCK_BEST", "CLK25")
AGE = {"CLK": "no clear", "CLK05": "clear 5%", "CLK10": "clear 10%",
       "CLK15": "clear 15%", "CLK25": "clear 25%", "CLK50": "clear 50%"}

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#1f1f1e", "#6b6b68", "#e4e4e1"
# A = neutral baseline; C0 = slot 1; the SRC point = slot 3 (as C1 before)
COLOR = {"A": "#a3a29b", "C0": "#2a78d6", BEST: "#1baf7a"}
HATCH = {"A": "", "C0": "////", BEST: "\\\\\\\\"}
LABEL = {"A": "SRAM 32 KiB, 4 cyc",
         "C0": "SRAM 48 KiB, 5 cyc",
         BEST: f"SRC 48 KiB, 5 cyc, 10 µs, CLOCK ({AGE[BEST]})"}
CFGS = ["A", "C0", BEST]
plt.rcParams["hatch.linewidth"] = 1.0


def load():
    g = {}
    for r in csv.DictReader(open(os.path.join(RES, "results.csv"))):
        g[(r["bench"], r["config"])] = {k: float(r[k])
                                        for k in ("ipc", "mpki_primary")}
    benches = [b for b in dict.fromkeys(b for b, _ in g)
               if all((b, c) in g for c in CFGS)]
    return benches, g


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def geomean(xs):
    return math.exp(sum(map(math.log, xs)) / len(xs))


def swatch(c):
    return plt.Rectangle((0, 0), 1, 1, facecolor=COLOR[c], hatch=HATCH[c],
                         edgecolor=SURFACE, linewidth=0)


def grouped(ax, names, series):
    """series: [(cfg, [y per group])]; returns bar x positions per cfg."""
    n = len(series)
    w = 0.8 / n
    pos = {}
    for j, (c, ys) in enumerate(series):
        xs = [i + (j - (n - 1) / 2) * w for i in range(len(ys))]
        ax.bar(xs, ys, w * 0.9, color=COLOR[c], edgecolor=SURFACE,
               linewidth=1, hatch=HATCH[c])
        pos[c] = xs
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=30, ha="right", color=INK)
    return pos


def footer(fig, benches, extra):
    fig.text(0.01, 0.01, f"SPEC 2026, {len(benches)} benchmarks, "
             "SimPoint-weighted. " + extra + " Alecto core, 256 KiB L2, no "
             "prefetcher, 3 GHz.", fontsize=7.5, color=MUTED)


def mpki_plot(benches, g):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    names = [b.replace("_r", "") for b in benches]
    series = [(c, [g[(b, c)]["mpki_primary"] for b in benches])
              for c in CFGS]
    pos = grouped(ax, names, series)
    # Selective labels: the SRC bar's MPKI change vs SRAM 32 KiB
    for x, b in zip(pos[BEST], benches):
        y = g[(b, BEST)]["mpki_primary"]
        d = y / g[(b, "A")]["mpki_primary"] - 1
        ax.text(x, y, f"{d * 100:+.1f}%", ha="center", va="bottom",
                fontsize=6.5, color=MUTED)
    ax.set_ylabel("primary L1D MPKI", fontsize=9, color=MUTED)
    ax.set_title("L1D misses: SRC with the CLOCK keep rule vs SRAM 32 and "
                 "48 KiB", fontsize=10, color=INK, loc="left")
    fig.legend([swatch(c) for c in CFGS], [LABEL[c] for c in CFGS],
               loc="upper center", ncol=3, frameon=False, fontsize=9,
               labelcolor=INK)
    footer(fig, benches, "Primary misses = real fetches from L2. Labels: "
           "SRC change vs SRAM 32 KiB.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    out = os.path.join(RES, f"best_mpki_{BEST}.png")
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    return out


def ipc_plot(benches, g):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    names = [b.replace("_r", "") for b in benches] + ["geomean"]
    series = []
    for c in ("C0", BEST):
        r = [g[(b, c)]["ipc"] / g[(b, "A")]["ipc"] for b in benches]
        series.append((c, [(x - 1) * 100 for x in r]
                       + [(geomean(r) - 1) * 100]))
    pos = grouped(ax, names, series)
    # Selective labels: every SRC bar, and both geomeans
    for c, ys in series:
        for k, (x, y) in enumerate(zip(pos[c], ys)):
            if c == BEST or k == len(ys) - 1:
                ax.text(x, y, f"{y:+.1f}", ha="center",
                        va="top" if y < 0 else "bottom", fontsize=6.5,
                        color=INK)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_ylabel("IPC change vs SRAM 32 KiB (%)", fontsize=9, color=MUTED)
    ax.set_title("IPC: SRC with the CLOCK keep rule vs SRAM 48 KiB, both "
                 "relative to SRAM 32 KiB (0)", fontsize=10, color=INK,
                 loc="left")
    fig.legend([swatch(c) for c in ("C0", BEST)],
               [LABEL[c] for c in ("C0", BEST)], loc="upper center",
               ncol=2, frameon=False, fontsize=9, labelcolor=INK)
    footer(fig, benches, "Baseline SRAM 32 KiB, 4-cycle L1D. Labels: SRC on "
           "every bar, both on the geomean.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    out = os.path.join(RES, f"best_ipc_{BEST}.png")
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    return out


def main():
    benches, g = load()
    print(f"{BEST}: {len(benches)} benchmarks: {', '.join(benches)}")
    print(mpki_plot(benches, g))
    print(ipc_plot(benches, g))


if __name__ == "__main__":
    main()
