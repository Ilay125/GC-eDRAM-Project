"""
Stage 2: restore a KVM checkpoint into O3 + ForgettingCache, warm the caches,
measure one 100M-instruction window.  O3 parallelizes well, so run many at once.

  ./gem5.fast -d OUT restore_measure.py --bench_type=lbm_r --sample_idx=2 \
      --l1d_size=48KiB --l1d_assoc=12 --drt_ticks=10000000 --top_mru=2 --refresh_dirty

Cache latencies come from FREQ_LATENCIES[--freq] with --cpu_profile default, and
from cpu_profiles.py with --cpu_profile alecto (3 GHz only).
"""

from m5.stats import dump, reset

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.memory import DualChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA

from ForgettingL1DCache import ForgettingCache
import cpu_profiles

from gem5.resources.resource import BinaryResource, CheckpointResource, FileResource
from gem5.simulate.exit_event import ExitEvent
from gem5.simulate.simulator import Simulator

import argparse
import os
import time


# Cache latencies (cycles of the core clock) per operating frequency
FREQ_LATENCIES = {
    "1GHz": dict(l1_tag=2, l1_data=2, l1_resp=1, l2_tag=10, l2_data=10, l2_resp=1),  # legacy runs
    "3GHz": dict(l1_tag=4, l1_data=4, l1_resp=1, l2_tag=10, l2_data=10, l2_resp=1),
}

parser = argparse.ArgumentParser()

parser.add_argument("--bench_type", type=str, required=True)
parser.add_argument("--sample_idx", type=int, required=True)
parser.add_argument("--checkpoint_dir", type=str, default=None)

parser.add_argument("--warmup", type=int, default=50_000_000)
parser.add_argument("--interval", type=int, default=100_000_000)

parser.add_argument("--l1d_size", type=str, default="32KiB")
parser.add_argument("--l1d_assoc", type=int, default=8)
parser.add_argument("--l1i_size", type=str, default="32KiB")
parser.add_argument("--l1i_assoc", type=int, default=8)
# None = the profile's L2 (default: 256KiB 16-way, alecto: 256KiB 8-way)
parser.add_argument("--l2_size", type=str, default=None)
parser.add_argument("--l2_assoc", type=int, default=None)

parser.add_argument("--drt_ticks", type=int, default=0)
parser.add_argument("--top_mru", type=int, default=0)
parser.add_argument("--refresh_dirty", action="store_true")
parser.add_argument("--drt_strict", action="store_true",
                    help="Panic when a dirty block expires (default: count it).")
parser.add_argument("--refresh_set_scan_cycles", type=int, default=1,
                    help="Cycles for the refresh daemon to scan one set.")
parser.add_argument("--refresh_line_cycles", type=int, default=0,
                    help="Data-array cycles of one line refresh (0 = 2 x data latency).")
parser.add_argument("--refresh_opp_age", type=float, default=None,
                    help="Age (fraction of DRT) from which idle-time refreshes "
                         "start (unset = gem5 default 0.8).")
parser.add_argument("--retention_margin", type=float, default=None,
                    help="Safety margin of T_guard, fraction of DRT "
                         "(unset = gem5 default 0.02).")
parser.add_argument("--guard_sweeps", type=float, default=None,
                    help="Worst-case daemon sweeps in T_guard "
                         "(unset = gem5 default 1).")
parser.add_argument("--active_invalidate", action="store_true",
                    help="The daemon invalidates unkept clean lines inside "
                         "T_guard (needs --refresh_dirty, --no_inline_refresh).")
parser.add_argument("--no_inline_refresh", action="store_true",
                    help="Disable the write-triggered inline refresh.")
parser.add_argument("--inline_refresh_on_read", action="store_true",
                    help="Read hits near expiry also refresh the line.")
parser.add_argument("--refresh_banks", type=int, default=1,
                    help="L1D data-array banks (bank = set mod N); a refresh "
                         "occupies only its bank, banks refresh in parallel.")

parser.add_argument("--l1d_prefetcher", type=str, default="none",
                    choices=["none", "stride"],
                    help="L1D prefetcher (stride trains on every access).")
parser.add_argument("--pf_degree", type=int, default=4,
                    help="Prefetches generated per trigger (stride).")

parser.add_argument("--freq", type=str, default="3GHz", choices=list(FREQ_LATENCIES),
                    help="Core clock; selects the cache-latency row in FREQ_LATENCIES.")
