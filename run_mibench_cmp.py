import subprocess
import time
import os
import argparse

parser = argparse.ArgumentParser()

parser.add_argument(
    "-j", type=int, default=10, help="Max number of parrallel runs."
)
args = parser.parse_args()

# Configuration
MAX_PARALLEL = args.j

print(f"MAX PARALLEL={MAX_PARALLEL}")
processes = []

# List of MiBench tests
#mibench_tests = ["bfs", "sssp", "pr", "cc", "bc", "tc"]
mibench_tests = ["qsort", "dijkstra", "patricia", "sha", "rijndael", "fft"]

BASELINE_SIZE = 64
BASELINE_ASSOC = 8

INCREASED_SIZE = 96
INCREASED_ASSOC = 12

OUT_PARENT_DIR = "l1d_forgetting/test"
debug_modes = ["1"]


DRT_POINTS = { 
    "1us": "1000000",
    "5us": "5000000",
    "10us": "10000000",
    "20us": "20000000", 
    "30us": "30000000"
}

runs = []

for mode in debug_modes:
    runs.append((f"baseline_mode{mode}_{BASELINE_SIZE}k_{BASELINE_ASSOC}way", f"{BASELINE_SIZE}KiB", BASELINE_ASSOC, "0", mode))
    runs.append((f"baseline_mode{mode}_{INCREASED_SIZE}k_{INCREASED_ASSOC}way", f"{INCREASED_SIZE}KiB", INCREASED_ASSOC, "0", mode))

for drt_name, drt_val in DRT_POINTS.items():
    for mode in debug_modes:
        runs.append(
            (f"forgetting_mode{mode}_{INCREASED_SIZE}k_{INCREASED_ASSOC}way_{drt_name}", f"{INCREASED_SIZE}KiB", INCREASED_ASSOC, drt_val, mode)
        )

def run_gem5(test_name, l1d_size, l1d_assoc, drt_ticks, debug_mode, run_name):
    """Helper to launch a gem5 process for MiBench"""

    out_dir = f"{OUT_PARENT_DIR}/{run_name}/{test_name}"
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "gem5/build/X86/gem5.opt",
        "-d", out_dir,
        "configs/forgetting_cache/system.py",
        "--l1i_size", l1d_size,
        "--l1i_assoc", str(l1d_assoc),
        "--bench_type", test_name,
        "--drt_ticks", str(drt_ticks),
        "--debug_drt_mode", str(debug_mode),
        "--freq", "1GHz",
        "--top_mru", "2",
        "--refresh_dirty"
    ]

    print(f"[LAUNCH] {run_name} - {test_name}")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# --- Main Simulation Loop ---
for test in mibench_tests:
    for run_name, size, assoc, drt, mode in runs:

        # Check if we already have the stats to avoid unnecessary re-runs
        if os.path.exists(f"{OUT_PARENT_DIR}/{run_name}/{test}/stats.txt"):
            continue

        while len(processes) >= MAX_PARALLEL:
            for p in processes[:]:
                if p.poll() is not None:
                    processes.remove(p)
            time.sleep(1)

        proc = run_gem5(test, size, assoc, drt, mode, run_name)
        processes.append(proc)


# --- Final Cleanup ---
print("\nAll simulations launched. Waiting for the final batch to finish...")
for p in processes:
    p.wait()

print("\nDONE!")