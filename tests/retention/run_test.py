"""
Directed SRC retention test (SE mode, from program start).

  gem5.fast -d OUT tests/retention/run_test.py --drt_ticks=10000000 \
      [--refresh_dirty] [--top_mru=N] [--no_inline_refresh] [--drt_strict]
      [--refresh_banks=N] [--prog=dirty_fill] [--refresh_line_cycles=N]
      [--retention_margin=F] [--refresh_opp_age=F] [--guard_sweeps=F]
      [--active_invalidate]

Runs tests/retention/store_loop (or --prog) on O3 at 3 GHz with the same
ForgettingCache hierarchy as the SPEC sweeps (48 KiB 12-way L1D).
"""

import argparse
import os
import sys

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory import DualChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "configs", "forgetting_cache"))

from ForgettingL1DCache import ForgettingCache  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--iters", type=int, default=3_000_000)
parser.add_argument("--drt_ticks", type=int, required=True)
parser.add_argument("--top_mru", type=int, default=0)
parser.add_argument("--refresh_dirty", action="store_true")
parser.add_argument("--no_inline_refresh", action="store_true")
parser.add_argument("--drt_strict", action="store_true")
parser.add_argument("--refresh_banks", type=int, default=1)
parser.add_argument("--prog", default="store_loop",
                    choices=["store_loop", "dirty_fill", "clean_fill"])
parser.add_argument("--refresh_line_cycles", type=int, default=0)
parser.add_argument("--retention_margin", type=float, default=None)
parser.add_argument("--refresh_opp_age", type=float, default=None)
parser.add_argument("--guard_sweeps", type=float, default=None)
parser.add_argument("--active_invalidate", action="store_true")
parser.add_argument("--cold_dirty", default=None)
parser.add_argument("--keep_touched", action="store_true")
parser.add_argument("--touched_clear_age", type=float, default=None)
parser.add_argument("--prog_args", default="",
                    help="Extra program arguments after the iterations")
parser.add_argument("--silent_clean_drop", action="store_true")
parser.add_argument("--quantized_age", action="store_true")
parser.add_argument("--age_epoch_log2", type=int, default=None)
parser.add_argument("--age_bits", type=int, default=None)
parser.add_argument("--deadline_epochs", type=int, default=None)
parser.add_argument("--opp_age_epochs", type=int, default=None)
parser.add_argument("--touched_clear_epochs", type=int, default=None)
parser.add_argument("--write_buffers", type=int, default=None)
args = parser.parse_args()

cache = ForgettingCache(
    l1d_size="48KiB", l1d_assoc=12,
    l1i_size="32KiB", l1i_assoc=8,
    l2d_size="1MiB", l2d_assoc=16,
    l1_tag_latency=4, l1_data_latency=4, l1_response_latency=1,
    l2_tag_latency=10, l2_data_latency=10, l2_response_latency=1,
    drt=args.drt_ticks,
    top_mru=args.top_mru,
    refresh_dirty_daemon=args.refresh_dirty,
    retention_params=dict(
        drt_strict=args.drt_strict,
        inline_refresh=not args.no_inline_refresh,
        refresh_banks=args.refresh_banks,
        refresh_line_cycles=args.refresh_line_cycles,
        active_invalidate=args.active_invalidate,
        keep_touched=args.keep_touched,
        # Unset: keep the gem5 defaults
        **{k: v for k, v in (("retention_margin", args.retention_margin),
                             ("refresh_opp_age", args.refresh_opp_age),
                             ("retention_guard_sweeps", args.guard_sweeps),
                             ("cold_dirty", args.cold_dirty),
                             ("touched_clear_age", args.touched_clear_age),
                             # RTL alignment: passed only when set
                             ("silent_clean_drop",
                              args.silent_clean_drop or None),
                             ("quantized_age", args.quantized_age or None),
                             ("age_epoch_log2", args.age_epoch_log2),
                             ("age_bits", args.age_bits),
                             ("deadline_epochs", args.deadline_epochs),
                             ("opp_age_epochs", args.opp_age_epochs),
                             ("touched_clear_epochs",
                              args.touched_clear_epochs),
                             ("write_buffers", args.write_buffers))
           if v is not None},
    ),
)

board = SimpleBoard(
    clk_freq="3GHz",
    processor=SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.X86,
                              num_cores=1),
    memory=DualChannelDDR4_2400(size="2GiB"),
    cache_hierarchy=cache,
)
board.set_se_binary_workload(
    binary=BinaryResource(local_path=os.path.join(HERE, args.prog)),
    arguments=[str(args.iters)] + args.prog_args.split(),
)

simulator = Simulator(board=board)
simulator.run()
print(f"exit: {simulator.get_last_exit_event_cause()}")
