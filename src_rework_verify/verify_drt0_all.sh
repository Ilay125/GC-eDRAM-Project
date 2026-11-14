#!/bin/bash
# DRT=0 equivalence: sp_0 of every benchmark at 32 KiB/8-way and 48 KiB/12-way
# on the new binary, compared with the pre-rework SRAM sweep (bit-exact).
# Usage: [NEW=binary] verify_drt0_all.sh [bench...]
cd ~/forgetting
NEW=${NEW:-$PWD/gem5/build/X86/gem5.fast}
CFG=$PWD/configs/forgetting_cache/restore_measure.py
CKPT=$PWD/spec_checkpoints_sp
REF=$PWD/sram_mpki_sweep/runs
OUT=$PWD/src_rework_verify/final_drt0
BENCHES=${@:-cactus_r nest_r roms_r palm_r flightdm_r femflow_r lbm_r fotonik3d_r sqlite_r zstd_r cpython_r sealcrypto_r}
export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
for b in $BENCHES; do
  for s in 32 48; do
    d=$OUT/${b}_${s}k; mkdir -p $d
    $NEW -d $d $CFG --bench_type=$b --sample_idx=0 --checkpoint_dir=$CKPT/$b \
      --freq=3GHz --l2_size=1MiB --l1d_size=${s}KiB --l1d_assoc=$((s/4)) \
      > $d/run.log 2>&1 &
  done
done
wait
fail=0
for b in $BENCHES; do
  for s in 32 48; do
    c=$OUT/${b}_${s}k/compare.txt
    if ./venv/bin/python src_rework_verify/compare_stats.py \
         $REF/$b/sp_0/l1d_${s}k/stats.txt $OUT/${b}_${s}k/stats.txt > $c 2>&1; then
      echo "SAME  $b ${s}k: $(head -n 1 $c)"
    else
      echo "DIFF  $b ${s}k: $(head -n 1 $c)"; fail=$((fail+1))
    fi
  done
done
echo "DRT=0 equivalence: $fail of $(( $(echo $BENCHES | wc -w) * 2 )) differ"
