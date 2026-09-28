#!/bin/bash
# Directed SRC retention tests. Usage: run_tests.sh [gem5 binary]
# Runs every case in parallel, then checks each case's stats.
cd "$(dirname "$0")/../.."
G=${1:-gem5/build/X86/gem5.fast}
T=tests/retention
OUT=$T/out
DRT=10000000   # 10 us; T_guard is ~2.3 us for 48 KiB 12-way at 3 GHz
rm -rf $OUT && mkdir -p $OUT

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
wait

./venv/bin/python $T/check_tests.py $OUT
