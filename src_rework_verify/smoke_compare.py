#!/usr/bin/env python3
"""Compare SRC smoke runs (sp_0) with the SRAM 32/48 KiB baselines.

usage: smoke_compare.py <smoke_dir> [<smoke_dir> ...]
Second stats dump only. MPKI is demand-based (as in sram_mpki_sweep).
"""
import os
import sys

ROOT = os.path.expanduser("~/forgetting")
SRAM = os.path.join(ROOT, "sram_mpki_sweep/runs")
L1 = "board.cache_hierarchy.l1dcache."
R = L1 + "retention."
KEYS = {
    "insts": "simInsts",
    "ipc": "board.processor.cores.core.ipc",
    "miss": L1 + "demandMisses::total",
    "acc": L1 + "demandAccesses::total",
    "l2acc": "board.cache_hierarchy.l2cache.demandAccesses::total",
    "force": R + "forceRefresh",
    "opp": R + "oppRefresh",
    "inl": R + "refreshInlineWrite",
    "rmiss": R + "retentionMisses",
    "lazy": R + "lazyWritebacks",
    "viol": R + "invariantViolations",
    "inflight": R + "expiredInflightHits",
    "revived": R + "daemonRevivedDirty",
    "dirtyEvict": R + "expiredDirtyEvictions",
    "stall": R + "refreshStallCycles",
    "fage": R + "ageAtForceRefresh::mean",
}


def load(path):
    """Second dump of stats.txt as {name: float}, or None if incomplete."""
    try:
        text = open(path).read()
    except OSError:
        return None
    dumps = text.split("Begin Simulation Statistics")
    if len(dumps) < 3 or "End Simulation" not in dumps[2]:
        return None
    out = {}
    for line in dumps[2].splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                out[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return {k: out.get(v, 0.0) for k, v in KEYS.items()}


def mpki(s):
    return s["miss"] / s["insts"] * 1000


def main():
    for d in sys.argv[1:]:
        print(f"\n== {d}")
        print(f"{'bench':12} {'IPC32':>6} {'IPC48':>6} {'IPCsrc':>6} "
              f"{'vs32':>7} {'vs48':>7} {'MPKI32':>7} {'MPKI48':>7} "
              f"{'MPKIsrc':>7} {'L2APKI':>7} {'force':>8} {'fAge':>5} "
              f"{'inline':>7} {'rMiss':>7} {'lazy':>5} {'viol':>4} "
              f"{'reviv':>5} {'dEvic':>5} {'stallCyc':>9}")
        for b in sorted(os.listdir(d)):
            src = load(os.path.join(d, b, "stats.txt"))
            if src is None:
                if os.path.isdir(os.path.join(d, b)):
                    print(f"{b:12} (not finished)")
                continue
            base = {k: load(os.path.join(SRAM, b, "sp_0", f"l1d_{k}k",
                                         "stats.txt")) for k in (32, 48)}
            s32, s48 = base[32], base[48]
            print(f"{b:12} {s32['ipc']:6.3f} {s48['ipc']:6.3f} "
                  f"{src['ipc']:6.3f} "
                  f"{100 * (src['ipc'] / s32['ipc'] - 1):+6.1f}% "
                  f"{100 * (src['ipc'] / s48['ipc'] - 1):+6.1f}% "
                  f"{mpki(s32):7.2f} {mpki(s48):7.2f} {mpki(src):7.2f} "
                  f"{src['l2acc'] / src['insts'] * 1000:7.2f} "
                  f"{src['force']:8.0f} {src['fage']:5.2f} "
                  f"{src['inl']:7.0f} {src['rmiss']:7.0f} "
                  f"{src['lazy']:5.0f} {src['viol']:4.0f} "
                  f"{src['revived']:5.0f} {src['dirtyEvict']:5.0f} "
                  f"{src['stall']:9.0f}")


if __name__ == "__main__":
    main()
