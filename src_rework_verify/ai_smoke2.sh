#!/bin/bash
# Rerun of the C1-AI smoke runs after the activeInvalidateEarlyMisses stat
# (stats only). Output in src_rework_verify/ai/c1ai2/.
cd ~/forgetting
OUT=$PWD/src_rework_verify/ai/c1ai2
G=$PWD/bin/gem5.fast.active_invalidate
CFG=$PWD/configs/forgetting_cache/restore_measure.py
CKPT=$PWD/spec_checkpoints_sp
export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
F="--cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12
   --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=4 --refresh_dirty
   --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
   --active_invalidate --guard_sweeps=2 --retention_margin=0
   --no_inline_refresh --drt_strict"
for x in palm_r:1 flightdm_r:0 roms_r:0; do
  b=${x%:*}; i=${x#*:}; d=$OUT/${b}_sp$i; mkdir -p $d
  $G -d $d $CFG --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b \
    $F > $d/run.log 2>&1 &
done
wait
echo "done: $(ls $OUT/*/stats.txt | wc -l) stats files"
