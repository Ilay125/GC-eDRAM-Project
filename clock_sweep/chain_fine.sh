#!/bin/bash
# Wait for the write-buffer rerun, then sweep the finer clear ages with the
# fixed binary. Log: clock_sweep/sweep_fine.log
main() {
  cd ~/forgetting
  while ! grep -q "wbfix rerun done" clock_sweep/wbfix.log 2>/dev/null; do
    sleep 60
  done
  echo "$(date +%T) wbfix rerun done, starting CLK05 CLK10 CLK15"
  G=$PWD/clock_sweep/bin/gem5.fast.wbfix CONFIGS="CLK05 CLK10 CLK15" \
    J=30 RESERVE_GB=10 clock_sweep/run_sweep.sh
}
main "$@"
