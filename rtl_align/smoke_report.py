#!/usr/bin/env python3
"""RTL-alignment smoke report: one table per SimPoint, CLK vs CLK-SD vs
CLK-RTL (second stats dump). Writes rtl_align/smoke/report.md.

  venv/bin/python rtl_align/smoke_report.py
"""
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(ROOT, "smoke")
CFGS = ["CLK", "CLK-SD", "CLK-RTL"]
RUNS = ["palm_r_sp0", "flightdm_r_sp0", "roms_r_sp3", "zstd_r_sp0",
        "cpython_r_sp4"]
H = "board.cache_hierarchy."
R = H + "l1dcache.retention."

# Must all be 0 (the run is strict, so most of them would have panicked)
CHECKERS = ["invariantViolations", "lazyWritebacks", "retentionMisses",
            "expiredInflightHits", "expiredDirtyEvictions",
            "daemonRevivedDirty", "activeInvalidateExpired",
            "activeInvalidateInflight", "visitIntervalOverruns",
            "expiredPrefetchDirty", "quantExpiredAtVisit", "epochWrapRisk"]


def load(path):
    if not os.path.exists(path):
        return None
    text = open(path).read().split("Begin Simulation Statistics")
    if len(text) < 3:
        return None
    s = {}
    for line in text[2].splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                s[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return s


def status(d):
    log = os.path.join(d, "run.log")
    if not os.path.exists(log):
        return "missing"
    t = open(log).read()
    if "measurement complete" in t:
        return "ok"
    m = re.search(r"(panic|fatal|Assertion)[^\n]*", t)
    return m.group(0)[:150] if m else "running/incomplete"


def rows(s):
    k = s["simInsts"] / 1000.0

    def g(name, default=None):
        return s.get(name, default)

    def pki(name):
        v = g(name)
        return None if v is None else v / k

    fr = g(R + "forceRefresh", 0)
    fb = g(R + "activeWbFullKept", 0)
    sh = g(R + "activeKeptShared", 0)
    inf = g(R + "activeInvalidateInflight", 0)
    out = [
        ("IPC", g("board.processor.cores.core.ipc"), "{:.4f}"),
        ("L1D demand MPKI", pki(H + "l1dcache.demandMisses::total"),
         "{:.3f}"),
        ("L1D primary MPKI", pki(H + "l1dcache.demandMshrMisses::total"),
         "{:.3f}"),
        ("refresh forced /kinst", (fr - fb - sh - inf) / k, "{:.3f}"),
        ("refresh opportunistic /kinst", pki(R + "oppRefresh"), "{:.3f}"),
        ("refresh fallback (wb full) /kinst", fb / k, "{:.4f}"),
        ("refresh Shared kept /kinst", sh / k, "{:.4f}"),
        ("drop clean /kinst", pki(R + "activeInvalidations"), "{:.3f}"),
        ("  of which silent /kinst", pki(R + "silentCleanDrops"), "{:.3f}"),
        ("drop dirty (writeback) /kinst", pki(R + "coldDirtyWritebacks"),
         "{:.3f}"),
        ("L2 accesses /kinst", pki(H + "l2cache.overallAccesses::total"),
         "{:.3f}"),
        ("L2 bus CleanEvict /kinst", pki(H + "l2bus.transDist::CleanEvict"),
         "{:.3f}"),
        ("L2 bus WritebackDirty /kinst",
         pki(H + "l2bus.transDist::WritebackDirty"), "{:.3f}"),
        ("L2 bus snoops /kinst", pki(H + "l2bus.snoops"), "{:.3f}"),
        ("snoop filter snoops /kinst",
         pki(H + "l2bus.snoop_filter.totSnoops"), "{:.3f}"),
        ("hit stall cycles /kinst", pki(R + "refreshStallCycles"), "{:.3f}"),
        ("misses to a dropped line /kinst",
         pki(R + "activeInvalidateMisses"), "{:.3f}"),
        ("  before it would expire /kinst",
         pki(R + "activeInvalidateEarlyMisses"), "{:.3f}"),
        ("T_guard (cycles)", g(R + "tGuardCycles"), "{:.0f}"),
        ("deadline F (epochs)", g(R + "deadlineEpochs"), "{:.0f}"),
        ("opp age (epochs)", g(R + "oppAgeEpochs"), "{:.0f}"),
        ("epoch age at deadline min-max",
         (g(R + "epochAgeAtDeadline::min_value"),
          g(R + "epochAgeAtDeadline::max_value")), None),
        ("age at forced refresh, mean (% DRT)",
         _pct(g(R + "ageAtForceRefresh::mean")), "{:.2f}"),
        ("age at drop, mean (% DRT)",
         _pct(g(R + "ageAtActiveInvalidate::mean")), "{:.2f}"),
        ("age at drop, min-max (% DRT)",
         (_pct(g(R + "ageAtActiveInvalidate::min_value")),
          _pct(g(R + "ageAtActiveInvalidate::max_value"))), None),
        ("age at opp refresh, mean (% DRT)",
         _pct(g(R + "ageAtOppRefresh::mean")), "{:.2f}"),
        ("checker counters (sum)",
         sum(g(R + c, 0) for c in CHECKERS), "{:.0f}"),
    ]
    return out


def _pct(v):
    return None if v is None else 100.0 * v


def fmt(v, f):
    if v is None:
        return "–"
    if isinstance(v, tuple):
        if any(x is None for x in v):
            return "–"
        return "{:.2f} – {:.2f}".format(*v)
    return f.format(v)


def main():
    lines = ["# RTL-alignment smoke runs (strict)", "",
             "CLK = reference (wbfix binary, exact ages, CleanEvict drops); "
             "CLK-SD = + silent clean drops; CLK-RTL = + quantized ages "
             "(1024-cycle epochs, 5-bit stamp, T_guard 258, F 29).", ""]
    for run in RUNS:
        stats = {}
        lines.append(f"## {run}")
        lines.append("")
        st = {c: status(os.path.join(SMOKE, c, run)) for c in CFGS}
        lines.append("Status: " + ", ".join(f"{c} {st[c]}" for c in CFGS))
        lines.append("")
        for c in CFGS:
            stats[c] = load(os.path.join(SMOKE, c, run, "stats.txt"))
        have = [c for c in CFGS if stats[c] is not None]
        if not have:
            continue
        table = {c: rows(stats[c]) for c in have}
        lines.append("| | " + " | ".join(have) + " |")
        lines.append("|---" * (len(have) + 1) + "|")
        for i, (name, _, f) in enumerate(table[have[0]]):
            vals = [fmt(table[c][i][1], f) for c in have]
            lines.append(f"| {name} | " + " | ".join(vals) + " |")
        nz = {c: [k for k in CHECKERS if stats[c].get(R + k, 0) != 0]
              for c in have}
        lines.append("")
        lines.append("Non-zero checker counters: " + ", ".join(
            f"{c} {nz[c] or 'none'}" for c in have))
        lines.append("")
    out = os.path.join(SMOKE, "report.md")
    open(out, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
