import subprocess
import time
import os

# Configuration
MAX_PARALLEL = 12
processes = []

# List of MiBench tests
#mibench_tests = ["qsort", "dijkstra", "patricia", "sha", "rijndael", "fft"]
mibench_tests = ["rijndael", "fft"]

def run_gem5(way, test_name):
    """Helper to launch a gem5 process for MiBench"""
    assoc = "4" if way == "4way" else "6"
    cache_size = "16KiB" if way == "4way" else "24KiB"
    
    out_dir = f"stats/{way}/{test_name}"
    
    # Ensure directory exists (gem5 creates it, but good to keep track)
    cmd = [
        "gem5/build/X86/gem5.opt",
        "-d", out_dir,
        "configs/assoc_test/system.py",
        "--l1d_size", cache_size,
        "--l1d_assoc", assoc,
        "--bench_type", test_name
    ]
    
    print(f"[LAUNCH] {way} - {test_name}")
    # Using DEVNULL to keep your terminal from being flooded with gem5 logs
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# --- Main Simulation Loop ---
for test in mibench_tests:
    for way in ["4way", "6way"]:
        
        while len(processes) >= MAX_PARALLEL:
            for p in processes:
                if p.poll() is not None:  # poll() returns None if process is still running
                    processes.remove(p)
            time.sleep(1) # Sleep to save host CPU cycles while waiting

        # Launch the next simulation
        proc = run_gem5(way, test)
        processes.append(proc)

# --- Final Cleanup ---
print("\nAll simulations launched. Waiting for the final batch to finish...")
for p in processes:
    p.wait()

print("\nDONE! All MiBench stats are ready in the stats/ folder.")