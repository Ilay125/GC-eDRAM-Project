#!/bin/bash
# RTL-aligned SRC sweep on every SimPoint of the 11 SPEC
# benchmarks of the alecto sweeps plus gcc_r and omnetpp_r. Non-strict, as in
# every earlier sweep: checker counters are counted, not fatal. Compare with
# alecto_sweep_notso/{A,C0,C1} and spec_add/A.
#   SWEEP_CFG=RTL     (default) CLOCK keep rule + quantized ages (T_guard 258 ->
#               F 29); clean drops send a CleanEvict like every other clean
#               eviction (gem5's exact snoop filter needs it)
#   SWEEP_CFG=RTL-B4  RTL with 4 data-array banks instead of 8 (T_sweep 448,
#               T_guard 450 -> F 28); RTL-B2: 2 banks (T_sweep 832, F 28);
#               RTL-B1: 1 bank (T_sweep 1600, T_guard 1602 -> F 27)
#   SWEEP_CFG=CLK-RTL the same + silent clean drops (first run: 8 of 93 runs
#               panic, "snoop filter exceeded capacity")
#   SWEEP_CFG=RTL-B4, RTL-B2  RTL with 4 / 2 refresh banks instead of 8
#               (T_sweep 448 / 832 cycles, F 28 for both)
#
#   SWEEP_CFG=RTL J=30 RESERVE_GB=10 rtl_align/run_sweep.sh [bench...]
#
# Resumable and restartable: finished runs and runs in progress are skipped.
# Frozen binary bin/gem5.fast.rtl_align, frozen configs rtl_align/configs.
main() {
  cd ~/forgetting
  ROOT=$PWD
  OUT=$ROOT/rtl_align/sweep
  G=$ROOT/bin/gem5.fast.rtl_align
  CFG=$ROOT/rtl_align/configs/restore_measure.py
  CKPT=$ROOT/spec_checkpoints_sp
  J=${J:-30}
  RESERVE_GB=${RESERVE_GB:-10}
  RUN_GB=4.5
  BENCHES=${@:-femflow_r cactus_r roms_r zstd_r sqlite_r flightdm_r palm_r sealcrypto_r cpython_r nest_r fotonik3d_r gcc_r omnetpp_r}
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
  FLAGS="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=1 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched
    --quantized_age --age_epoch_log2=10 --age_bits=5"
  C=${SWEEP_CFG:-RTL}
  case $C in
    RTL) ;;
    RTL-B4) FLAGS="${FLAGS/--refresh_banks=8/--refresh_banks=4}" ;;
    RTL-B2) FLAGS="${FLAGS/--refresh_banks=8/--refresh_banks=2}" ;;
    RTL-B1) FLAGS="${FLAGS/--refresh_banks=8/--refresh_banks=1}" ;;
    CLK-RTL) FLAGS="$FLAGS --silent_clean_drop" ;;
    *) echo "unknown SWEEP_CFG=$C"; exit 1 ;;
  esac

  [ -x $G ] || { echo "missing $G"; exit 1; }
  running() { pgrep -u "$USER" -fc "^$G -d $OUT/"; }
  in_progress() { pgrep -u "$USER" -f "^$G -d $1 " > /dev/null; }
  mem_ok() { awk -v r=$RESERVE_GB -v g=$RUN_GB \
    '/^MemAvailable:/{exit !($2 >= (r + g) * 1048576)}' /proc/meminfo; }
  done_ok() { [ -f "$1/stats.txt" ] &&
    [ "$(grep -c 'Begin Simulation Statistics' $1/stats.txt)" -ge 2 ]; }

  total=0; skipped=0
  for b in $BENCHES; do
    n=$(ls -d $CKPT/$b/sp_* 2>/dev/null | wc -l)
    [ "$n" -eq 0 ] && { echo "WARN: no checkpoints for $b"; continue; }
    for ((i=0; i<n; i++)); do
      d=$OUT/$C/runs/$b/sp_$i
      if done_ok $d || in_progress $d; then
        skipped=$((skipped+1)); continue
      fi
      while [ "$(running)" -ge "$J" ] || ! mem_ok; do sleep 10; done
      mkdir -p $d
      $G -d $d $CFG --bench_type=$b --sample_idx=$i \
        --checkpoint_dir=$CKPT/$b $FLAGS > $d/run.log 2>&1 &
      total=$((total+1))
      echo "$(date +%T) launch $b sp_$i"
    done
  done
  echo "launched $total $C runs (skipped $skipped), J=$J RESERVE_GB=$RESERVE_GB"
  while [ "$(running)" -gt 0 ]; do sleep 30; done
  echo "$(date +%T) rtl sweep done: $(ls $OUT/*/runs/*/sp_*/stats.txt 2>/dev/null | wc -l) stats files"
}
main "$@"
