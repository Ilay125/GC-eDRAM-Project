#!/bin/bash
# CLOCK keep rule with the bit also cleared at 50% of DRT, with top_mru 0 and 1, strict, on the smoke
# SimPoints. Output in src_rework_verify/ai/cold/clock_top<k>/<bench>_sp<i>/.
cd ~/forgetting
OUT=$PWD/src_rework_verify/ai/cold
G=$PWD/bin/gem5.fast.clock_half
CFG=$PWD/configs/forgetting_cache/restore_measure.py
CKPT=$PWD/spec_checkpoints_sp
export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
F="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
   --l1d_hit_cycles=5 --drt_ticks=10000000 --refresh_dirty
   --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
   --active_invalidate --guard_sweeps=2 --retention_margin=0
   --no_inline_refresh --drt_strict --cold_dirty=touched --keep_touched --touched_clear_age=0.5"
for k in 0 1; do
  for x in palm_r:1 flightdm_r:0 roms_r:0; do
    b=${x%:*}; i=${x#*:}; d=$OUT/clock_half_top$k/${b}_sp$i; mkdir -p $d
    $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
      $F --top_mru=$k > $d/run.log 2>&1 &
  done
done
wait
echo "done: $(ls $OUT/clock_half_top*/*/stats.txt | wc -l) stats files"
