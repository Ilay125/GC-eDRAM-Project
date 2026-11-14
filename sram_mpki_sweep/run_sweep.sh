#!/bin/bash
# Non-forgetting L1D capacity sweep: 16/32/48/64/96 KiB at 64 sets (assoc = size/4), DRT=0.
cd ~/forgetting
ROOT=$PWD
G=$ROOT/gem5/build/X86/gem5.fast
CFG=$ROOT/configs/forgetting_cache/restore_measure.py
CKPT=$ROOT/spec_checkpoints_sp
OUT=$ROOT/sram_mpki_sweep/runs
J=${J:-25}; FREQ=${FREQ:-3GHz}; L2=${L2:-1MiB}
SIZES="16 32 48 64 96"
BENCHES=${@:-sqlite_r cpython_r sealcrypto_r zstd_r cactus_r fotonik3d_r nest_r lbm_r roms_r palm_r flightdm_r femflow_r}
mkdir -p $OUT
running(){ jobs -rp | wc -l; }
done_ok(){ [ -f "$1/stats.txt" ] && [ "$(grep -c 'Begin Simulation Statistics' $1/stats.txt)" -ge 2 ]; }
total=0; skipped=0
for b in $BENCHES; do
  n=$(ls -d $CKPT/$b/sp_* 2>/dev/null | wc -l)
  [ "$n" -eq 0 ] && { echo "WARN: no checkpoints for $b"; continue; }
  for ((i=0; i<n; i++)); do
    for s in $SIZES; do
      d=$OUT/$b/sp_$i/l1d_${s}k
      if done_ok $d; then skipped=$((skipped+1)); continue; fi
      while [ "$(running)" -ge "$J" ]; do sleep 10; done
      mkdir -p $d
      $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
         --freq=$FREQ --l2_size=$L2 --l1d_size=${s}KiB --l1d_assoc=$((s/4)) > $d/run.log 2>&1 &
      total=$((total+1))
    done
  done
done
echo "launched $total runs (skipped $skipped), J=$J FREQ=$FREQ L2=$L2"
wait
echo "sram mpki sweep done: $(find $OUT -name stats.txt | wc -l) stats files"
