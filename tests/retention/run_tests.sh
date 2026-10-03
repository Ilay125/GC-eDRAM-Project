#!/bin/bash
# Directed SRC retention tests. Usage: run_tests.sh [gem5 binary]
# Runs every case in parallel, then checks each case's stats.
cd "$(dirname "$0")/../.."
G=${1:-gem5/build/X86/gem5.fast}
T=tests/retention
OUT=$T/out
DRT=10000000   # 10 us; T_guard is ~2.3 us for 48 KiB 12-way at 3 GHz
rm -rf $OUT && mkdir -p $OUT
[ -x $T/store_loop ] || gcc -O1 -static -o $T/store_loop $T/store_loop.c || exit 1
[ -x $T/dirty_fill ] || gcc -O1 -static -o $T/dirty_fill $T/dirty_fill.c || exit 1

run() { # name args...
  local n=$1; shift
  mkdir -p $OUT/$n
  $G -d $OUT/$n $T/run_test.py "$@" > $OUT/$n/run.log 2>&1
  echo $? > $OUT/$n/exit
}

# 1. no daemon, no inline: the looped line expires every DRT (lazy WB)
run no_refresh      --drt_ticks=$DRT --no_inline_refresh &
# 2. same, strict: must panic on the first lost dirty block
run no_refresh_strict --drt_ticks=$DRT --no_inline_refresh --drt_strict &
# 3. inline only: the looped line is kept alive by its own stores
run inline_only     --drt_ticks=$DRT &
# 4. daemon only (dirty refresh), strict: no dirty block may expire
run daemon_strict   --drt_ticks=$DRT --refresh_dirty --no_inline_refresh --drt_strict &
# 5. daemon + inline, strict
run both_strict     --drt_ticks=$DRT --refresh_dirty --drt_strict &
# 6. DRT below T_guard: startup must refuse
run guard_fatal     --drt_ticks=2000000 --refresh_dirty --iters=1000 &
# 7. 8 banks, daemon only, strict: T_guard 1440 cycles, no dirty loss
run banks8_strict   --drt_ticks=$DRT --refresh_dirty --no_inline_refresh --drt_strict --refresh_banks=8 &
# 8. 8 banks, daemon + inline, strict
run banks8_both_strict --drt_ticks=$DRT --refresh_dirty --drt_strict --refresh_banks=8 &
# 9. 8 banks make the 2 us DRT of case 6 feasible
run banks8_guard_ok --drt_ticks=2000000 --refresh_dirty --refresh_banks=8 --iters=1000 &
# 10. more banks than sets: refused
run banks_fatal     --drt_ticks=$DRT --refresh_dirty --refresh_banks=65 --iters=1000 &

# Active invalidation, C1 timing (8 banks, line 2): T_sweep 256, T_guard 514
AI="--refresh_dirty --top_mru=4 --refresh_banks=8 --refresh_line_cycles=2
    --no_inline_refresh --active_invalidate --guard_sweeps=2
    --retention_margin=0 --drt_strict"
# 11. store loop at 10 us: nothing expires, nothing is lost
run ai_strict       --drt_ticks=$DRT $AI &
# 12. every L1D line dirty, then spin, at 10 us
run ai_fill         --drt_ticks=$DRT $AI --prog=dirty_fill --iters=1000000 &
# 13. worst case: DRT 520 cycles, just above T_guard, so every dirty line
#     is refreshed at every visit (12 per set): each sweep is the bound
run ai_worst        --drt_ticks=173160 $AI --prog=dirty_fill --iters=1000000 \
                    --refresh_opp_age=1.0 &
# 14. active invalidation without the dirty refresh: refused
run ai_needs_dirty  --drt_ticks=$DRT --top_mru=4 --no_inline_refresh \
                    --active_invalidate --iters=1000 &
# 15. active invalidation with inline refresh: refused
run ai_needs_noinl  --drt_ticks=$DRT --refresh_dirty --active_invalidate \
                    --iters=1000 &
# 16-17. all-dirty fill at 10 us, cold dirty lines written back at T_guard
run cold_mru        --drt_ticks=$DRT $AI --prog=dirty_fill --iters=1000000 \
                    --cold_dirty=mru &
run cold_touched    --drt_ticks=$DRT $AI --prog=dirty_fill --iters=1000000 \
                    --cold_dirty=touched &
wait

./venv/bin/python $T/check_tests.py $OUT
