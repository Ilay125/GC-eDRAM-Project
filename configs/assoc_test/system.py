"""
A cache configuration file for tutorial purposes.
Using M5 for simple cache hierarchy.
"""

import argparse

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory.single_channel import SingleChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA

from SimpleL1Cache import SimpleL1Cache

import os
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

import time

parser = argparse.ArgumentParser()

parser.add_argument(
    "--l1d_size", type=str, default="4KiB", help="Size of data L1 Cache"
)


parser.add_argument(
    "--l1d_assoc", type=int, default=4, help="Associativity of data L1 Cache"
)

parser.add_argument(
    "--bench_type", type=str, default="-b", help="Test flag from LLCbench."
)

parser.add_argument(
    "--bench_size", type=str, default="m15", help="Array size of LLCbench."
)

args = parser.parse_args()


cache = SimpleL1Cache(
    l1d_size=args.l1d_size,
    l1d_assoc=args.l1d_assoc,
    l1i_size="64KiB",
    l1i_assoc=8
)

memory = SingleChannelDDR4_2400(size="2GiB")

processor = SimpleProcessor(cpu_type=CPUTypes.TIMING, isa=ISA.X86, num_cores=1)

board = SimpleBoard(
    clk_freq="3GHz", processor=processor, memory=memory, cache_hierarchy=cache
)


# Hardcode absolute path to benchmark

if args.bench_type in ["b", "r", "w", "s", "p"]:
    binary_path = os.path.expanduser(r"~/GCeDRAM/benchmark-llcbench/cachebench/cachebench")
    test_workload = BinaryResource(binary_path)
    board.set_se_binary_workload(test_workload,
                                arguments = [f"-{args.bench_type}", "-x50000", f"-{args.bench_size}"]
                                )

elif args.bench_type == "qsort":
    binary_path = os.path.expanduser(r"~/GCeDRAM/mibench/automotive/qsort/qsort_large")
    input_file_path = os.path.expanduser(r"~/GCeDRAM/mibench/automotive/qsort/input_large.dat")

    test_workload = BinaryResource(local_path = binary_path)

    board.set_se_binary_workload(
        binary = test_workload, 
        arguments = ["1000000", input_file_path]
    )

elif args.bench_type == "dijkstra":
    binary_path = os.path.expanduser(r"~/GCeDRAM/mibench/network/dijkstra/dijkstra")
    input_file_path = os.path.expanduser(r"~/GCeDRAM/mibench/network/dijkstra/input.dat")

    test_workload = BinaryResource(local_path = binary_path)

    board.set_se_binary_workload(
        binary = test_workload, 
        arguments = ["500", input_file_path]
    )

elif args.bench_type == "patricia":
    binary_path = os.path.expanduser(r"~/GCeDRAM/mibench/network/patricia/patricia")
    input_file_path = os.path.expanduser(r"~/GCeDRAM/mibench/network/patricia/large.udp")

    test_workload = BinaryResource(local_path = binary_path)

    board.set_se_binary_workload(
        binary = test_workload, 
        arguments = [input_file_path]
    )

elif args.bench_type == "sha":
    binary_path = os.path.expanduser(r"~/GCeDRAM/mibench/security/sha/sha")
    input_file_path = os.path.expanduser(r"~/GCeDRAM/mibench/security/sha/input_large.asc")

    test_workload = BinaryResource(local_path = binary_path)

    board.set_se_binary_workload(
        binary = test_workload, 
        arguments = [input_file_path]
    )

elif args.bench_type == "rijndael":
    # Location: security/rijndael
    binary_path = os.path.expanduser(r"~/GCeDRAM/mibench/security/rijndael/rijndael")
    input_file_path = os.path.expanduser(r"~/GCeDRAM/mibench/security/rijndael/input_large.asc")
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
    binary_path = os.path.expanduser(r"~/GCeDRAM/mibench/telecomm/FFT/fft")
    
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

print(f"Done! This run took: {exec_time} second")
