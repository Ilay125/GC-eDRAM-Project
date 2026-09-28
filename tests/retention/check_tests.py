#!/usr/bin/env python3
"""Check the directed SRC retention tests run by run_tests.sh."""
import os
import sys

DRT = 10e-6  # seconds
P = "board.cache_hierarchy.l1dcache.retention."


def stats(out, name):
    path = os.path.join(out, name, "stats.txt")
    s = {}
    if os.path.exists(path):
        for line in open(path):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    s[parts[0]] = float(parts[1])
                except ValueError:
                    pass
    return s


def log(out, name):
    path = os.path.join(out, name, "run.log")
    return open(path).read() if os.path.exists(path) else ""


def exit_code(out, name):
    return int(open(os.path.join(out, name, "exit")).read())


def main(out):
    results = []

    def check(case, cond, what):
        results.append((case, bool(cond), what))

    s = stats(out, "no_refresh")
    expect = s.get("simSeconds", 0) / DRT
    lwb = s.get(P + "lazyWritebacksWrite", 0)
    check("no_refresh", exit_code(out, "no_refresh") == 0, "run completes")
    check("no_refresh", 0.8 * expect <= lwb <= 1.3 * expect,
          f"looped line expires every DRT: lazyWritebacksWrite {lwb:.0f} "
          f"vs simSeconds/DRT {expect:.0f}")
    check("no_refresh", s.get(P + "invariantViolations", 0) > 0,
          "violations counted")

    check("no_refresh_strict", "expired at access" in
          log(out, "no_refresh_strict") and
          exit_code(out, "no_refresh_strict") != 0,
          "strict mode panics on the first lost dirty block")

    s = stats(out, "inline_only")
    inl = s.get(P + "refreshInlineWrite", 0)
    lwb3 = s.get(P + "lazyWritebacksWrite", 0)
    check("inline_only", exit_code(out, "inline_only") == 0, "run completes")
    check("inline_only", inl >= 0.8 * expect,
          f"stores keep the line alive: refreshInlineWrite {inl:.0f}")
    check("inline_only", lwb3 < 0.1 * lwb,
          f"write lazy writebacks drop: {lwb3:.0f} (was {lwb:.0f})")

    for case in ("daemon_strict", "both_strict"):
        s = stats(out, case)
        check(case, exit_code(out, case) == 0, "run completes, no panic")
        check(case, s.get(P + "invariantViolations", 1) == 0,
              "no dirty block expires")
        check(case, s.get(P + "totalRefreshes", 0) > 0, "daemon refreshes")
        check(case, s.get(P + "refreshStallCycles", 0) > 0,
              "refreshes stall hits")

    s = stats(out, "both_strict")
    check("both_strict", s.get(P + "refreshInlineWrite", 0) +
          s.get(P + "forceRefresh", 0) > 0, "inline or forced refreshes")

    check("guard_fatal", "retention cannot be guaranteed" in
          log(out, "guard_fatal") and exit_code(out, "guard_fatal") != 0,
          "DRT below T_guard is refused at startup")

    fails = 0
    for case, ok, what in results:
        print(f"{'PASS' if ok else 'FAIL'}  {case:18s} {what}")
        fails += not ok
    print(f"\n{len(results) - fails}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
