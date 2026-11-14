#!/bin/bash
# Verification of active invalidation (branch active_invalidate).
#   1. DRT = 0 on the default profile: compare with sram_mpki_sweep (l1d_32k)
#   2. C1 with the feature off: compare with spec_add/C1 (same source base)
#   3. C1-AI smoke, strict, next to C1 (feature off) on the same binary
# Usage: src_rework_verify/ai_verify.sh   (output in src_rework_verify/ai/)
cd ~/forgetting
OUT=$PWD/src_rework_verify/ai
G=${NEW:-$PWD/bin/gem5.fast.active_invalidate}
CFG=$PWD/configs/forgetting_cache/restore_measure.py
CKPT=$PWD/spec_checkpoints_sp
export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C

DEF="--freq=3GHz --l2_size=1MiB --l1d_size=32KiB --l1d_assoc=8"
ALECTO="--cpu_profile=alecto --freq=3GHz"
C1="--l1d_size=48KiB --l1d_assoc=12 --l1d_hit_cycles=5 --drt_ticks=10000000
    --top_mru=4 --refresh_dirty --refresh_banks=8 --refresh_line_cycles=2
    --refresh_opp_age=0.8"
C1_MARGIN="--retention_margin=0.0414"
AI="--active_invalidate --guard_sweeps=2 --retention_margin=0
    --no_inline_refresh --drt_strict"

run() { # dir bench sp args...
  local d=$OUT/$1 b=$2 i=$3; shift 3
  mkdir -p $d
  $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
    "$@" > $d/run.log 2>&1 &
}

run drt0/palm_r_sp1    palm_r 1   $DEF
run drt0/sqlite_r_sp7  sqlite_r 7 $DEF
run drt0/lbm_r_sp4     lbm_r 4    $DEF
run c1/palm_r_sp1      palm_r 1     $ALECTO $C1 $C1_MARGIN
run c1/flightdm_r_sp0  flightdm_r 0 $ALECTO $C1 $C1_MARGIN
run c1/roms_r_sp0      roms_r 0     $ALECTO $C1 $C1_MARGIN
run c1ai/palm_r_sp1     palm_r 1     $ALECTO $C1 $AI
run c1ai/flightdm_r_sp0 flightdm_r 0 $ALECTO $C1 $AI
run c1ai/roms_r_sp0     roms_r 0     $ALECTO $C1 $AI
wait
echo "done: $(ls $OUT/*/*/stats.txt | wc -l) stats files"
