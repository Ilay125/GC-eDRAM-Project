#!/bin/bash
# Bit-exactness of bin/gem5.fast.rtl_align2 (line scanner, line budget, new
# stamp check) with every new flag off, against bin/gem5.fast.rtl_align:
# the RTL sweep configuration (set scanner, 8 banks, F 29) and DRT = 0
# (alecto A, 32 KiB) on the three equivalence SimPoints. Each binary with
# its own frozen configs (configs2 only adds the two new flags).
#   rtl_align/verify2.sh ; then compare with src_rework_verify/compare_stats.py
main() {
  cd ~/forgetting
  ROOT=$PWD
  OUT=$ROOT/rtl_align/verify2
  CKPT=$ROOT/spec_checkpoints_sp
  export ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C
  BASE="--cpu_profile=alecto --freq=3GHz"
  RTL="--l1d_size=48KiB --l1d_assoc=12
    --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=0 --refresh_dirty
    --refresh_banks=8 --refresh_line_cycles=2 --refresh_opp_age=0.8
    --active_invalidate --guard_sweeps=1 --retention_margin=0
    --no_inline_refresh --cold_dirty=touched --keep_touched
    --quantized_age --age_epoch_log2=10 --age_bits=5"
  DRT0="--l1d_size=32KiB --l1d_assoc=8"
  for p in "palm_r 1" "sqlite_r 7" "lbm_r 4"; do
    read b i <<< "$p"
    for bin in old new; do
      G=$ROOT/bin/gem5.fast.rtl_align
      CFG=$ROOT/rtl_align/configs/restore_measure.py
      if [ $bin = new ]; then
        G=$ROOT/bin/gem5.fast.rtl_align2
        CFG=$ROOT/rtl_align/configs2/restore_measure.py
      fi
      for c in rtl drt0; do
        F=$RTL; [ $c = drt0 ] && F=$DRT0
        d=$OUT/$c/$bin/${b}_sp$i
        mkdir -p $d
        $G -d $d $CFG --bench_type=$b --sample_idx=$i \
          --checkpoint_dir=$CKPT/$b $BASE $F > $d/run.log 2>&1 &
      done
    done
  done
  wait
  echo "$(date +%T) verify2 done: $(ls $OUT/*/*/*/stats.txt | wc -l) stats files"
}
main "$@"
