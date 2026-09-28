#!/usr/bin/env python3
"""Compare SRC variants side by side at one DRT (default 10 us).

usage: compare_variants.py [--drt 10] [--out DIR] NAME=RESULTS_DIR ...
  e.g. compare_variants.py b1=src_sweep/results b8=src_sweep/results_b8

Each RESULTS_DIR holds a results.csv written by analyze.py (run with
SRC_RUNS/SRC_RESULTS for that variant). The SRAM 32/48 KiB rows come from
the same CSVs. Prints, per benchmark: IPC change vs SRAM 32 KiB, gain kept
(demand and MSHR MPKI), refreshes and stall cycles per kinst, the
opportunistic share of daemon refreshes, and violations / lazy writebacks.
Writes compare_<drt>us.png (IPC change and MSHR gain kept per variant).
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_GAIN = 0.3   # MSHR MPKI; below it "gain kept" is not shown
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#1f1f1e", "#6b6b68", "#e4e4e1"
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#8a5cc2", "#c9a227"]


def load(path):
    rows = {}
    with open(os.path.join(path, "results.csv")) as f:
        for r in csv.DictReader(f):
            for k, v in r.items():
                try:
                    r[k] = float(v)
                except (TypeError, ValueError):
                    pass
            rows[(r["bench"], r["config"])] = r
    return rows


def kept(s32, s48, r, key):
    d = s32[key] - s48[key]
    return None if d < MIN_GAIN else (s32[key] - r[key]) / d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drt", type=int, default=10)
    ap.add_argument("--out", default=os.path.join(HERE, "results_compare"))
    ap.add_argument("variants", nargs="+")
    a = ap.parse_args()
    variants = [v.split("=", 1) for v in a.variants]
    data = {n: load(p) for n, p in variants}
    cfg = f"src{a.drt}"
    first = data[variants[0][0]]
    benches = []
    for (b, c) in first:
        if c == "sram32" and b not in benches and \
                all((b, cfg) in d for d in data.values()):
            benches.append(b)

    print(f"SRC variants at DRT = {a.drt} us "
          "(IPC change vs SRAM 32 KiB; kept = share of the SRAM 32->48 KiB "
          "MPKI reduction kept)")
    hdr = (f"{'bench':<13}{'variant':<10}{'dIPC%':>8}{'kept':>7}"
           f"{'keptMSHR':>9}{'refr/ki':>8}{'opp%':>6}{'stall/ki':>9}"
           f"{'rMiss%':>8}{'lazyWB':>7}{'viol':>6}")
    print(hdr)
    ipc, keptm = {}, {}
    for b in benches:
        s32, s48 = first[(b, "sram32")], first[(b, "sram48")]
        for n, _ in variants:
            r = data[n][(b, cfg)]
            dipc = (r["ipc"] / s32["ipc"] - 1) * 100
            k = kept(s32, s48, r, "mpki")
            km = kept(s32, s48, r, "mpki_mshr")
            daemon = r["force_pki"] + r["opp_pki"]
            opp = r["opp_pki"] / daemon * 100 if daemon else 0.0
            ipc[(b, n)], keptm[(b, n)] = dipc, km
            ks = f"{k * 100:>6.0f}%" if k is not None else f"{'-':>7}"
            kms = f"{km * 100:>8.0f}%" if km is not None else f"{'-':>9}"
            print(f"{b:<13}{n:<10}{dipc:>7.2f}%{ks}{kms}"
                  f"{r['refresh_pki']:>8.2f}{opp:>5.0f}%{r['stall_pki']:>9.1f}"
                  f"{r['rmiss_frac'] * 100:>7.3f}%"
                  f"{r['lazyWritebacks']:>7.0f}"
                  f"{r['invariantViolations']:>6.0f}")
        print(f"{'':<13}{'SRAM 48':<10}"
              f"{(s48['ipc'] / s32['ipc'] - 1) * 100:>7.2f}%")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(a.out, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    nv = len(variants)
    width = 0.8 / nv
    for ax, vals, ylabel, title in (
            (axes[0], ipc, "IPC change vs. SRAM 32 KiB (%)",
             f"IPC of SRC 48 KiB variants at DRT = {a.drt} us relative to "
             "SRAM 32 KiB (black tick: SRAM 48 KiB)"),
            (axes[1], keptm, "gain kept (%)",
             "Share of the SRAM 32->48 KiB MSHR-miss reduction that SRC "
             "keeps (100% = as good as SRAM 48 KiB)")):
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=MUTED, labelsize=8, length=0)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for j, (n, _) in enumerate(variants):
            xs = [i + (j - (nv - 1) / 2) * width for i in range(len(benches))]
            ys = [vals[(b, n)] if vals[(b, n)] is not None else 0.0
                  for b in benches]
            if vals is keptm:
                ys = [y * 100 for y in ys]
            ax.bar(xs, ys, width=width - 0.03, color=COLORS[j % len(COLORS)],
                   label=n, zorder=2, linewidth=0)
            for x, y, b in zip(xs, ys, benches):
                if vals[(b, n)] is None:
                    continue
                ax.text(x, y, f"{y:.1f}" if vals is ipc else f"{y:.0f}",
                        ha="center", va="bottom" if y >= 0 else "top",
                        fontsize=6, color=INK)
        ax.axhline(0, color=MUTED, lw=0.8, zorder=2)
        ax.set_ylabel(ylabel, fontsize=8, color=MUTED)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
    for i, b in enumerate(benches):
        s32, s48 = first[(b, "sram32")], first[(b, "sram48")]
        v = (s48["ipc"] / s32["ipc"] - 1) * 100
        axes[0].plot([i - 0.42, i + 0.42], [v, v], color=INK, lw=1.2,
                     zorder=4)
    axes[1].axhline(100, color=MUTED, lw=0.8, ls=":", zorder=2)
    axes[1].set_xticks(range(len(benches)))
    axes[1].set_xticklabels([b.replace("_r", "") for b in benches],
                            fontsize=8, rotation=30, ha="right")
    axes[0].legend(fontsize=8, frameon=False, ncol=nv, loc="lower left",
                   labelcolor=INK)
    fig.tight_layout()
    out = os.path.join(a.out, f"compare_{a.drt}us.png")
    fig.savefig(out, dpi=150)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
