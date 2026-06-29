
from gem5.components.boards.simple_board import SimpleBoard

#from gem5.components.memory.single_channel import SingleChannelDDR4_2400

#from gem5.components.memory.memory import ChanneledMemory
#from gem5.components.memory.dram_interfaces.ddr5 import DDR5_4400_4x8

from gem5.components.memory import DualChannelDDR4_2400

from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA

from ForgettingL1ICache import ForgettingCache

from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

import argparse
import time
import os


parser = argparse.ArgumentParser()

parser.add_argument(
    "--l1d_size", type=str, default="16KiB", help="Size of data L1 Cache"
)

parser.add_argument(
    "--l1d_assoc", type=int, default=4, help="Associativity of data L1 Cache"
)

parser.add_argument(
    "--l1i_size", type=str, default="64KiB", help="Size of instruction L1 Cache"
)

parser.add_argument(
    "--l1i_assoc", type=int, default=8, help="Associativity of instruction L1 Cache"
)

parser.add_argument(
    "--l2_size", type=str, default="256KiB", help="Size of data L2 Cache"
)

parser.add_argument(
    "--l2_assoc", type=int, default=16, help="Associativity of data L2 Cache"
)

parser.add_argument(
    "--drt_ticks", type=int, default=0, help="Data retention time (DRT) in ticks."
)

parser.add_argument(
    "--debug_drt_mode", type=int, default=1, help="Using write-through policy."
)

parser.add_argument(
    "--bench_type", type=str, default="test", help="Test flag from LLCbench."
)

parser.add_argument(
    "--freq", type=str, default="1GHz", help="CPU Frequency."
)

parser.add_argument(
    "--top_mru", type=int, default=0, help="N top mru block to actively refresh via daemon."
)

parser.add_argument(
    "--delay", type=str, default="0", help="number of delay iterations for retbench."
)

parser.add_argument(
    "--refresh_dirty", action="store_true", help="Refresh dirty blocks using daemon process"
)

parser.add_argument(
    "--bench_size", type=int, default=0, help="log2 of the size of gapbs test."
)

args = parser.parse_args()

cache = ForgettingCache(
    l1d_size=args.l1d_size,
    l1d_assoc=args.l1d_assoc,
    l1i_size=args.l1i_size,
    l1i_assoc=args.l1i_assoc,

    l2_size=args.l2_size,
    l2_assoc=args.l2_assoc,

    l3_size="2MiB",
    l3_assoc=16,

    drt=args.drt_ticks,
    debug_drt_mode=args.debug_drt_mode,
    top_mru=args.top_mru,
    refresh_dirty_daemon=args.refresh_dirty
)

'''
memory = ChanneledMemory(
    DDR5_4400_4x8, 
    num_channels=2, 
    interleaving_size=64, 
    size="2GiB"
)
'''
memory = DualChannelDDR4_2400(size="2GiB")

processor = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.X86, num_cores=1)

board = SimpleBoard(
    clk_freq=args.freq, processor=processor, memory=memory, cache_hierarchy=cache
)


# Dynamically find the root directory (the parent of the 'configs' folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))


# General Test
if args.bench_type == "test":
    binary_path = os.path.join(ROOT_DIR, "gem5", "configs", "tutorial", "test")

    test_workload = BinaryResource(local_path=binary_path)
    board.set_se_binary_workload(binary=test_workload)

# Retbench
elif args.bench_type == "ret_deadblk":
    binary_path = os.path.join(ROOT_DIR, "retbench", "deadblk", "deadblk.exe")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[args.delay]
    )

elif args.bench_type == "ret_mixed":
    binary_path = os.path.join(ROOT_DIR, "retbench", "mixed", "mixed.exe")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[args.delay, "5"] # stride=2 (20% write) 
    )

elif args.bench_type == "ret_seq":
    binary_path = os.path.join(ROOT_DIR, "retbench", "sequential", "sequential.exe")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[args.delay]
    )

