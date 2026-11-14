#!/bin/bash
# CLOCK keep rule sweep (branch active_invalidate): SRC 48 KiB at C1 timing
# with active invalidation, cold dirty writeback and the reference bit,
# top_mru 0, at three clear ages:
#   CLK    bit cleared only by a fill or refresh
#   CLK25  also cleared at 25% of DRT
#   CLK50  also cleared at 50% of DRT
#   CLK05, CLK10, CLK15: cleared at 5 / 10 / 15% (finer points, second run,
#   with the write-buffer fix: G=clock_sweep/bin/gem5.fast.wbfix)
# All SimPoints of the 11 benchmarks (lbm excluded), alecto profile, no TSO.
# Compare with alecto_sweep_notso/{A,C0,C1}.
#
#   J=30 RESERVE_GB=10 clock_sweep/run_sweep.sh [bench...]
#
# Resumable and restartable: finished runs and runs in progress are
# skipped. Uses the frozen binary clock_sweep/bin/gem5.fast and config
# copies frozen into clock_sweep/configs on the first launch.
main() {
  cd ~/forgetting
  ROOT=$PWD
  OUT=$ROOT/clock_sweep
  G=${G:-$OUT/bin/gem5.fast}
  CFGDIR=$OUT/configs
  CKPT=$ROOT/spec_checkpoints_sp
  J=${J:-30}
  RESERVE_GB=${RESERVE_GB:-10}
  RUN_GB=4.5
  CONFIGS=${CONFIGS:-CLK CLK25 CLK50}
  BENCHES=${@:-femflow_r cactus_r roms_r zstd_r sqlite_r flightdm_r palm_r sealcrypto_r cpython_r nest_r fotonik3d_r}
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C

  COMMON="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=2 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched"
  declare -A FLAGS=(
    [CLK]=""
    [CLK25]="--touched_clear_age=0.25"
    [CLK50]="--touched_clear_age=0.5"
    [CLK05]="--touched_clear_age=0.05"
    [CLK10]="--touched_clear_age=0.10"
    [CLK15]="--touched_clear_age=0.15"
  )

  [ -x $G ] || { echo "missing $G"; exit 1; }
  if [ ! -d $CFGDIR ]; then
    mkdir -p $CFGDIR
    cp -p $ROOT/configs/forgetting_cache/{restore_measure.py,ForgettingL1DCache.py,cpu_profiles.py} $CFGDIR/
    echo "$(date +%T) froze configs into $CFGDIR"
  fi
  CFG=$CFGDIR/restore_measure.py

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
      for c in $CONFIGS; do
        d=$OUT/$c/runs/$b/sp_$i
        if done_ok $d || in_progress $d; then
          skipped=$((skipped+1)); continue
        fi
        while [ "$(running)" -ge "$J" ] || ! mem_ok; do sleep 10; done
        mkdir -p $d
        $G -d $d $CFG --bench_type=$b --sample_idx=$i \
          --checkpoint_dir=$CKPT/$b $COMMON ${FLAGS[$c]} > $d/run.log 2>&1 &
        total=$((total+1))
        echo "$(date +%T) launch $c $b sp_$i"
      done
    done
  done
  echo "launched $total runs (skipped $skipped), J=$J RESERVE_GB=$RESERVE_GB G=$G"
  while [ "$(running)" -gt 0 ]; do sleep 30; done
  echo "$(date +%T) clock sweep done: $(ls $OUT/*/runs/*/sp_*/stats.txt 2>/dev/null | wc -l) stats files"
}
main "$@"
