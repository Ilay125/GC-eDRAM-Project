import subprocess
import time
import os

# Configuration
MAX_PARALLEL = 12
processes = []

# List of MiBench tests
mibench_tests = ["qsort", "dijkstra", "patricia", "sha", "rijndael", "fft"]

def run_gem5(way_config, test_name):
    """Helper to launch a gem5 process for MiBench"""
    
    # Logical mapping for sizes to keep stats folders clean
    if way_config == "4_24kB":
        cache_size = "24KiB"
        assoc = "4"
        out_dir = f"stats/4_24kB/{test_name}"
    elif way_config == "6_24kB":
        cache_size = "24KiB"
        assoc = "6"
        out_dir = f"stats/6_24kB/{test_name}"
    elif way_config == "6way":
        cache_size = "24KiB"
        assoc = "6"
        out_dir = f"stats/6way/{test_name}"
    else:
        cache_size = "16KiB"
        assoc = "4"
        out_dir = f"stats/4way/{test_name}"
    
    os.makedirs(out_dir, exist_ok=True)
    
    cmd = [
        "gem5/build/X86/gem5.opt",
        "-d", out_dir,
        "configs/assoc_test/system.py",
        "--l1d_size", cache_size,
        "--l1d_assoc", assoc,
        "--bench_type", test_name,
        "--idx_policy", "modulo"
    ]
    
    print(f"[LAUNCH] {way_config} ({cache_size}) - {test_name}")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# --- Main Simulation Loop ---
for test in mibench_tests:
    for config in ["4_24kB", "6_24kB"]:
        
        # Check if we already have the stats to avoid unnecessary re-runs
        if os.path.exists(f"stats/{config}/{test}/stats.txt"):
            continue

        while len(processes) >= MAX_PARALLEL:
            for p in processes:
                if p.poll() is not None:
                    processes.remove(p)
            time.sleep(1)

        proc = run_gem5(config, test)
        processes.append(proc)

# --- Final Cleanup ---
print("\nAll simulations launched. Waiting for the final batch to finish...")
for p in processes:
    p.wait()

print("\nDONE! New isolated stats are in stats/4_24kB/.")