elif args.bench_type == "ret_temp":
    binary_path = os.path.join(ROOT_DIR, "retbench", "temporal", "temporal.exe")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[args.delay]
    )

elif args.bench_type == "ret_wb":
    binary_path = os.path.join(ROOT_DIR, "retbench", "writebacks", "writebacks.exe")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[args.delay]
    )

# gapbs
elif args.bench_type == "bfs":
    binary_path = os.path.join(ROOT_DIR, "gapbs", "bfs")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["-g", f"{args.bench_size}", "-n", "1"]
    )

elif args.bench_type == "sssp":
    binary_path = os.path.join(ROOT_DIR, "gapbs", "sssp")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["-g", f"{args.bench_size}", "-n", "1"]
    )

elif args.bench_type == "pr":
    binary_path = os.path.join(ROOT_DIR, "gapbs", "pr")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["-g", f"{args.bench_size}", "-n", "1"]
    )

elif args.bench_type == "cc":
    binary_path = os.path.join(ROOT_DIR, "gapbs", "cc")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["-g", f"{args.bench_size}", "-n", "1"]
    )

elif args.bench_type == "bc":
    binary_path = os.path.join(ROOT_DIR, "gapbs", "bc")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["-g", f"{args.bench_size}", "-n", "1"]
    )

elif args.bench_type == "tc":
    binary_path = os.path.join(ROOT_DIR, "gapbs", "tc")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["-g", f"{args.bench_size}", "-n", "1"]
    )

# Mibench
elif args.bench_type == "qsort":
    binary_path = os.path.join(ROOT_DIR, "mibench", "automotive", "qsort", "qsort_large")
    input_file_path = os.path.join(ROOT_DIR, "mibench", "automotive", "qsort", "input_large.dat")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["1000000", input_file_path]
    )

elif args.bench_type == "dijkstra":
    binary_path = os.path.join(ROOT_DIR, "mibench", "network", "dijkstra", "dijkstra")
    input_file_path = os.path.join(ROOT_DIR, "mibench", "network", "dijkstra", "input.dat")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["500", input_file_path]
    )

elif args.bench_type == "patricia":
    binary_path = os.path.join(ROOT_DIR, "mibench", "network", "patricia", "patricia")
    input_file_path = os.path.join(ROOT_DIR, "mibench", "network", "patricia", "large.udp")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[input_file_path]
    )

elif args.bench_type == "sha":
    binary_path = os.path.join(ROOT_DIR, "mibench", "security", "sha", "sha")
    input_file_path = os.path.join(ROOT_DIR, "mibench", "security", "sha", "input_large.asc")

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[input_file_path]
    )

elif args.bench_type == "rijndael":
    # Location: security/rijndael
    binary_path = os.path.join(ROOT_DIR, "mibench", "security", "rijndael", "rijndael")
    input_file_path = os.path.join(ROOT_DIR, "mibench", "security", "rijndael", "input_large.asc")
    
    # Output file can be local; gem5 keeps it in the simulation directory
    output_file_path = "output.enc"
    # A standard 128-bit hex key (32 chars)
    hex_key = "1234567890abcdeffedcba0987654321" 

    test_workload = BinaryResource(local_path=binary_path)

    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=[input_file_path, output_file_path, "e", hex_key]
    )

elif args.bench_type == "fft":
    # Location: telecomm/fft
    binary_path = os.path.join(ROOT_DIR, "mibench", "telecomm", "FFT", "fft")
    
    test_workload = BinaryResource(local_path=binary_path)

    # Arguments: <n_waves> <n_samples>
    # "8 32768" is the standard 'large' workload for MiBench
    board.set_se_binary_workload(
        binary=test_workload, 
        arguments=["8", "32768"]
    )

else:
     print("No test was found.")
     exit()


simulation = Simulator(board=board)

print("Simulation started.")

start_time = time.time()

simulation.run(max_ticks=int(1e12))

exec_time = time.time() - start_time

print(f"Done! This run took: {exec_time} seconds")
