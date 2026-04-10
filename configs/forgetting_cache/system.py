import argparse

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory.single_channel import SingleChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA

from ForgettingL1Cache import ForgettingL1Cache

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
    "--drt_ticks", type=int, default=0, help="Data retention time (DRT) in ticks."
)

parser.add_argument(
    "--wt", action="store_true", help="Using write-through policy."
)

args = parser.parse_args()

cache = ForgettingL1Cache(
    l1d_size=args.l1d_size,
    l1d_assoc=args.l1d_assoc,
    l1i_size="64KiB",
    l1i_assoc=8,
    drt=args.drt_ticks,
    writeback_policy=not args.wt
)

memory = SingleChannelDDR4_2400(size="2GiB")

processor = SimpleProcessor(cpu_type=CPUTypes.TIMING, isa=ISA.X86, num_cores=1)

board = SimpleBoard(
    clk_freq="3GHz", processor=processor, memory=memory, cache_hierarchy=cache
)

binary_path = os.path.expanduser(r"~/GCeDRAM/gem5/configs/tutorial/drt_test.exe")
test_workload = BinaryResource(binary_path)
board.set_se_binary_workload(test_workload)

simulation = Simulator(board=board)

print("Simulation started.")

start_time = time.time()

simulation.run(max_ticks=int(1e12))

exec_time = time.time() - start_time

print(f"Done! This run took: {exec_time} seconds")
