#!/bin/bash
# Rerun after the write-buffer fix (activeWbFullKept): all femflow SimPoints
# in the three configs, plus sp_0 of every other benchmark in CLK50, into
# clock_sweep/wbfix/<cfg>/runs/. Compare with the first runs.
main() {
  cd ~/forgetting
  OUT=$PWD/clock_sweep/wbfix
  G=$PWD/clock_sweep/bin/gem5.fast.wbfix
  CFG=$PWD/clock_sweep/configs/restore_measure.py
  CKPT=$PWD/spec_checkpoints_sp
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
  COMMON="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=2 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched"
  declare -A FLAGS=([CLK]="" [CLK25]="--touched_clear_age=0.25"
                    [CLK50]="--touched_clear_age=0.5")
  jobs_list=()
  n=$(ls -d $CKPT/femflow_r/sp_* | wc -l)
  for ((i=0; i<n; i++)); do
    for c in CLK CLK25 CLK50; do jobs_list+=("$c femflow_r $i"); done
  done
  for b in palm_r flightdm_r cactus_r fotonik3d_r cpython_r sqlite_r roms_r \
           nest_r zstd_r sealcrypto_r; do
    jobs_list+=("CLK50 $b 0")
  done
  for j in "${jobs_list[@]}"; do
    read c b i <<< "$j"
    # At most 30 at once, and keep 10 GiB + one run free (4.5 GiB each)
    while [ "$(pgrep -u "$USER" -fc "^$G -d $OUT/")" -ge 30 ] ||
          ! awk '/^MemAvailable:/{exit !($2 >= 14.5 * 1048576)}' /proc/meminfo
    do sleep 10; done
    d=$OUT/$c/runs/$b/sp_$i; mkdir -p $d
    $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
      $COMMON ${FLAGS[$c]} > $d/run.log 2>&1 &
  done
  wait
  echo "$(date +%T) wbfix rerun done: $(ls $OUT/*/runs/*/sp_*/stats.txt | wc -l) stats files"
}
main "$@"
