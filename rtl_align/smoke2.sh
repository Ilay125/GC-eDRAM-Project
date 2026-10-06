#!/bin/bash
# RTL2 smoke runs, strict (any lost dirty line, revisit overrun, stamp wrap
# or expired valid line panics): the 2-bank line-scanner controller on the
# five SimPoints of smoke.sh. Output rtl_align/smoke2/RTL2/<bench>_sp<i>/.
#   rtl_align/smoke2.sh
main() {
  cd ~/forgetting
  ROOT=$PWD
  OUT=$ROOT/rtl_align/smoke2
  G=$ROOT/bin/gem5.fast.rtl_align2
  CFG=$ROOT/rtl_align/configs2/restore_measure.py
  CKPT=$ROOT/spec_checkpoints_sp
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
  RTL2="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=2 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=1 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched
    --quantized_age --age_epoch_log2=10 --age_bits=5
    --refresh_scan=line --refresh_line_budget_cycles=4 --drt_strict"
  for p in "palm_r 0" "flightdm_r 0" "roms_r 3" "zstd_r 0" "cpython_r 4"; do
    read b i <<< "$p"
    d=$OUT/RTL2/${b}_sp$i
    mkdir -p $d
    $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
      $RTL2 > $d/run.log 2>&1 &
    echo "$(date +%T) launch RTL2 $b sp_$i"
  done
  wait
  echo "$(date +%T) smoke2 done: $(ls $OUT/*/*/stats.txt | wc -l) stats files"
}
main "$@"
