import subprocess
import time

# Configurations
tests = ["b", "r", "w", "s", "p"]
sizes = {
    "8": "m13",   # 2^13 bytes = 8KB
    "16": "m14",  # 2^14 bytes = 16KB
    "32": "m15"   # 2^15 bytes = 32KB
}

MAX_PARALLEL = 10
processes = []

def run_gem5(way, size_kb, test_char, size_flag):
    """Helper to launch a gem5 process"""
    assoc = "4" if way == "4way" else "6"
    cache_size = "16KiB" if way == "4way" else "24KiB"
    
    # Directory name like stats/4way/b8
    test_id = f"{test_char}{size_kb}"
    out_dir = f"stats/{way}/{test_id}"
    
    cmd = [
        "gem5/build/X86/gem5.opt",
        "-d", out_dir,
        "configs/assoc_test/system.py",
        "--l1d_size", cache_size,
        "--l1d_assoc", assoc,
        "--bench_type", test_char,
        "--bench_size", size_flag  
    ]
    
    print(f"[LAUNCH] {way} {test_id} (Array: {size_kb}KB)")
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Main Loop
for t in tests:
    for kb, flag in sizes.items():
        for way in ["4way", "6way"]:
            # Check if we hit the limit, if so, wait for one to finish
            while len(processes) >= MAX_PARALLEL:
                for p in processes:
                    if p.poll() is not None: # Process is done
                        processes.remove(p)
                time.sleep(1) # Wait a sec before checking again

            # Launch the next simulation
            proc = run_gem5(way, kb, t, flag)
            processes.append(proc)

# Wait for the final batch to finish
print("\nAll simulations launched. Waiting for the final batch to finish...")
for p in processes:
    p.wait()

print("\nDONE! All stats are in the stats/ folder.")