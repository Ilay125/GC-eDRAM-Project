#!/usr/bin/env python3
"""Side-by-side before/after evidence for the DRT=0 equivalence runs.

  show_equivalence.py [final_drt0 dir]

For every <bench>_<N>k run in the directory, prints key stats from the
pre-rework measurement (sram_mpki_sweep/runs/<bench>/sp_0/l1d_<N>k, made by
bin/gem5.fast.pre-rework) next to the new binary's, then the count of ALL
stats (second dump, host* ignored) that differ, via compare_stats.load().
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REF = os.path.join(ROOT, "sram_mpki_sweep", "runs")

_spec = importlib.util.spec_from_file_location(
    "compare_stats", os.path.join(HERE, "compare_stats.py"))
cmp_stats = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmp_stats)

H = "board.cache_hierarchy."
KEY = [
    ("simInsts", "simInsts"),
    ("simTicks", "simTicks"),
    ("cycles", "board.processor.cores.core.numCycles"),
    ("IPC", "board.processor.cores.core.ipc"),
    ("L1D acc", H + "l1dcache.demandAccesses::total"),
    ("L1D miss", H + "l1dcache.demandMisses::total"),
    ("L1D wb", H + "l1dcache.writebacks::total"),
    ("L2 acc", H + "l2cache.demandAccesses::total"),
    ("L2 miss", H + "l2cache.demandMisses::total"),
]


def main(d):
    runs = sorted(r for r in os.listdir(d)
                  if os.path.isfile(os.path.join(d, r, "stats.txt")))
    n_same = 0
    for r in runs:
        bench, size = r.rsplit("_", 1)
        old_p = os.path.join(REF, bench, "sp_0", f"l1d_{size}", "stats.txt")
        new_p = os.path.join(d, r, "stats.txt")
        old, new = cmp_stats.load(old_p), cmp_stats.load(new_p)
        common = set(old) & set(new)
        diff = sorted(k for k in common if old[k] != new[k])
        same = not diff and len(common) > 0
        n_same += same
        print(f"\n=== {bench} sp_0, L1D {size} (DRT=0)")
        print(f"  before: {os.path.relpath(old_p, ROOT)}")
        print(f"  after : {os.path.relpath(new_p, ROOT)}")
        print(f"  {'stat':<10}{'before (pre-rework)':>22}{'after (new)':>22}")
        for label, k in KEY:
            a, b = old.get(k, "-"), new.get(k, "-")
            mark = "" if a == b else "   <-- DIFF"
            print(f"  {label:<10}{a:>22}{b:>22}{mark}")
        only_old = sorted(set(old) - set(new))
        print(f"  ALL stats: {len(common)} compared, {len(diff)} differ"
              f"  -> {'IDENTICAL' if same else 'DIFFERENT'}")
        if only_old:
            print(f"  stats removed by the rework (before only): "
                  f"{', '.join(k.split('.')[-1] for k in only_old[:6])}"
                  f"{' ...' if len(only_old) > 6 else ''} ({len(only_old)})")
        for k in diff[:10]:
            print(f"    DIFF {k}: {old[k]} -> {new[k]}")
    print(f"\n{n_same}/{len(runs)} runs identical to the pre-rework binary")
    return 0 if n_same == len(runs) and runs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(HERE, "final_drt0")))
