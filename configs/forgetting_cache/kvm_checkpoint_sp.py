"""
KVM fast-forward -> checkpoint, at a SIMPOINT offset.

Reads simpoints.json (from cluster_bbv.py), takes checkpoint for one simpoint:
fast-forwards to (simpoint_interval_index * interval_size - warmup) on KVM,
then checkpoints.  One process per simpoint (single-shot, robust).

  ./gem5.fast -d OUT kvm_checkpoint_sp.py --bench_type=gmsh_r --sp_idx=0

Benchmark table, stdin and environment MUST match restore_measure.py.
"""

import m5
from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory import DualChannelDDR4_2400
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource, FileResource
from gem5.simulate.exit_event import ExitEvent
from gem5.simulate.simulator import Simulator

import argparse, json, os, time

parser = argparse.ArgumentParser()
parser.add_argument("--bench_type", type=str, required=True)
parser.add_argument("--sp_idx", type=int, required=True,
                    help="index into the simpoint_list")
parser.add_argument("--simpoints", type=str, default=None)
parser.add_argument("--checkpoint_dir", type=str, default=None)
parser.add_argument("--warmup", type=int, default=50_000_000,
                    help="instructions of warmup to run on O3 at restore; the "
                         "checkpoint is taken this many insts BEFORE the simpoint.")
parser.add_argument("--mem_size", type=str, default="4GiB")
args = parser.parse_args()

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
    "zstd_r": ("zstd_base.mytest", ["-b3", "-e12", "--verbose", "-i15"], None),
    "cactus_r": ("cactus_base.mytest", ["ShiftedGaugeWave.par"], None),
    "gmsh_r": ("gmsh_r_base.mytest",
        ["-option", "gmsh.opts", "-nt", "0", "sphere-discrete.geo"], None),
    "fotonik3d_r": ("fotonik3d_r_base.mytest", [], None),
    "nest_r": ("nest_r_base.mytest", ["cuba.sli"], None),
    "lbm_r": ("lbm_r_base.mytest",
        ["120", "reference.dat", "0", "0", "200_200_130_ldc.of"], None),

    # --- new ---
    "roms_r": ("roms_r_base.mytest", [], "roms_benchmark1.in.x"),
    "palm_r": ("palm_r_base.mytest", [], "runfile_atmos"),
    "flightdm_r": ("JSBSim_base.mytest", ["--nohighlight", "scripts/c3105.xml"], None),
    "femflow_r": ("femflow_r_base.mytest", ["train.prm"], None),
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

# Same environment used for BBV profiling and in restore_measure.py
BENCH_ENV = ["ACC_NUM_CORES=1", "OMP_NUM_THREADS=1", "OMP_THREAD_LIMIT=1", "LC_ALL=C"]

if args.bench_type not in SPEC_BENCHMARKS:
    print(f"Unknown benchmark '{args.bench_type}'."); exit(1)

sp_path = args.simpoints or os.path.join(
    SPEC_DIR, args.bench_type + "_train", "simpoints.json")
with open(sp_path) as f:
    sp = json.load(f)

simpoint_list = sp["simpoint_list"]
interval = sp["interval"]
if not (0 <= args.sp_idx < len(simpoint_list)):
    print(f"sp_idx {args.sp_idx} out of range (have {len(simpoint_list)})"); exit(1)

# Simpoint interval index -> instruction where the measured window STARTS.
sp_start = simpoint_list[args.sp_idx] * interval
# Checkpoint `warmup` instructions earlier so the cache warms before measuring.
target = max(1, sp_start - args.warmup)

ckpt_root = args.checkpoint_dir or os.path.join(
    ROOT_DIR, "spec_checkpoints_sp", args.bench_type)
os.makedirs(ckpt_root, exist_ok=True)
ckpt_path = os.path.join(ckpt_root, f"sp_{args.sp_idx}")

print(f"{args.bench_type} simpoint[{args.sp_idx}] = interval {simpoint_list[args.sp_idx]}")
print(f"  window start = {sp_start:,}, checkpoint at {target:,} (warmup {args.warmup:,})")

board = SimpleBoard(
    clk_freq="1GHz",          # irrelevant for KVM fast-forward; checkpoints are freq-independent
    processor=SimpleProcessor(cpu_type=CPUTypes.KVM, isa=ISA.X86, num_cores=1),
    memory=DualChannelDDR4_2400(size=args.mem_size),
    cache_hierarchy=NoCache(),
)

binary_name, bench_args, stdin_name = SPEC_BENCHMARKS[args.bench_type]
bench_dir = os.path.join(SPEC_DIR, args.bench_type + "_train")
board.set_se_binary_workload(
    binary=BinaryResource(local_path=os.path.join(bench_dir, binary_name)),
    arguments=bench_args,
    stdin_file=(FileResource(local_path=os.path.join(bench_dir, stdin_name))
                if stdin_name else None),
    env_list=BENCH_ENV,
)
for core in board.get_processor().get_cores():
    core.get_simobject().workload[0].cwd = bench_dir


def take():
    print(f"  -> checkpoint at {target:,}")
    m5.checkpoint(ckpt_path)
    print("checkpoint written")
    yield True


simulator = Simulator(board=board,
                      on_exit_event={ExitEvent.MAX_INSTS: take()})
simulator.schedule_max_insts(target)

start = time.time()
simulator.run()
print(f"Done! Took {time.time() - start:.1f} seconds")
