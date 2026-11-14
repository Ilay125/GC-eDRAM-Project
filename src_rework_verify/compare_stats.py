#!/usr/bin/env python3
"""Compare the measurement dump (2nd) of two gem5 stats.txt files.

  compare_stats.py OLD/stats.txt NEW/stats.txt

Ignores host* stats. Maps SRC stats that moved into the retention group
(l1dcache.X -> l1dcache.retention.X) and lists stats that exist on only
one side separately, so they are visible but not counted as mismatches.
Exit code 1 if any common stat differs.
"""
import re
import sys

MOVED = ["retentionMisses", "dirtyRetentionMisses", "oppRefresh",
         "forceRefresh", "totalRefreshes", "expiredHitPot",
         "refreshedBlockUtility"]
IGNORE = re.compile(r"^(hostSeconds|hostTickRate|hostMemory|hostInstRate|"
                    r"hostOpRate)")


def load(path):
    stats, dump = {}, 0
    for line in open(path):
        if "Begin Simulation Statistics" in line:
            dump += 1
            continue
        if dump != 2 or not line.strip() or line.startswith("-"):
            continue
        parts = line.split()
        if len(parts) < 2 or IGNORE.match(parts[0]):
            continue
        name = parts[0]
        for m in MOVED:
            name = re.sub(rf"\.retention\.{m}$", f".{m}", name)
        stats[name] = " ".join(parts[1:]).split("#")[0].strip()
    return stats


def main():
    old, new = load(sys.argv[1]), load(sys.argv[2])
    only_old = sorted(set(old) - set(new))
    only_new = sorted(set(new) - set(old))
    diff = [(k, old[k], new[k]) for k in sorted(set(old) & set(new))
            if old[k] != new[k]]
    print(f"common stats: {len(set(old) & set(new))}, "
          f"differ: {len(diff)}, only old: {len(only_old)}, "
          f"only new: {len(only_new)}")
    for k, a, b in diff[:40]:
        print(f"  DIFF {k}: {a} -> {b}")
    for k in only_old[:40]:
        print(f"  only old: {k} = {old[k]}")
    for k in only_new[:40]:
        print(f"  only new: {k} = {new[k]}")
    return 1 if diff else 0


if __name__ == "__main__":
    sys.exit(main())
