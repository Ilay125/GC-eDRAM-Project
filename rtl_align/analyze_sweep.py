#!/usr/bin/env python3
"""Analyze the RTL-aligned SRC sweep (rtl_align/run_sweep.sh) against the
existing runs of the same core (Alecto, no TSO, L2 256 KiB, 3 GHz):

  A    SRAM 32 KiB 8-way, 4-cycle     spec_add/A/runs (fixed binary; gcc and
                                       omnetpp: alecto_sweep_notso/A/runs)
  C0   SRAM 48 KiB 12-way, 5-cycle    alecto_sweep_notso/C0/runs
  C1   SRC 48 KiB, exact ages, top-4 MRU kept, no active invalidation
                                       alecto_sweep_notso/C1/runs
  CLK  SRC 48 KiB, CLOCK keep rule, exact ages, CleanEvict drops
                                       clock_sweep/CLK/runs (11 benchmarks)
  RTL  SRC 48 KiB, CLOCK + silent clean drops + quantized ages (F 29)
                                       rtl_align/sweep/CLK-RTL/runs

SimPoint weighting as everywhere (sram_mpki_sweep/analyze.py): IPC =
1 / sum(w * CPI), per-kinst metrics = sum(w * x). A benchmark is reported
once every RTL SimPoint is done. Writes rtl_align/sweep/results/
{results.csv,report.md,overview.png}.

  venv/bin/python rtl_align/analyze_sweep.py
"""
import csv
import importlib.util
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(HERE, "sweep", "results")

_spec = importlib.util.spec_from_file_location(
    "sram_analyze", os.path.join(ROOT, "sram_mpki_sweep", "analyze.py"))
sram = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sram)

BENCHES = ["palm_r", "flightdm_r", "femflow_r", "cactus_r", "fotonik3d_r",
           "cpython_r", "sqlite_r", "roms_r", "nest_r", "zstd_r",
           "sealcrypto_r", "gcc_r", "omnetpp_r"]
CONFIGS = ["A", "C0", "C1", "CLK", "RTL"]
LABELS = {"A": "SRAM 32 KiB 4c", "C0": "SRAM 48 KiB 5c",
          "C1": "SRC 48 KiB C1 (exact, top-4 MRU)",
          "CLK": "SRC 48 KiB CLK (exact, CleanEvict)",
          "RTL": "SRC 48 KiB RTL-aligned"}
H = "board.cache_hierarchy."
R = H + "l1dcache.retention."
SRC_PKI = {
    "refresh_pki": ["forceRefresh", "oppRefresh"],
    "drop_pki": ["activeInvalidations", "coldDirtyWritebacks"],
    "stall_pki": ["refreshStallCycles"],
    "rmiss_pki": ["retentionMisses"],
}
CHECKERS = ["invariantViolations", "lazyWritebacks", "expiredDirtyEvictions",
            "daemonRevivedDirty", "expiredPrefetchDirty",
            "activeInvalidateExpired", "activeInvalidateInflight",
            "visitIntervalOverruns", "quantExpiredAtVisit", "epochWrapRisk"]


def run_dir(cfg, bench):
    if cfg == "A":
        p = os.path.join(ROOT, "spec_add", "A", "runs", bench)
        if os.path.isdir(p):
            return p
        return os.path.join(ROOT, "alecto_sweep_notso", "A", "runs", bench)
    if cfg in ("C0", "C1"):
        return os.path.join(ROOT, "alecto_sweep_notso", cfg, "runs", bench)
    if cfg == "CLK":
        return os.path.join(ROOT, "clock_sweep", "CLK", "runs", bench)
    return os.path.join(HERE, "sweep", "CLK-RTL", "runs", bench)


def aggregate(bench, cfg, weights):
    runs = []
    for i, w in enumerate(weights):
        p = os.path.join(run_dir(cfg, bench), f"sp_{i}", "stats.txt")
        stats = sram.read_second_dump(p) if os.path.exists(p) else None
        if stats is None:
            return None
        m = sram.run_metrics(stats)
        k = m["insts"] / 1e3
        m["l2bus_pki"] = stats.get(H + "l2bus.pktCount::total", 0) / k
        m["cleanevict_pki"] = stats.get(H + "l2bus.transDist::CleanEvict",
                                        0) / k
        for key, names in SRC_PKI.items():
            m[key] = sum(stats.get(R + n, 0.0) for n in names) / k
        m["checkers"] = sum(stats.get(R + n, 0.0) for n in CHECKERS)
        runs.append((w, m))
    cov = sum(w for w, _ in runs)

    def wsum(key):
        return sum(w * m[key] for w, m in runs) / cov

    row = {"bench": bench, "config": cfg, "ipc": 1.0 / wsum("cpi"),
           "mpki": wsum("mpki"), "mpki_primary": wsum("mpki_mshr"),
           "l2_apki": wsum("l2_apki"), "l2bus_pki": wsum("l2bus_pki"),
           "cleanevict_pki": wsum("cleanevict_pki"),
           "checkers": sum(m["checkers"] for _, m in runs)}
    for key in SRC_PKI:
        row[key] = wsum(key)
    return row


