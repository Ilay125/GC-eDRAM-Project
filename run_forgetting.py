import subprocess

'''
cmd = [
        "gem5/build/X86/gem5.opt",
        "-d", "test_stats2",
        "configs/forgetting_cache/system.py",
        "--l1d_size", "16KiB",
        "--l1d_assoc", "4",
        "--drt_ticks", "100"
    ]

subprocess.run(cmd, check=True)
'''

cmd = [
        "gem5/build/X86/gem5.opt",
        "-d", "test_stats",
        "configs/forgetting_cache/system.py",
        "--l1d_size", "16KiB",
        "--l1d_assoc", "4",
        "--drt_ticks", "10"
    ]

subprocess.run(cmd, check=True)