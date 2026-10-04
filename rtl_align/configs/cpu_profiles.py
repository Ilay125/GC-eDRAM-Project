"""
CPU profiles shared by restore_measure.py and the latency calibration
(alecto_sweep/calib/run_chase.py), so both build the same machine.

  default  gem5 O3 defaults (8-wide, ROB 192, IQ 64, LQ/SQ 32/32) and the
           FREQ_LATENCIES row of restore_measure.py. Every result before the
           Alecto sweep used it; it changes nothing.
  alecto   Alecto (Li, Zhang, Ren, Xie, HPCA 2025, Table I; arXiv 2503.19390),
           a Skylake-like core. Table I gives no rename/dispatch width: they are
           set to the decode width (6). Physical registers and the branch
           predictor stay at the gem5 defaults (not in Table I).
           No L3 (Table I has one; left out on purpose).
           needsTSO off (session 4): gem5's X86 O3 keeps one store in flight
           under TSO, so stores drain at one per L1 hit latency (3-4 cycles
           each), far slower than a real core's pipelined store buffer.
           Single core in SE mode: nothing else can observe store order.
           The first A/C0/C1 run (alecto_sweep/configs) still had it on.
"""

ALECTO_CORE = dict(
    numROBEntries=256,
    LQEntries=72,
    SQEntries=56,
    fetchWidth=6,
    decodeWidth=6,
    renameWidth=6,     # not in Table I: = decode width
    dispatchWidth=6,   # not in Table I: = decode width
    issueWidth=8,
    wbWidth=8,
    commitWidth=4,
)
ALECTO_IQ_ENTRIES = 256
ALECTO_NEEDS_TSO = False     # X86O3CPU default: True (one store in flight)

# Cache parameters in cycles of the 3 GHz core clock, set by measurement with
# the pointer chase in alecto_sweep/calib (load-to-use, see CLAUDE.md), not by
# adding up Table I. L1D: load-to-use cycles -> (tag, data, response).
# 4 = Table I (32 KiB); 5 = the 48 KiB 12-way L1D of Berti / Ice Lake.
ALECTO_L1D_HIT = {
    4: (3, 3, 1),
    5: (4, 4, 1),
}
ALECTO_L1I = (3, 3, 1)       # same as the 4-cycle L1D
ALECTO_L2 = (8, 8, 1)        # 15-cycle load-to-use with the 4-cycle L1D
ALECTO_L2_SIZE = "256KiB"
ALECTO_L2_ASSOC = 8
ALECTO_L2_MSHRS = 32         # L1I/L1D: 16 MSHRs, already the stdlib default

PROFILES = ("default", "alecto")


def cache_latencies(profile, freq_row, l1d_hit_cycles=None):
    """ForgettingCache latency kwargs of a profile.

    freq_row is the FREQ_LATENCIES row used by the default profile.
    """
    if profile == "default":
        if l1d_hit_cycles is not None:
            raise ValueError("--l1d_hit_cycles needs --cpu_profile alecto")
        return dict(
            l1_tag_latency=freq_row["l1_tag"],
            l1_data_latency=freq_row["l1_data"],
            l1_response_latency=freq_row["l1_resp"],
            l2_tag_latency=freq_row["l2_tag"],
            l2_data_latency=freq_row["l2_data"],
            l2_response_latency=freq_row["l2_resp"],
        )
    if profile == "alecto":
        hit = 4 if l1d_hit_cycles is None else l1d_hit_cycles
        if hit not in ALECTO_L1D_HIT:
            raise ValueError(f"--l1d_hit_cycles {hit} is not calibrated "
                             f"(choices: {sorted(ALECTO_L1D_HIT)})")
        l1i, l1d, l2 = ALECTO_L1I, ALECTO_L1D_HIT[hit], ALECTO_L2
        return dict(
            l1_tag_latency=l1i[0],
            l1_data_latency=l1i[1],
            l1_response_latency=l1i[2],
            l1d_tag_latency=l1d[0],
            l1d_data_latency=l1d[1],
            l1d_response_latency=l1d[2],
            l2_tag_latency=l2[0],
            l2_data_latency=l2[1],
            l2_response_latency=l2[2],
            l2_mshrs=ALECTO_L2_MSHRS,
        )
    raise ValueError(f"unknown cpu profile {profile}")


def apply_core(processor, profile):
    """Set the O3 core parameters of a profile on every core."""
    if profile == "default":
        return
    assert profile == "alecto", profile
    for core in processor.get_cores():
        cpu = core.get_simobject()
        for name, value in ALECTO_CORE.items():
            setattr(cpu, name, value)
        cpu.instQueues[0].numEntries = ALECTO_IQ_ENTRIES
        cpu.needsTSO = ALECTO_NEEDS_TSO
