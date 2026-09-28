#!/bin/bash
# SRC L1D DRT sweep: 48 KiB 12-way (64 sets) at each DRT, every SimPoint.
# Non-forgetting baselines (SRAM 32 KiB 8-way, 48 KiB 12-way, same setup)
# are read from sram_mpki_sweep/runs; they are not rerun here.
# usage: [J=25] [DRTS_US="10 5 20"] [OUT=dir] [SRC_FLAGS="..."] \
#        run_sweep.sh [bench...]
cd ~/forgetting
ROOT=$PWD
HERE=$ROOT/src_sweep
G=$HERE/bin/gem5.fast   # frozen copy of the merged gem5/build/X86/gem5.fast
CFG=$ROOT/configs/forgetting_cache/restore_measure.py
CKPT=$ROOT/spec_checkpoints_sp
OUT=${OUT:-$HERE/runs}
J=${J:-25}; FREQ=${FREQ:-3GHz}; L2=${L2:-1MiB}
DRTS_US=${DRTS_US:-10 5 20}   # 10 us first: the main comparison point
# Non-strict: violations are counted (retention.invariantViolations), not fatal
SRC_FLAGS=${SRC_FLAGS:---top_mru=4 --refresh_dirty}
BENCHES=${@:-palm_r flightdm_r femflow_r cactus_r fotonik3d_r cpython_r sqlite_r roms_r lbm_r nest_r zstd_r sealcrypto_r}
export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
[ -x $G ] || { echo "missing $G"; exit 1; }
mkdir -p $OUT
running(){ jobs -rp | wc -l; }
done_ok(){ [ -f "$1/stats.txt" ] && [ "$(grep -c 'Begin Simulation Statistics' $1/stats.txt)" -ge 2 ]; }
total=0; skipped=0
for us in $DRTS_US; do
  for b in $BENCHES; do
    n=$(ls -d $CKPT/$b/sp_* 2>/dev/null | wc -l)
    [ "$n" -eq 0 ] && { echo "WARN: no checkpoints for $b"; continue; }
    for ((i=0; i<n; i++)); do
      d=$OUT/$b/sp_$i/drt_${us}us
      if done_ok $d; then skipped=$((skipped+1)); continue; fi
      while [ "$(running)" -ge "$J" ]; do sleep 10; done
      mkdir -p $d
      $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
         --freq=$FREQ --l2_size=$L2 --l1d_size=48KiB --l1d_assoc=12 \
         --drt_ticks=$((us * 1000000)) $SRC_FLAGS > $d/run.log 2>&1 &
      total=$((total+1))
      echo "$(date +%T) launch $b sp_$i drt_${us}us"
    done
  done
done
echo "launched $total runs (skipped $skipped), J=$J DRTS_US='$DRTS_US' G=$G"
echo "OUT=$OUT SRC_FLAGS='$SRC_FLAGS'"
wait
echo "$(date +%T) src sweep done: $(find $OUT -name stats.txt | wc -l) stats files"
