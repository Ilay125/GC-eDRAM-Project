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
                 "cold_touched", "clock_store", "clock_fill",
                 "clock_half_store"):
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

    s = stats(out, "clock_store")
    rd = s.get(P + "refreshDirty", 0)
    drts = s.get("simSeconds", 0) / DRT
    check("clock_store", rd >= 0.8 * drts,
          f"looped line kept by its reference bit: {rd:.0f} dirty "
          f"refreshes >= 0.8 x {drts:.0f} DRTs")
    s = stats(out, "clock_half_store")
    rd = s.get(P + "refreshDirty", 0)
    drts = s.get("simSeconds", 0) / DRT
    clr = s.get(P + "refBitClears", 0)
    check("clock_half_store", rd >= 0.8 * drts and clr > 0,
          f"bit cleared at 50% ({clr:.0f} clears), looped line still "
          f"kept: {rd:.0f} dirty refreshes >= 0.8 x {drts:.0f} DRTs")
    s = stats(out, "clock_fill")
    wb = s.get(P + "coldDirtyWritebacks", 0)
    check("clock_fill", wb >= 600, f"untouched dirty lines written back: "
          f"{wb:.0f} >= 600")

    # RTL alignment. Every case is strict: no panic, no checker counter.
    CE = "board.cache_hierarchy.l2bus.transDist::CleanEvict"
    for case in ("clean_drop", "silent_drop", "silent_wb2", "quant_store",
                 "quant_fill", "quant_silent", "quant_f28"):
        s = stats(out, case)
        check(case, exit_code(out, case) == 0, "run completes, no panic")
        for k in ("invariantViolations", "retentionMisses",
                  "activeInvalidateExpired", "activeInvalidateInflight",
                  "visitIntervalOverruns", "quantExpiredAtVisit",
                  "epochWrapRisk"):
            check(case, s.get(P + k, 1) == 0, f"{k} = 0")

    # Clean drops: one CleanEvict each, or none (silent); a silent drop
    # never takes a write-buffer slot
    s0, s1 = stats(out, "clean_drop"), stats(out, "silent_drop")
    inv0 = s0.get(P + "activeInvalidations", 0)
    check("clean_drop", inv0 >= 600 and s0.get(CE, 0) >= 0.9 * inv0,
          f"{inv0:.0f} clean drops, {s0.get(CE, 0):.0f} CleanEvicts")
    check("clean_drop", s0.get(P + "silentCleanDrops", 1) == 0,
          "no silent drops without the flag")
    sil = s1.get(P + "silentCleanDrops", 0)
    check("silent_drop", sil >= 600 and
          sil == s1.get(P + "activeInvalidations", -1),
          f"every clean drop is silent: {sil:.0f}")
    # The rest are replacements, which still send one
    left = s0.get(CE, 0) - inv0
    check("silent_drop", abs(s1.get(CE, 1e9) - left) <= 0.05 * inv0,
          f"CleanEvicts {s1.get(CE, 0):.0f} = {s0.get(CE, 0):.0f} - "
          f"{inv0:.0f} drops")
    s = stats(out, "silent_wb2")
    sil = s.get(P + "silentCleanDrops", 0)
    kept = s.get(P + "activeWbFullKept", 0)
    check("silent_wb2", sil >= 300 and
          sil == s.get(P + "activeInvalidations", -1),
          f"clean drops all silent with a 2-entry buffer: {sil:.0f}")
    check("silent_wb2", kept >= 50 and
          s.get(P + "coldDirtyWritebacks", 0) >= 300,
          f"dirty drops written back ({s.get(P + 'coldDirtyWritebacks', 0):.0f})"
          f", {kept:.0f} kept by a full buffer")

    # Quantized ages: F = 29 (28 when given), opp age 23, every deadline
    # action at exactly epoch age F, so at a true age of (F - 1) x 1024 to
    # F x 1024 + 256 cycles
    for case, f in (("quant_store", 29), ("quant_fill", 29),
                    ("quant_silent", 29), ("quant_f28", 28)):
        s = stats(out, case)
        q = P + "epochAgeAtDeadline::"
        check(case, s.get(P + "deadlineEpochs", 0) == f and
              s.get(P + "oppAgeEpochs", 0) == 23 and
              s.get(P + "epochCycles", 0) == 1024,
              f"F {s.get(P + 'deadlineEpochs', 0):.0f}, opp "
              f"{s.get(P + 'oppAgeEpochs', 0):.0f}, epoch "
              f"{s.get(P + 'epochCycles', 0):.0f}")
        check(case, s.get(q + "samples", 0) > 0 and
              s.get(q + "min_value", 0) == f and
              s.get(q + "max_value", 0) == f,
              f"{s.get(q + 'samples', 0):.0f} deadline actions, all at "
              f"epoch age {f}")
        lo, hi = (f - 1) * 1024 / 30030, (f * 1024 + 256) / 30030
        for d in ("ageAtActiveInvalidate", "ageAtForceRefresh"):
            if s.get(P + d + "::samples", 0) > 0:
                mn = s.get(P + d + "::min_value", 0)
                mx = s.get(P + d + "::max_value", 1)
                check(case, lo <= mn and mx <= hi,
                      f"{d} in [{lo:.3f}, {hi:.3f}]: {mn:.3f}-{mx:.3f}")
    s = stats(out, "quant_store")
    rd = s.get(P + "refreshDirty", 0)
    drts = s.get("simSeconds", 0) / DRT
    check("quant_store", rd >= 0.8 * drts,
          f"looped line kept: {rd:.0f} dirty refreshes >= 0.8 x "
          f"{drts:.0f} DRTs")
    for case in ("quant_fill", "quant_f28"):
        wb = stats(out, case).get(P + "coldDirtyWritebacks", 0)
        check(case, wb >= 600, f"untouched dirty lines written back: {wb:.0f}")
    s = stats(out, "quant_silent")
    check("quant_silent", s.get(P + "silentCleanDrops", 0) >= 600,
          f"silent drops: {s.get(P + 'silentCleanDrops', 0):.0f}")

    check("quant_f30_fatal", "cannot guarantee retention" in
          log(out, "quant_f30_fatal") and
          exit_code(out, "quant_f30_fatal") != 0,
          "F = 30 (30 x 1024 + 256 + 24 >= 30030) is refused")
    check("quant_bits_fatal", "wraps before the deadline" in
          log(out, "quant_bits_fatal") and
          exit_code(out, "quant_bits_fatal") != 0,
          "a 4-bit stamp is refused")

    fails = 0
    for case, ok, what in results:
        print(f"{'PASS' if ok else 'FAIL'}  {case:18s} {what}")
        fails += not ok
    print(f"\n{len(results) - fails}/{len(results)} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