parser.add_argument("--mem_size", type=str, default="4GiB")

parser.add_argument("--cpu_profile", type=str, default="default",
                    choices=cpu_profiles.PROFILES,
                    help="Core and cache parameters (see cpu_profiles.py).")
parser.add_argument("--l1d_hit_cycles", type=int, default=None,
                    help="L1D load-to-use cycles (alecto only: 4 or 5; default 4).")

args = parser.parse_args()

if args.cpu_profile == "default":
    l2_default = ("256KiB", 16)
else:
    if args.freq != "3GHz":
        parser.error("--cpu_profile alecto is calibrated at 3GHz only")
    l2_default = (cpu_profiles.ALECTO_L2_SIZE, cpu_profiles.ALECTO_L2_ASSOC)
if args.l2_size is None:
    args.l2_size = l2_default[0]
if args.l2_assoc is None:
    args.l2_assoc = l2_default[1]

try:
    lat = cpu_profiles.cache_latencies(args.cpu_profile, FREQ_LATENCIES[args.freq],
                                       args.l1d_hit_cycles)
except ValueError as e:
    parser.error(str(e))
print(f"[latency] {args.freq} profile={args.cpu_profile}: {lat}")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SPEC_DIR = os.path.join(ROOT_DIR, "spec_tests")

# name: (binary, [args], stdin_file_or_None)   -- train inputs, in spec_tests/<name>_train
SPEC_BENCHMARKS = {
    "sqlite_r": ("sqlite_r_base.mytest",
        ["--memdb", "--size", "500", "--testset", "main", "--verify"], None),
    "cpython_r": ("cpython_r_base.mytest",
        ["-I", "-B", "dna_bench.py", "200000"], None),
    "sealcrypto_r": ("sealcrypto_r_base.mytest",
        ["train", "australia_state_capitals_train.csv", "Victoria"], None),
    "zstd_r": ("zstd_base.mytest",
        ["-b3", "-e12", "--verbose", "-i15"], None),
    "cactus_r": ("cactus_base.mytest", ["ShiftedGaugeWave.par"], None),
    "gmsh_r": ("gmsh_r_base.mytest",
        ["-option", "gmsh.opts", "-nt", "0", "sphere-discrete.geo"], None),
    "fotonik3d_r": ("fotonik3d_r_base.mytest", [], None),
    "nest_r": ("nest_r_base.mytest", ["cuba.sli"], None),
    "lbm_r": ("lbm_r_base.mytest",
        ["120", "reference.dat", "0", "0", "200_200_130_ldc.of"], None),

    # --- new (need checkpoints before use) ---
    "roms_r": ("roms_r_base.mytest", [], "roms_benchmark1.in.x"),
    "palm_r": ("palm_r_base.mytest", [], "runfile_atmos"),
    "flightdm_r": ("JSBSim_base.mytest", ["--nohighlight", "scripts/c3105.xml"], None),
    "femflow_r": ("femflow_r_base.mytest", ["train.prm"], None),
    "stockfish_r": ("stockfish_base.mytest",
        ["bench", "1600", "1", "24", "spec_train.fen", "depth", "nnue"], None),
    "marian_r": ("marian-decoder_base.mytest",
        ["--cpu-threads", "1", "-m", "model.alphas.npz", "-v", "vocab.spm", "vocab.spm",
         "--beam-size", "2", "--mini-batch", "32", "--maxi-batch", "100",
         "--maxi-batch-sort", "src", "-w", "64", "--skip-cost",
         "--gemm-type", "intgemm8", "--intgemm-options", "precomputed-alpha", "standard-only",
         "--quiet", "--quiet-translation", "-i", "technology_and_courage.en",
         "--log", "technology_and_courage.log", "--log-level", "off",
         "-o", "technology_and_courage.out"], None),
    # --- added 2026-10-01 (spec_add/): gcc scilab.c (the most L1-sensitive of
    # the 3 train commands), omnetpp train, and omnetpp with the mesh tuned
    # to 10x10 (spec_tests/omnetpp_m10_r_train/randomMesh.ini) ---
    "gcc_r": ("cc1_r_base.mytest",
        ["scilab.c", "-O3", "-o", "scilab.c.opts-O3.s"], None),
    "omnetpp_r": ("omnetpp_r_base.mytest",
        ["-f", "randomMesh.ini", "-c", "General"], None),
    "omnetpp_m10_r": ("omnetpp_r_base.mytest",
        ["-f", "randomMesh.ini", "-c", "General"], None),
}

