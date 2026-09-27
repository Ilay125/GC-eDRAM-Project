from gem5.components.boards.simple_board import SimpleBoard

from gem5.components.memory import DualChannelDDR4_2400

from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA

from ForgettingL1DCache import ForgettingCache

from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

import argparse
import time
import os

# Cache latencies (cycles of the core clock) per operating frequency
FREQ_LATENCIES = {
    "1GHz": dict(l1_tag=2, l1_data=2, l1_resp=1, l2_tag=10, l2_data=10, l2_resp=1),  # legacy runs
    "3GHz": dict(l1_tag=4, l1_data=4, l1_resp=1, l2_tag=10, l2_data=10, l2_resp=1),
}

parser = argparse.ArgumentParser()

parser.add_argument(
    "--l1d_size", type=str, default="32KiB", help="Size of data L1 Cache"
)

parser.add_argument(
    "--l1d_assoc", type=int, default=8, help="Associativity of data L1 Cache"
)

parser.add_argument(
    "--l1i_size", type=str, default="32KiB", help="Size of instruction L1 Cache"
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
    "--bench_type", type=str, default="stockfish", help="SPEC benchmark to run."
)

parser.add_argument(
    "--freq", type=str, default="1GHz", help="CPU Frequency.", choices=list(FREQ_LATENCIES)
)

parser.add_argument(
    "--top_mru", type=int, default=0, help="N top mru block to actively refresh via daemon."
)

parser.add_argument(
    "--refresh_dirty", action="store_true", help="Refresh dirty blocks using daemon process"
)

# ---- Stockfish-specific knobs -------------------------------------------------
parser.add_argument(
    "--st_hash", type=int, default=16,
    help="Stockfish transposition-table size in MB (SPEC ref uses 1600)."
)

parser.add_argument(
    "--st_depth", type=int, default=10,
    help="Stockfish search depth (SPEC ref uses 26)."
)

parser.add_argument(
    "--st_eval", type=str, default="classical",
    help="Stockfish eval type: classical or nnue."
)

parser.add_argument(
    "--st_fen", type=str, default="spec_ref_pos_1to6.fen",
    help="FEN input file name (inside the stockfish test dir)."
)

args = parser.parse_args()

lat = FREQ_LATENCIES[args.freq]

cache = ForgettingCache(
    l1d_size=args.l1d_size,
    l1d_assoc=args.l1d_assoc,

    l1_tag_latency=lat["l1_tag"],
    l1_data_latency=lat["l1_data"],
    l1_response_latency=lat["l1_resp"],

    l1i_size=args.l1i_size,
    l1i_assoc=args.l1i_assoc,

    l2d_size=args.l2_size,
    l2d_assoc=args.l2_assoc,

    l2_tag_latency=lat["l2_tag"],
    l2_data_latency=lat["l2_data"],
    l2_response_latency=lat["l2_resp"],

    drt=args.drt_ticks,
    debug_drt_mode=args.debug_drt_mode,
    top_mru=args.top_mru,
    refresh_dirty_daemon=args.refresh_dirty
)

memory = DualChannelDDR4_2400(size="2GiB")

processor = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.X86, num_cores=1)

board = SimpleBoard(
    clk_freq=args.freq, processor=processor, memory=memory, cache_hierarchy=cache
)


# Dynamically find the root directory (the parent of the 'configs' folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

# Where the SPEC test binaries/inputs live: ~/GCeDRAM/spec_tests/...
SPEC_DIR = os.path.join(ROOT_DIR, "spec_tests")


# ---- SPEC benchmarks ----------------------------------------------------------

# 706.stockfish_r
if args.bench_type == "stockfish":
    binary_path = os.path.join(SPEC_DIR, "stockfish", "stockfish_base.mytest")
    fen_path = os.path.join(SPEC_DIR, "stockfish", args.st_fen)

    test_workload = BinaryResource(local_path=binary_path)

    # Native SPEC invocation:
    #   bench 1600 1 26 spec_ref_pos_1to6.fen depth classical
    board.set_se_binary_workload(
        binary=test_workload,
        arguments=[
            "bench",
            str(args.st_hash),   # TT size in MB
            "1",                 # threads (keep 1 for SE mode)
            str(args.st_depth),  # search depth
            fen_path,            # absolute path to FEN input
            "depth",             # limit type
            args.st_eval,        # classical / nnue
        ],
    )

else:
    print("No SPEC benchmark matched --bench_type.")
    exit()


simulation = Simulator(board=board)

print("Simulation started.")

start_time = time.time()

simulation.run(max_ticks=int(1e12))

exec_time = time.time() - start_time

print(f"Done! This run took: {exec_time} seconds")