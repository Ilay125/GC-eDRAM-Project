#!/bin/bash
# Bit-exactness of the rtl_align binary with every new flag off, against the
# CLK reference binary (clock_sweep/bin/gem5.fast.wbfix, gem5 9891f4056c):
# the CLK configuration and DRT = 0 (alecto A, 32 KiB) on the three
# equivalence SimPoints. Identical command lines and frozen configs.
#   rtl_align/verify.sh ; then compare with src_rework_verify/compare_stats.py
main() {
  cd ~/forgetting
  ROOT=$PWD
  OUT=$ROOT/rtl_align/verify
  NEW=$ROOT/bin/gem5.fast.rtl_align
  OLD=$ROOT/clock_sweep/bin/gem5.fast.wbfix
  CFG=$ROOT/rtl_align/configs/restore_measure.py
  CKPT=$ROOT/spec_checkpoints_sp
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
  BASE="--cpu_profile=alecto --freq=3GHz"
  CLK="--l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=2 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched"
  DRT0="--l1d_size=32KiB --l1d_assoc=8"
  for p in "palm_r 1" "sqlite_r 7" "lbm_r 4"; do
    read b i <<< "$p"
    for bin in old new; do
      G=$OLD; [ $bin = new ] && G=$NEW
      for c in clk drt0; do
        F=$CLK; [ $c = drt0 ] && F=$DRT0
        d=$OUT/$c/$bin/${b}_sp$i
        mkdir -p $d
        $G -d $d $CFG --bench_type=$b --sample_idx=$i \
          --checkpoint_dir=$CKPT/$b $BASE $F > $d/run.log 2>&1 &
      done
    done
  done
  wait
  echo "$(date +%T) verify done: $(ls $OUT/*/*/*/stats.txt | wc -l) stats files"
}
main "$@"
