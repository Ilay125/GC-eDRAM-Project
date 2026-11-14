#!/bin/bash
# Equivalence checks for the SRC rework (gem5 branch src-rework).
# Usage: src_rework_verify.sh <step-name>
cd ~/forgetting
STEP=${1:?step name}
OUT=$PWD/src_rework_verify/$STEP
NEW=${NEW:-$PWD/gem5/build/X86/gem5.fast}
OLD=$PWD/bin/gem5.fast.pre-rework
CFG=$PWD/configs/forgetting_cache/restore_measure.py
OLDCFG=${OLDCFG:-}
CKPT=$PWD/spec_checkpoints_sp
COMMON="--freq=3GHz --l2_size=1MiB"
SRC="--l1d_size=48KiB --l1d_assoc=12 --drt_ticks=10000000 --top_mru=4 --refresh_dirty"
run() { # dir binary config bench sp args...
  local d=$1 g=$2 c=$3 b=$4 i=$5; shift 5
  mkdir -p $d
  $g -d $d $c --bench_type=$b --sample_idx=$i --checkpoint_dir=$CKPT/$b $COMMON "$@" > $d/run.log 2>&1 &
}
run $OUT/drt0/palm_r_sp1   $NEW $CFG palm_r 1   --l1d_size=32KiB --l1d_assoc=8
run $OUT/drt0/sqlite_r_sp7 $NEW $CFG sqlite_r 7 --l1d_size=32KiB --l1d_assoc=8
run $OUT/drt0/lbm_r_sp4    $NEW $CFG lbm_r 4    --l1d_size=32KiB --l1d_assoc=8
run $OUT/src_new/palm_r_sp1 $NEW $CFG palm_r 1 $SRC
[ -n "$OLDCFG" ] && run $OUT/src_old/palm_r_sp1 $OLD $OLDCFG palm_r 1 $SRC
wait
echo "done: $(ls $OUT/*/*/stats.txt | wc -l) stats files"