def geomean(xs):
    xs = [x for x in xs if x is not None and x > 0]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else None


def pct(new, base):
    return None if new is None or not base else 100.0 * (new / base - 1)


def fp(v, digits=2):
    return "–" if v is None else f"{v:+.{digits}f}%"


def main():
    os.makedirs(RESULTS, exist_ok=True)
    rows, missing = {}, []
    for b in BENCHES:
        w = sram.load_weights(b)
        if aggregate(b, "RTL", w) is None:
            missing.append(b)
            continue
        for c in CONFIGS:
            rows[(b, c)] = aggregate(b, c, w)
    done = [b for b in BENCHES if b not in missing]

    with open(os.path.join(RESULTS, "results.csv"), "w", newline="") as f:
        keys = list(next(iter(rows.values())).keys()) if rows else []
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        for r in rows.values():
            if r:
                wr.writerow(r)

    def get(b, c, k):
        r = rows.get((b, c))
        return r[k] if r else None

    md = ["# RTL-aligned SRC sweep (SimPoint-weighted)", "",
          f"Benchmarks complete: {len(done)} of {len(BENCHES)}" +
          (f" (incomplete: {', '.join(missing)})" if missing else ""), "",
          "Configs: " + "; ".join(f"**{c}** = {LABELS[c]}" for c in CONFIGS)
          + ". CLK runs exist for 11 benchmarks only (older binary, before "
          "the write-buffer fix).", "",
          "## IPC", "",
          "| bench | IPC A | C0 vs A | C1 vs A | CLK vs A | **RTL vs A** | "
          "RTL vs C0 | RTL vs CLK |", "|---|---|---|---|---|---|---|---|"]
    ratios = {k: [] for k in ("C0", "C1", "CLK", "RTL", "RTL/C0", "RTL/CLK")}
    for b in done:
        a = get(b, "A", "ipc")
        vals = {c: get(b, c, "ipc") for c in CONFIGS}
        for c in ("C0", "C1", "CLK", "RTL"):
            if vals[c]:
                ratios[c].append(vals[c] / a)
        ratios["RTL/C0"].append(vals["RTL"] / vals["C0"])
        if vals["CLK"]:
            ratios["RTL/CLK"].append(vals["RTL"] / vals["CLK"])
        md.append(f"| {b} | {a:.4f} | {fp(pct(vals['C0'], a))} | "
                  f"{fp(pct(vals['C1'], a))} | {fp(pct(vals['CLK'], a))} | "
                  f"**{fp(pct(vals['RTL'], a))}** | "
                  f"{fp(pct(vals['RTL'], vals['C0']))} | "
                  f"{fp(pct(vals['RTL'], vals['CLK']))} |")
    g = {k: geomean(v) for k, v in ratios.items()}
    md.append("| **geomean** | | " + " | ".join(
        ("**" if k == "RTL" else "") + fp(None if g[k] is None else
                                           100 * (g[k] - 1)) +
        ("**" if k == "RTL" else "")
        for k in ("C0", "C1", "CLK", "RTL", "RTL/C0", "RTL/CLK")) + " |")
    md += ["", "CLK geomean covers its 11 benchmarks only.", "",
           "## Primary L1D MPKI and the gain kept", "",
           "Primary MPKI = demand MSHR misses (real L2 fetches). Kept = "
           "(A − X) / (A − C0).", "",
           "| bench | A | C0 | C1 | CLK | RTL | kept C1 | kept CLK | "
           "**kept RTL** |", "|---|---|---|---|---|---|---|---|---|"]
    for b in done:
        v = {c: get(b, c, "mpki_primary") for c in CONFIGS}
        gap = v["A"] - v["C0"]

        def kept(x):
            return "–" if x is None or gap < 0.05 else \
                f"{100 * (v['A'] - x) / gap:.0f}%"
        md.append(f"| {b} | " + " | ".join(
            "–" if v[c] is None else f"{v[c]:.2f}" for c in CONFIGS) +
            f" | {kept(v['C1'])} | {kept(v['CLK'])} | **{kept(v['RTL'])}** |")
    tot = {c: sum(get(b, c, "mpki_primary") or 0 for b in done)
           for c in ("A", "C0", "RTL")}
    if tot["A"] > tot["C0"]:
        md.append(f"| **sum** | {tot['A']:.1f} | {tot['C0']:.1f} | | | "
                  f"{tot['RTL']:.1f} | | | **"
                  f"{100 * (tot['A'] - tot['RTL']) / (tot['A'] - tot['C0']):.0f}"
                  "%** |")
    md += ["", "## L2 traffic and SRC activity (per kinst)", "",
           "| bench | L2 bus pkts A | C0 | RTL | CleanEvict A | RTL | "
           "refreshes CLK | RTL | drops CLK | RTL | stall cyc RTL | "
           "checkers RTL |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in done:
        def f1(c, k, d=1):
            x = get(b, c, k)
            return "–" if x is None else f"{x:.{d}f}"
        md.append(f"| {b} | {f1('A', 'l2bus_pki')} | {f1('C0', 'l2bus_pki')}"
                  f" | {f1('RTL', 'l2bus_pki')} | {f1('A', 'cleanevict_pki')}"
                  f" | {f1('RTL', 'cleanevict_pki')} | "
                  f"{f1('CLK', 'refresh_pki', 2)} | "
                  f"{f1('RTL', 'refresh_pki', 2)} | "
                  f"{f1('CLK', 'drop_pki', 2)} | {f1('RTL', 'drop_pki', 2)} | "
                  f"{f1('RTL', 'stall_pki', 2)} | "
                  f"{get(b, 'RTL', 'checkers'):.0f} |")
    open(os.path.join(RESULTS, "report.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))
    if done:
        plot(done, get, g)


def plot(done, get, g):
    SURFACE, TEXT, TEXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    # Color follows the entity (as in rtl_align/smoke/vs_sram.png)
    COL = {"C0": "#1baf7a", "RTL": "#eb6834"}
    names = [b.removesuffix("_r") for b in done] + ["geomean"]
    fig, axes = plt.subplots(3, 1, figsize=(16, 13), facecolor=SURFACE)
    panels = [
        ("IPC change vs SRAM 32 KiB", "ipc", ["C0", "RTL"]),
        ("primary L1D MPKI change vs SRAM 32 KiB", "mpki_primary",
         ["C0", "RTL"]),
        ("L2 bus packets per kinst, change vs SRAM 32 KiB", "l2bus_pki",
         ["C0", "RTL"]),
    ]
    for ax, (title, key, cfgs) in zip(axes, panels):
        ax.set_facecolor(SURFACE)
        w = 0.38
        for j, c in enumerate(cfgs):
            vals = [pct(get(b, c, key), get(b, "A", key)) for b in done]
            if key == "ipc":
                vals.append(100 * (g[c] - 1))
            else:
                vals.append(100 * (geomean([get(b, c, key) /
                                            get(b, "A", key)
                                            for b in done]) - 1))
            xs = [i + (j - 0.5) * w for i in range(len(names))]
            ax.bar(xs, vals, w - 0.03, color=COL[c], zorder=2,
                   label=LABELS[c])
            for xi, v in zip(xs, vals):
                txt = "0%" if abs(v) < 0.05 else (
                    f"{v:+.0f}%" if abs(v) >= 10 else f"{v:+.1f}%")
                ax.annotate(txt, (xi, v), xytext=(0, 3 if v >= 0 else -3),
                            textcoords="offset points", ha="center",
                            va="bottom" if v >= 0 else "top", fontsize=7,
                            color=TEXT2)
        ax.axhline(0, color=TEXT2, lw=0.8, zorder=3)
        ax.axvline(len(done) - 0.5, color=GRID, lw=1, zorder=1)
        ax.set_title(title, fontsize=11, color=TEXT, loc="left")
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=9, color=TEXT2)
        ax.tick_params(axis="y", labelsize=8, colors=TEXT2)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v:+.0f}%" if abs(v) >= 1 or v == 0
            else f"{v:+.1f}%"))
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(GRID)
        lo, hi = ax.get_ylim()
        pad = 0.1 * (hi - lo)
        ax.set_ylim(lo - (pad if lo < 0 else 0), hi + pad)
    handles = [plt.Rectangle((0, 0), 1, 1, color=COL[c]) for c in COL]
    fig.legend(handles, [LABELS[c] for c in COL], loc="upper center",
               ncol=2, frameon=False, fontsize=10.5,
               bbox_to_anchor=(0.5, 0.995), labelcolor=TEXT)
    fig.suptitle("RTL-aligned SRC 48 KiB vs SRAM 32 KiB, SimPoint-weighted "
                 "(Alecto core, DRT 10 µs)", y=1.02, fontsize=13, color=TEXT)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(RESULTS, "overview.png")
    fig.savefig(out, dpi=130, bbox_inches="tight", facecolor=SURFACE)
    print(out)


if __name__ == "__main__":
    main()
