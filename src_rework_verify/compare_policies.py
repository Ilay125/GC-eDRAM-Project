#!/usr/bin/env python3
"""Compare the SRC daemon policies on the smoke SimPoints (second dump).

C0 (SRAM 48 KiB) comes from alecto_sweep_notso; C1 and C1-AI from
src_rework_verify/ai; the variants from src_rework_verify/ai/cold/.
Usage: venv/bin/python src_rework_verify/compare_policies.py
"""
import os

ROOT = os.path.expanduser("~/forgetting")
V = f"{ROOT}/src_rework_verify/ai"
BENCH = [("palm_r", 1), ("flightdm_r", 0), ("roms_r", 0)]
CONFIGS = [
    ("C0 SRAM48", lambda b, i: f"{ROOT}/alecto_sweep_notso/C0/runs/{b}/sp_{i}"),
    ("C1", lambda b, i: f"{V}/c1/{b}_sp{i}"),
    ("C1-AI", lambda b, i: f"{V}/c1ai2/{b}_sp{i}"),
    ("mru top4", lambda b, i: f"{V}/cold/mru_top4/{b}_sp{i}"),
    ("mru top2", lambda b, i: f"{V}/cold/mru_top2/{b}_sp{i}"),
    ("touched top4", lambda b, i: f"{V}/cold/touched_top4/{b}_sp{i}"),
    ("clock top1", lambda b, i: f"{V}/cold/clock_top1/{b}_sp{i}"),
    ("clock top0", lambda b, i: f"{V}/cold/clock_top0/{b}_sp{i}"),
    ("clock½ top1", lambda b, i: f"{V}/cold/clock_half_top1/{b}_sp{i}"),
    ("clock½ top0", lambda b, i: f"{V}/cold/clock_half_top0/{b}_sp{i}"),
]
H = "board.cache_hierarchy."
R = H + "l1dcache.retention."


def load(d):
    p = os.path.join(d, "stats.txt")
    if not os.path.exists(p):
        return None
    s, n = {}, 0
    for line in open(p):
        if "Begin Simulation Statistics" in line:
            n += 1
            s = {}
        a = line.split()
        if len(a) >= 2:
            try:
                s[a[0]] = float(a[1])
            except ValueError:
                pass
    return s if n >= 2 else None


def pki(s, k):
    return s.get(k, 0) / s["simInsts"] * 1000


ROWS = [
    ("IPC", lambda s: s["board.processor.cores.core.ipc"], "{:.4f}"),
    ("dIPC vs C1 %", None, "{:+.2f}"),
    ("dIPC vs C0 %", None, "{:+.2f}"),
    ("L1D primary MPKI", lambda s: pki(s, H + "l1dcache.demandMshrMisses::total"), "{:.2f}"),
    ("refreshes PKI", lambda s: pki(s, R + "totalRefreshes"), "{:.2f}"),
    ("  dirty", lambda s: pki(s, R + "refreshDirty"), "{:.2f}"),
    ("  clean", lambda s: pki(s, R + "refreshClean"), "{:.2f}"),
    ("  wasted (dead)", lambda s: pki(s, R + "refreshDeadClean") + pki(s, R + "refreshDeadDirty"), "{:.2f}"),
    ("  needed", lambda s: pki(s, R + "refreshNeededClean") + pki(s, R + "refreshNeededDirty"), "{:.2f}"),
    ("  kept by R bit (clean)", lambda s: pki(s, R + "refreshTouched"), "{:.2f}"),
    ("clean invalidations PKI", lambda s: pki(s, R + "activeInvalidations"), "{:.2f}"),
    ("cold dirty writebacks PKI", lambda s: pki(s, R + "coldDirtyWritebacks"), "{:.2f}"),
    ("early misses PKI (cost)", lambda s: pki(s, R + "activeInvalidateEarlyMisses"), "{:.3f}"),
    ("  of which cold dirty", lambda s: pki(s, R + "coldDirtyEarlyMisses"), "{:.3f}"),
    ("retention misses PKI", lambda s: pki(s, R + "retentionMisses"), "{:.3f}"),
    ("refresh stall cyc/kinst", lambda s: pki(s, R + "refreshStallCycles"), "{:.2f}"),
    ("L1D writebacks PKI", lambda s: pki(s, H + "l1dcache.writebacks::total"), "{:.2f}"),
    ("L2 demand miss PKI", lambda s: pki(s, H + "l2cache.demandMisses::total"), "{:.2f}"),
    ("DRAM reads PKI", lambda s: pki(s, "board.memory.mem_ctrl0.dram.numReads::total")
                                 + pki(s, "board.memory.mem_ctrl1.dram.numReads::total"), "{:.2f}"),
    ("dirty data lost", lambda s: s.get(R + "invariantViolations", 0), "{:.0f}"),
    ("revisit overruns", lambda s: s.get(R + "visitIntervalOverruns", 0), "{:.0f}"),
]

for b, i in BENCH:
    runs = [(n, load(f(b, i))) for n, f in CONFIGS]
    runs = [(n, s) for n, s in runs if s]
    ipc = {n: s["board.processor.cores.core.ipc"] for n, s in runs}
    print(f"\n## {b} sp_{i}\n")
    print("| | " + " | ".join(n for n, _ in runs) + " |")
    print("|---" * (len(runs) + 1) + "|")
    for name, fn, fmt in ROWS:
        cells = []
        for n, s in runs:
            if name == "dIPC vs C1 %":
                v = 100 * (ipc[n] / ipc["C1"] - 1) if "C1" in ipc else float("nan")
            elif name == "dIPC vs C0 %":
                v = 100 * (ipc[n] / ipc["C0 SRAM48"] - 1)
            else:
                v = fn(s)
            cells.append(fmt.format(v))
        print(f"| {name} | " + " | ".join(cells) + " |")