# Same environment used for BBV profiling
BENCH_ENV = ["ACC_NUM_CORES=1", "OMP_NUM_THREADS=1", "OMP_THREAD_LIMIT=1", "LC_ALL=C"]

if args.bench_type not in SPEC_BENCHMARKS:
    print(f"Unknown benchmark '{args.bench_type}'.")
    exit(1)

ckpt_root = args.checkpoint_dir or os.path.join(
    ROOT_DIR, "checkpoints_kvm", args.bench_type)
cpt_path = os.path.join(ckpt_root, f"sp_{args.sample_idx}")

if not os.path.isdir(cpt_path):
    print(f"Checkpoint not found: {cpt_path}")
    exit(1)

# Baseline (drt=0) must be a clean SRAM cache: no refresh machinery.
refresh = args.refresh_dirty and args.drt_ticks > 0
top_mru = args.top_mru if args.drt_ticks > 0 else 0

cache = ForgettingCache(
    l1d_size=args.l1d_size,
    l1d_assoc=args.l1d_assoc,
    l1i_size=args.l1i_size,
    l1i_assoc=args.l1i_assoc,
    l2d_size=args.l2_size,
    l2d_assoc=args.l2_assoc,

    **lat,

    drt=args.drt_ticks,
    top_mru=top_mru,
    refresh_dirty_daemon=refresh,
    retention_params=dict(
        drt_strict=args.drt_strict,
        refresh_set_scan_cycles=args.refresh_set_scan_cycles,
        refresh_line_cycles=args.refresh_line_cycles,
        inline_refresh=not args.no_inline_refresh,
        inline_refresh_on_read=args.inline_refresh_on_read,
        refresh_banks=args.refresh_banks,
        active_invalidate=args.active_invalidate,
        # Unset: keep the gem5 defaults (config.ini unchanged)
        **{k: v for k, v in (("refresh_opp_age", args.refresh_opp_age),
                             ("retention_margin", args.retention_margin),
                             ("retention_guard_sweeps", args.guard_sweeps))
           if v is not None},
    ),
    l1d_prefetcher=args.l1d_prefetcher,
    pf_degree=args.pf_degree,
)

processor = SimpleProcessor(cpu_type=CPUTypes.O3, isa=ISA.X86, num_cores=1)
cpu_profiles.apply_core(processor, args.cpu_profile)

board = SimpleBoard(
    clk_freq=args.freq,
    processor=processor,
    memory=DualChannelDDR4_2400(size=args.mem_size),
    cache_hierarchy=cache,
)

binary_name, bench_args, stdin_name = SPEC_BENCHMARKS[args.bench_type]
bench_dir = os.path.join(SPEC_DIR, args.bench_type + "_train")

board.set_se_binary_workload(
    binary=BinaryResource(local_path=os.path.join(bench_dir, binary_name)),
    arguments=bench_args,
    stdin_file=(FileResource(local_path=os.path.join(bench_dir, stdin_name))
                if stdin_name else None),
    env_list=BENCH_ENV,
    checkpoint=CheckpointResource(local_path=cpt_path),
)

for core in board.get_processor().get_cores():
    core.get_simobject().workload[0].cwd = bench_dir


def phases():
    # (1) end of warmup -> discard, start measuring
    print(f"[{args.bench_type} s{args.sample_idx}] warmup done, measuring {args.interval:,}")
    dump()
    reset()
    simulator.schedule_max_insts(args.interval)
    yield False
    # (2) end of measurement
    print(f"[{args.bench_type} s{args.sample_idx}] measurement complete")
    yield True


simulator = Simulator(
    board=board,
    on_exit_event={ExitEvent.MAX_INSTS: phases()},
)

# Restore starts on O3 directly; warm the cold cache first.
simulator.schedule_max_insts(args.warmup)

print(f"restore {cpt_path}  freq={args.freq}  cpu={args.cpu_profile}  l1d={args.l1d_size}/{args.l1d_assoc}w  "
      f"l2={args.l2_size}/{args.l2_assoc}w  drt={args.drt_ticks}  "
      f"refresh={refresh}  top_mru={top_mru}  l1d_pf={args.l1d_prefetcher}")
start = time.time()
simulator.run()
print(f"Done! Took {time.time() - start:.1f} seconds")
