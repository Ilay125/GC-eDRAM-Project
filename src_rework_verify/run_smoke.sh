#!/bin/bash
# SRC smoke: sp_0 of each bench, 48 KiB 12-way, top_mru 4, dirty refresh, strict.
# usage: run_smoke.sh <drt_ticks> <outdir> <bench...>
set -u
DRT=$1; OUT=$2; shift 2
BIN=${BIN:-/home/ilay/forgetting/bin/gem5.fast.step5}
cd /home/ilay/forgetting
export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
for b in "$@"; do
  d=$OUT/$b; mkdir -p $d
  $BIN -d $d configs/forgetting_cache/restore_measure.py --bench_type=$b \
    --sample_idx=0 --checkpoint_dir=/home/ilay/forgetting/spec_checkpoints_sp/$b \
    --freq=3GHz --l2_size=1MiB --l1d_size=48KiB --l1d_assoc=12 \
    --drt_ticks=$DRT --top_mru=4 --refresh_dirty --drt_strict \
    > $d/run.log 2>&1 &
done
wait
