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

    for case in ("banks8_strict", "banks8_both_strict"):
        s = stats(out, case)
        check(case, exit_code(out, case) == 0, "run completes, no panic")
        check(case, s.get(P + "invariantViolations", 1) == 0,
              "no dirty block expires")
        tg = s.get(P + "tGuardCycles", 0)
        check(case, abs(tg - 1440) < 1,
              f"T_guard = 8 x (8 + 12 x 8) + 8 + 2% DRT = 1440: {tg:.1f}")
        # Upper edge of the highest non-empty sweep-time bucket
        mx = max([int(k.rsplit("-", 1)[1]) for k, v in s.items()
                  if k.startswith(P + "daemonSweepCycles::") and
                  "-" in k.rsplit("::", 1)[1] and v > 0] or [1e9])
        ts = s.get(P + "tSweepCycles", 0)
        check(case, mx <= ts,
              f"measured sweep within the bound: max {mx:.0f} <= {ts:.0f}")
        used = sum(1 for b in range(8)
                   if s.get(P + f"bankRefreshes::{b}", 0) > 0)
        check(case, used >= 1, f"refreshes land in banks ({used} of 8)")

    check("banks8_guard_ok", exit_code(out, "banks8_guard_ok") == 0 and
          "8 bank(s)" in log(out, "banks8_guard_ok"),
          "2 us DRT (refused with 1 bank) accepted with 8 banks")
    check("banks_fatal", "refresh_banks (65)" in log(out, "banks_fatal") and
          exit_code(out, "banks_fatal") != 0,
          "more banks than sets is refused")

    # Active invalidation (C1 timing): T_sweep = 8 x (8 x 1 + 12 x 2) = 256,
    # T_guard = 2 x 256 + 2 = 514 cycles
    for case in ("ai_strict", "ai_fill", "ai_worst", "cold_mru",
                 "cold_touched"):
        s = stats(out, case)
        check(case, exit_code(out, case) == 0, "run completes, no panic")
        for k in ("invariantViolations", "retentionMisses",
                  "expiredCleanEvictions", "expiredInflightHits",
                  "activeInvalidateExpired", "activeInvalidateInflight",
                  "visitIntervalOverruns", "refreshInlineWrite"):
            check(case, s.get(P + k, 1) == 0, f"{k} = 0")
        check(case, s.get(P + "activeInvalidations", 0) > 0,
              f"daemon invalidates: {s.get(P + 'activeInvalidations', 0):.0f}")
        tg = s.get(P + "tGuardCycles", 0)
        check(case, abs(tg - 514) < 1, f"T_guard = 2 x 256 + 2 = 514: {tg:.1f}")
        mx = s.get(P + "maxSetVisitCycles", 1e9)
        ts = s.get(P + "tSweepCycles", 0)
        check(case, mx <= ts, f"set revisits within T_sweep: max {mx:.0f} "
              f"<= {ts:.0f}")

    # Worst case: every line refreshed at every visit. The scanner's 8 scans
    # of a round overlap the banks' refreshes, so a round takes
    # max(8 x 1, 12 x 2) = 24 cycles: the reached maximum is 8 x 24 = 192
    s = stats(out, "ai_worst")
    mx = s.get(P + "maxSetVisitCycles", 0)
    check("ai_worst", abs(mx - 192) < 1,
          f"worst case reached: max revisit {mx:.0f} = 8 x max(8, 24) = 192")
    sweeps = s.get("simTicks", 0) / 333 / 192
    fr = s.get(P + "forceRefresh", 0)
    check("ai_worst", fr >= 0.9 * 768 * sweeps,
          f"every line refreshed each sweep: {fr:.0f} >= 0.9 x 768 x "
          f"{sweeps:.0f} sweeps")

    check("ai_needs_dirty", "needs refresh_dirty_daemon" in
          log(out, "ai_needs_dirty") and exit_code(out, "ai_needs_dirty") != 0,
          "active invalidation without the dirty refresh is refused")
    check("ai_needs_noinl", "needs inline refresh off" in
          log(out, "ai_needs_noinl") and exit_code(out, "ai_needs_noinl") != 0,
          "active invalidation with inline refresh is refused")

    # The fill dirties all 768 lines, then the program only spins: the 8
    # non-MRU dirty lines per set (mru), or every untouched one (touched),
    # are written back once at T_guard instead of refreshed every DRT
    for case, low in (("cold_mru", 400), ("cold_touched", 600)):
        s = stats(out, case)
        wb = s.get(P + "coldDirtyWritebacks", 0)
        check(case, wb >= low, f"cold dirty lines written back: {wb:.0f} "
              f">= {low}")
    s = stats(out, "cold_touched")
    check("cold_touched", s.get(P + "refreshDirty", 1e9) <
          stats(out, "ai_fill").get(P + "refreshDirty", 0) / 10,
          "dirty refreshes drop vs ai_fill")

    fails = 0
    for case, ok, what in results:
        print(f"{'PASS' if ok else 'FAIL'}  {case:18s} {what}")
        fails += not ok
    print(f"\n{len(results) - fails}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
