#!/bin/bash
# RTL-alignment smoke runs, strict: CLK (reference, wbfix binary), CLK-SD
# (+ silent clean drops) and CLK-RTL (+ quantized ages, T_guard 258 -> F 29)
# on five SimPoints. Output rtl_align/smoke/<cfg>/<bench>_sp<i>/.
#   J=15 RESERVE_GB=10 rtl_align/smoke.sh
main() {
  cd ~/forgetting
  ROOT=$PWD
  OUT=$ROOT/rtl_align/smoke
  NEW=$ROOT/bin/gem5.fast.rtl_align
  OLD=$ROOT/clock_sweep/bin/gem5.fast.wbfix
  CFG=$ROOT/rtl_align/configs/restore_measure.py
  CKPT=$ROOT/spec_checkpoints_sp
  J=${J:-15}
  RESERVE_GB=${RESERVE_GB:-10}
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
  CLK="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=2 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched --drt_strict"
  declare -A FLAGS=(
    [CLK]=""
    [CLK-SD]="--silent_clean_drop"
    [CLK-RTL]="--silent_clean_drop --quantized_age --age_epoch_log2=10
               --age_bits=5 --guard_sweeps=1"
  )
  mem_ok() { awk -v r=$RESERVE_GB '/^MemAvailable:/{exit !($2 >= (r + 4.5) * 1048576)}' /proc/meminfo; }
  running() { pgrep -u "$USER" -fc "^$ROOT/[a-z_/]*gem5.fast[.a-z_]* -d $OUT/"; }
  for p in "palm_r 0" "flightdm_r 0" "roms_r 3" "zstd_r 0" "cpython_r 4"; do
    read b i <<< "$p"
    for c in CLK CLK-SD CLK-RTL; do
      d=$OUT/$c/${b}_sp$i
      [ -f $d/stats.txt ] && grep -q "measurement complete" $d/run.log 2>/dev/null && continue
      G=$NEW; [ $c = CLK ] && G=$OLD
      while [ "$(running)" -ge "$J" ] || ! mem_ok; do sleep 10; done
      mkdir -p $d
      $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
        $CLK ${FLAGS[$c]} > $d/run.log 2>&1 &
      echo "$(date +%T) launch $c $b sp_$i"
    done
  done
  wait
  echo "$(date +%T) smoke done: $(ls $OUT/*/*/stats.txt | wc -l) stats files"
}
main "$@"
