#!/usr/bin/env python3
"""Compare the RTL-aligned SRC with the CLK reference on the smoke runs.

Change vs CLK (exact ages, CleanEvict drops) of CLK-SD (silent clean drops
only) and CLK-RTL (silent drops + quantized ages, F 29), per SimPoint.
Writes rtl_align/smoke/compare.png and compare.md.

  venv/bin/python rtl_align/plot_compare.py
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from smoke_report import H, R, RUNS, SMOKE, load  # noqa: E402

# Reference palette, categorical slots 1-2 (validated pair), light surface
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#e4e3df"
SERIES = {"CLK-SD": "#2a78d6", "CLK-RTL": "#eb6834"}
LABEL = {"CLK-SD": "silent clean drops only",
         "CLK-RTL": "silent drops + quantized ages (full RTL)"}


def metrics(s):
    k = s["simInsts"] / 1000.0
    refr = (s.get(R + "forceRefresh", 0) + s.get(R + "oppRefresh", 0))
    return {
        "IPC": s["board.processor.cores.core.ipc"],
        "L1D demand MPKI": s[H + "l1dcache.demandMisses::total"] / k,
        "L1D primary MPKI": s[H + "l1dcache.demandMshrMisses::total"] / k,
        "refreshes /kinst": refr / k,
        "drops /kinst (clean + dirty)":
            (s.get(R + "activeInvalidations", 0) +
             s.get(R + "coldDirtyWritebacks", 0)) / k,
        "L2 accesses /kinst": s[H + "l2cache.overallAccesses::total"] / k,
        "L2 bus CleanEvict /kinst":
            s[H + "l2bus.transDist::CleanEvict"] / k,
        "snoops reaching L1D /kinst":
            s.get(H + "l2bus.snoop_filter.totSnoops", 0) / k,
        "hit stall cycles /kinst": s.get(R + "refreshStallCycles", 0) / k,
    }


def short(run):
    b, sp = run.rsplit("_sp", 1)
    return f"{b.removesuffix('_r')} sp{sp}"


def main():
    data = {c: {r: metrics(load(os.path.join(SMOKE, c, r, "stats.txt")))
                for r in RUNS} for c in ("CLK", "CLK-SD", "CLK-RTL")}
    names = list(data["CLK"][RUNS[0]])

    # Table: absolute CLK and CLK-RTL, % change (CLK-SD in between)
    md = ["# CLK vs RTL-aligned CLK (smoke runs, strict)", "",
          "CLK = exact ages, a CleanEvict per clean drop (reference). "
          "SD = + silent clean drops. RTL = SD + quantized ages "
          "(1024-cycle epochs, 5-bit stamp, F 29). Δ = change vs CLK.", ""]
    for name in names:
        md.append(f"## {name}")
        md.append("")
        md.append("| SimPoint | CLK | CLK-SD | CLK-RTL | Δ SD | Δ RTL |")
        md.append("|---|---|---|---|---|---|")
        for r in RUNS:
            v = [data[c][r][name] for c in ("CLK", "CLK-SD", "CLK-RTL")]
            fmt = "{:.4f}" if name == "IPC" else "{:.3f}"
            d = [("–" if v[0] == 0 else f"{100 * (x - v[0]) / v[0]:+.2f}%")
                 for x in v[1:]]
            md.append(f"| {short(r)} | " + " | ".join(fmt.format(x)
                      for x in v) + f" | {d[0]} | {d[1]} |")
        md.append("")
    open(os.path.join(SMOKE, "compare.md"), "w").write("\n".join(md))

    # Plot: % change vs CLK, one panel per metric (own scale each), the
    # snoop count in absolute terms since CLK is ~0 on some SimPoints
    pct = [n for n in names if n != "snoops reaching L1D /kinst"]
    panels = pct + ["snoops reaching L1D /kinst"]
    ncol = 3
    nrow = (len(panels) + ncol - 1) // ncol
    fig, axes = plt.subplots(nrow, ncol, figsize=(18, 4.3 * nrow),
                             facecolor=SURFACE)
    labels = [short(r) for r in RUNS]
    x = range(len(RUNS))
    for ax, name in zip(axes.flat, panels):
        ax.set_facecolor(SURFACE)
        absolute = name not in pct
        cfgs = ["CLK", "CLK-SD", "CLK-RTL"] if absolute else \
            ["CLK-SD", "CLK-RTL"]
        w = 0.8 / len(cfgs)
        for j, c in enumerate(cfgs):
            vals = []
            for r in RUNS:
                base, v = data["CLK"][r][name], data[c][r][name]
                vals.append(v if absolute else
                            (100 * (v - base) / base if base else 0.0))
            xs = [i + (j - (len(cfgs) - 1) / 2) * w for i in x]
            color = SERIES.get(c, "#9b9a95")
            ax.bar(xs, vals, w - 0.03, color=color, zorder=2,
                   label=("CLK (reference)" if c == "CLK" else LABEL[c]))
            for xi, v in zip(xs, vals):
                if absolute:
                    txt = f"{v:.0f}" if v >= 10 else f"{v:.1f}"
                elif abs(v) < 0.05:
                    txt = "0%"
                else:
                    txt = f"{v:+.0f}%" if abs(v) >= 10 else f"{v:+.1f}%"
                ax.annotate(txt, (xi, v), xytext=(0, 3 if v >= 0 else -3),
                            textcoords="offset points", ha="center",
                            va="bottom" if v >= 0 else "top", fontsize=7,
                            color=TEXT2)
        ax.axhline(0, color=TEXT2, lw=0.8, zorder=3)
        ax.set_title(name + ("" if absolute else "  (change vs CLK)"),
                     fontsize=10.5, color=TEXT, loc="left")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=8.5, color=TEXT2)
        ax.tick_params(axis="y", labelsize=8, colors=TEXT2)
        if not absolute:
            ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"
                                                if abs(v) >= 1 else
                                                f"{v:+.1f}%"))
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(GRID)
        lo, hi = ax.get_ylim()
        pad = 0.12 * (hi - lo)
        ax.set_ylim(lo - (pad if lo < 0 else 0), hi + pad)
    for ax in list(axes.flat)[len(panels):]:
        ax.set_visible(False)

    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[c])
               for c in ("CLK-SD", "CLK-RTL")]
    handles.append(plt.Rectangle((0, 0), 1, 1, color="#9b9a95"))
    fig.legend(handles, [LABEL["CLK-SD"], LABEL["CLK-RTL"],
                         "CLK reference (absolute panel only)"],
               loc="upper center", ncol=3, frameon=False, fontsize=10,
               bbox_to_anchor=(0.5, 0.995), labelcolor=TEXT)
    fig.suptitle("RTL-aligned SRC vs CLK reference: 48 KiB, DRT 10 µs, "
                 "5 SimPoints, strict (0 checker violations)",
                 y=1.03, fontsize=12.5, color=TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = os.path.join(SMOKE, "compare.png")
    fig.savefig(out, dpi=140, bbox_inches="tight", facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()
