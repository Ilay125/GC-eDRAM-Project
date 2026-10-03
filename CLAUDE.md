# CLAUDE.md: SRC (Selective Retention Cache) thesis project

Handoff for future Claude Code sessions. Last updated 2026-09-30 (session 4: Alecto-core profile, calibration, A/C0/C1 sweep; see section 11).
Read all of it before touching anything. Section 11 is the current work; section 9 is the earlier state.

---

## 1. Project in one paragraph

M.Sc. thesis (Technion, ACSL lab), advisor Prof. Mark Silberstein (contact via Discord; raise open
questions and trade-offs, don't present things as settled, don't restate results he has already seen).
**SRC = Selective Retention Cache**: an L1D built from GC-eDRAM (gain-cell eDRAM). Its blocks lose their
data a **data retention time (DRT)** after the last full-line write, instead of being refreshed
continuously. That gives roughly 50% more capacity than SRAM in the same area (e.g. 48 KiB SRC in the area of 32 KiB SRAM).
In code and conversation it is called **"forgetting"**. The evaluation is **out-of-order only** (the in-order
direction was dropped). The thesis proposal is finished; don't touch it. **DRT = 0 means a plain SRAM cache** (the baseline).

Physics we model: a store recharges only the cells it writes; reads don't recharge. Only a **full-line
write** (fill from L2, a daemon refresh, an inline refresh) recharges a line. There are no per-word valid
bits: the whole block expires together once `now - fullChargeTick >= DRT`.

---

## 2. Machine and environment

- Server `acsl-serv02`: 64 cores, 187 GB RAM. The root disk is shared and **98% full (~13 GB free)**.
  Check `df -h ~` before big sweeps. Don't enable gem5 debug flags or traces in sweeps.
  Core dumps go to apport (`/var/crash`), not the working directory.
- **RAM / J (measured session 4):** every restore run peaks at **4.2–4.5 GiB** RSS, all benchmarks alike (palm 4.36, femflow/nest 4.46 max;
  the restored 4 GiB guest image is fully resident, plus gem5). So 50 runs (~220 GiB) OOM. **User rule: always keep ≥ 10 GiB free for other users.**
  Size J = (187 − what others use now − 10) / 4.5; check `free -g` and your own RSS first. With others at ~40 GiB this gives **J = 30**.
  The old "15 if palm-heavy" note is not supported by the data.
- The server's `head`/`tail` need `-n N` (the `-3` shorthand is not accepted).
- `perf_event_paranoid` must be ≤ 1 for KVM (already persisted in `/etc/sysctl.d/99-gem5-kvm.conf`).
- Python venv: `~/forgetting/venv/bin/python` (has matplotlib 3.11, pandas 3.0).
- Environment for every benchmark run: `ACC_NUM_CORES=1 OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 LC_ALL=C`.

---

## 3. Repositories, branches, commit rules

There are **two git repos**.

| Repo | Path | Remote | Branches |
|---|---|---|---|
| Outer project | `~/forgetting` | GitHub `Ilay125/GC-eDRAM-Project` | `master` (old work), **`src-rework`** (current) |
| gem5 fork (v25.1) | `~/forgetting/gem5` | GitHub `Ilay125/gem5ForgettingCache` | `stable` (pre-rework, `ac48641acd`), **`src-rework`** (current) |

- **All the SRC rework is on `src-rework` in both repos**, so there's a fallback. Don't commit rework to
  `stable` or `master`. Nothing has been pushed.
- **Commit identity:** `git -c user.name=Ilay125 -c user.email=ilaybl125@gmail.com commit ...`. The server has
  no global git identity. Don't use the old `IlayBell <ilay.ben@campus.technion.ac.il>` identity seen in history.
  End messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **gem5 pre-commit hooks** (run automatically):
  - the header needs a MAINTAINERS.yaml tag, e.g. `mem-cache: Do X` (≤ 65 chars);
  - lines ≤ 79 chars; trailing whitespace is stripped (after a hook failure, `git add` again and re-commit);
  - clang-format check.
- The upstream gem5 base of the fork is **`7a2b0e413d`** ("misc: Release v25.1.0.0"). Use
  `git -C gem5 diff 7a2b0e413d -- src/mem` to see every fork change.
- Some config files use **CRLF** line endings (e.g. `configs/forgetting_cache/ForgettingL1DCache.py`).
  Edit them preserving CRLF (`open(p, newline="")`), or the whole file shows as changed. Normalizing
  line endings is a separate, pending hygiene task.
- Most of the outer repo is **untracked** (`git status` shows many `??`). The rework branch tracks only what
  was needed: `restore_measure.py`, `kvm_checkpoint_sp.py`, tests, verification scripts, `.gitignore`.

### Commits on `src-rework` (oldest first)

gem5:
1. `880ab92820` mem-cache: Remove non-SRC deviations from upstream
2. `6b78af96e1` mem-cache: Move SRC logic into RetentionManager
3. `67a673ff46` mem-cache: Count every SRC retention backdoor
4. `f4112754aa` mem-cache: Add SRC refresh timing and retention guarantee
5. `12c5267e26` mem-cache: Add write-triggered SRC inline refresh
6. `d244685c81` mem-cache: Add banked SRC data array with parallel refresh (session 3)

outer:
- `7263e91` Track restore_measure.py and kvm_checkpoint_sp.py as-is (pre-rework snapshot)
- `26fb15d` configs: Drop debug_drt_mode, add --drt_strict
- `ffe2a22` configs: Pass SRC retention params, add timing/inline flags
- `a192f1f` Add SRC directed retention tests and rework equivalence checks
- `acec9ea` tests: Build the retention test binary if missing
- `befe4d2`, `6d9e382` CLAUDE.md
- `a928f1b` Add SRC smoke results and the SRC DRT sweep tooling (session 2)
- `7d54123` SRC sweep analysis: lbm excluded, backdoor grid, stats reference (session 3)
- `19a99bb` SRC step 6: 8-bank refresh flags, tests, design doc, variant compare (session 3)

### Frozen binaries (`~/forgetting/bin/`)
- `gem5.fast.pre-rework`: the binary every earlier result (incl. the SRAM MPKI sweep) came from.
  gem5 `ac48641acd`, built 2026-09-27 12:45 (details in `gem5.fast.pre-rework.txt`). It needs the **old**
  configs, which have `debug_drt_mode`; a copy of those lives in the session scratchpad only, and the git
  snapshot is commit `7263e91`.
- `gem5.fast.step2` (built session 2), `gem5.fast.step3`, `gem5.fast.step4`, `gem5.fast.step5`, **`gem5.fast.step6`** (8-bank refresh, gem5 `d244685c81`, sha256 `4162fc45…`): the binary after each rework step.
- **`src_sweep/bin/gem5.fast`** (sha256 in `src_sweep/binary.txt`): the SRC sweep binary, built from the `src-rework` HEAD
  (`12c5267e26`) after a checkout round trip. Same source as `step5`, but not byte-identical (the link layout differs).
  `gem5/build/X86/gem5.fast` currently equals it.
- Build: `cd gem5 && scons build/X86/gem5.fast -j 40` (incremental, about 80 s). SCons replaces the file, so
  running simulations are unaffected, but **a sweep that launches jobs over time must use a frozen copy**,
  never `build/X86/gem5.fast` while you rebuild.

---

## 4. graphify (code-map tool)

- Installed this session: PyPI package `graphifyy` in a dedicated venv at `~/.local/share/graphify-venv`,
  with the command symlinked to `~/.local/bin/graphify`. System pip is PEP 668 "externally managed", so a venv is needed.
- Claude skill installed with `graphify install --platform claude`, giving `~/.claude/skills/graphify/SKILL.md`.
  It also created **`~/.claude/CLAUDE.md`** (global) telling Claude to use the skill on `/graphify`.
  The skill becomes available in sessions started after the install.
- Not run: `graphify claude install` (per-project CLAUDE.md directive + PreToolUse hook) and `graphify hook install` (git hooks).
- Used this session: `graphify extract <dir> --code-only` (local AST, no LLM/API key), then `graphify query "..."`.
  The graph was built on a **copy** of `gem5/src/mem/cache` + `configs/forgetting_cache` in the session scratchpad
  (not in the repo; `~/forgetting/graphify-out/` holds only an empty cache dir from an earlier attempt).
- **Limitation: graphify skips `.hh` files**, and all the SRC block/tag state lives in headers.
  Use grep for headers. Don't run graphify on all of `gem5/`, `spec/` or `checkpoints/` (huge).

---

## 5. The simulation pipeline (unchanged this session, verified)

- gem5 25.1, X86, `gem5/build/X86/gem5.fast`, standard library `SimpleBoard`, O3 CPU, SE mode,
  `DualChannelDDR4_2400`. The cache hierarchy is `ForgettingCache` in `configs/forgetting_cache/ForgettingL1DCache.py`
  (L1I, L1D = `ForgettingCacheBlock`, L2 on an L2XBar, all prefetchers disabled; the L1D replacement policy is LRURP).
- Frequency: `FREQ_LATENCIES` in `restore_measure.py`. `"3GHz"` (default): L1 4/4/1, L2 10/10/1 cycles
  (tag/data/response). `"1GHz"`: L1 2/2/1 (legacy; old results were at 1 GHz). Verified `clock=333` in `config.ini`.
- **12 SPEC CPU 2026 benchmarks, train inputs**: cactus_r, nest_r, roms_r, palm_r, flightdm_r, femflow_r,
  lbm_r, fotonik3d_r, sqlite_r, zstd_r, cpython_r, sealcrypto_r. Excluded: stockfish_r and marian_r (they spawn
  threads), gem5_r (syscalls), gmsh_r. flightdm uses `scripts/c3105.xml`; roms and palm read stdin.
  Binaries are static (`-O3 -march=x86-64 -mtune=generic`, config `spec/config/mytest.cfg`), in `spec_tests/<b>_{test,train}/`.
- **SimPoints:** valgrind BBV with 100M intervals → `tools/cluster_bbv.py` (maxk=8, dims=15, seed=1) →
  `spec_tests/<b>_train/simpoints.json` (`simpoint_list`, `weight_list`, `n_intervals`, coverage 1.0 for all).
  KVM checkpoints by `configs/forgetting_cache/kvm_checkpoint_sp.py` in `spec_checkpoints_sp/<b>/sp_<i>`,
  placed at `simpoint × 100M − 50M`. **89 checkpoints.**
- **`restore_measure.py`** restores on O3, warms up 50M instructions, then measures 100M. `stats.txt` has 2 dumps;
  **only the second counts**. O3 stops 1–2 instructions past 100M (macro-op), which is normal.
- `kvm_checkpoint_sp.py` and `restore_measure.py` each hold a copy of the `SPEC_BENCHMARKS` table plus `BENCH_ENV`.
  Keep them in sync (centralizing it is pending). `restore_measure.py` still lists stockfish_r and marian_r (they are excluded; harmless).

### restore_measure.py SRC flags (current)
`--drt_ticks N` (0 = SRAM) `--top_mru N` `--refresh_dirty` `--drt_strict` `--refresh_set_scan_cycles N` (default 1)
`--refresh_line_cycles N` (0 = 2 × data latency) `--no_inline_refresh` `--inline_refresh_on_read`
`--refresh_banks N` `--refresh_opp_age F` / `--retention_margin F` (unset = gem5 defaults 0.8 / 0.02; added session 4).
CPU (session 4, section 11): `--cpu_profile {default,alecto}` (default = everything before) and `--l1d_hit_cycles {4,5}` (alecto only).
`--l2_size`/`--l2_assoc` unset = the profile's L2 (default profile: 256KiB 16-way, as before; every sweep passes `--l2_size=1MiB`).
Prefetch session: `--l1d_prefetcher {none,stride}` `--pf_degree N` (default none).
`--debug_drt_mode` **no longer exists**; the user asked to remove it, and SRC always uses the former mode 1.
With `--drt_ticks 0`, the daemon flags are ignored and the cache is plain SRAM.

---

## 6. Completed: SRAM (DRT=0) MPKI sweep, formerly "knee sweep"

Everything is in **`~/forgetting/sram_mpki_sweep/`** (moved there at the user's request; `run_all.sh` points to it):
`run_sweep.sh` (was `knee_sweep.sh`), `analyze.py`, `sweep.log`, `runs/<bench>/sp_<i>/l1d_<N>k/{stats.txt,config.ini,run.log}`,
`results/results.csv`, `results/mpki_vs_size.png`, `results/ipc_vs_size.png` (IPC change vs 32 KiB, shared y-axis; `analyze.py` also prints an IPC table; added session 4, same runs, no re-simulation).

- The setup: L1D 16/32/48/64/96 KiB, always **64 sets** (assoc = size/4 → 4/8/12/16/24). L1I 32 KiB 8-way,
  L2 1 MiB 16-way, 3 GHz, no prefetchers. 89 SimPoints × 5 sizes = 445 runs, **all valid**, no errors or OOM kills.
- **Metrics (user's choice: demand-based, not MSHR-based, because they're easier to explain):**
  - MPKI = `l1dcache.demandMisses::total / simInsts × 1000`;
  - miss rate = demandMisses / demandAccesses;
  - L2 APKI and MPKI also from demand counts.
  
  The MSHR-based MPKI is kept only as a CSV column (`mpki_mshr`).
- **SimPoint weighting** (the user asked how this works): every SimPoint run is exactly 100M instructions, so the
  whole-program MPKI is Σwᵢ·MPKIᵢ, and `n_intervals` cancels out. Ratios are ratios of weighted totals, not averages of ratios:
  - miss rate = Σw·misses / Σw·accesses;
  - IPC = 1 / Σw·CPI;
  - DRAM BW = Σw·bytes / Σw·seconds.
  
  Weights are renormalized by coverage (1.0 everywhere).
- Plot titles show `ΔMPKI 32→48 = X (Y%)`, where improvement % = (MPKI₃₂ − MPKI₄₈)/MPKI₃₂.

Results (demand MPKI, SimPoint-weighted):

| bench | 32 KiB | 48 KiB | ΔMPKI (improvement) | ΔIPC 32→48 |
|---|---|---|---|---|
| palm_r | 40.72 | 32.02 | −8.70 (21.4%) | +0.33% |
| cactus_r | 111.42 | 104.55 | −6.87 (6.2%) | +0.01% |
| femflow_r | 48.87 | 43.84 | −5.03 (10.3%) | +0.02% |
| roms_r | 103.02 | 99.01 | −4.01 (3.9%) | +0.04% |
| cpython_r | 2.76 | 0.15 | −2.61 (94.5%) | +0.28% |
| sqlite_r | 15.77 | 13.54 | −2.23 (14.1%) | +0.27% |
| fotonik3d_r | 120.23 | 118.04 | −2.19 (1.8%) | −0.01% |
| flightdm_r | 42.28 | 40.31 | −1.96 (4.6%) | +0.24% |
| zstd_r | 16.34 | 15.78 | −0.56 | +0.06% |
| nest_r | 160.41 | 160.36 | −0.05 | +0.02% |
| sealcrypto_r | 7.96 | 7.89 | −0.06 | 0.00% |
| lbm_r | 61.20 | 61.20 | 0.00 | +0.05% |

**Groups decided by the user:**
- **Targets:** palm, flightdm, femflow, cactus, fotonik3d, cpython, sqlite, **roms**.
- **Controls:** lbm, nest.
- **Out:** zstd, sealcrypto.

`ROLES` in `sram_mpki_sweep/analyze.py` now uses this grouping (target / control / excluded); `src_sweep/analyze.py` imports it.

**Key finding (discussed with the user):** IPC is flat even at 3 GHz. Even 16→96 KiB gives at most +1.5% IPC,
because O3 plus a 10-cycle L2 hides L1 misses. So an IPC-based pitch is weak at this design point.
Directions raised, for the user and advisor to decide:
1. Reframe as same performance at lower area/leakage/energy (L2 traffic drops 15–22% on palm and sqlite; needs CACTI/McPAT).
2. Check whether the setup hides the effect (a 10-cycle L2 at 3 GHz is optimistic, real cores have 14–17; LQ/SQ = 32).
3. SRC at the L2 (an `l2_forgetting/` directory exists).

---

## 7. The SRC simulator rework (the main work of this session)

### 7.1 Why
The handoff tasks (write granularity, inline refresh, clock-correct thresholds, validation) plus the user's
requirements:
- all SRC code **separated and contained**, so DRT=0 runs exactly stock gem5;
- the refresh daemon must **cost time** (a per-set time, still unknown, so it's a parameter);
- write-near-expiry must trigger an **immediate refresh with a stall**;
- **keep every backdoor** (especially the lazy writeback fallback) but **track each one**, hopefully showing they are ~0;
- remove `debug_drt_mode` entirely (always mode 1);
- delete the shadow conflict-miss cache;
- work in a branch.

### 7.2 Audit of the pre-rework fork (vs upstream `7a2b0e413d`)
Leaks into DRT=0, **all fixed in commit 1**:
- **L1:** the `writeThrough()` guard was swapped between the WritebackDirty and WriteClean branches of `BaseCache::access()`.
- **L2:** a shadow fully-associative LRU (conflict-miss tracking) ran on every access in every cache. Deleted, with `conflictMisses`.
- **L3:** `incHitCount` had been moved after `satisfyRequest`. Restored, together with the upstream `incHit/MissCount(pkt)` signatures.
- **L4:** `nozero|nonan` were removed from the hit/miss/access stat flags. **Kept on purpose** (it only affects output).
- **L5:** a "TESTING PARTIAL FORGETTING — REMOVE" VA-range hack in `handleFill`, plus the unused `isForgettingBlk`. Deleted.
- The `dirtyReadHits`/`dirtyWriteHits` stats were deleted.
- The license header of `tags/base_set_assoc.cc` had been deleted by the fork; it is restored.

Backdoors (expired data surviving), **all now counted** (commit 3). Each is kept as a fallback:
- **B1:** a read of an expired dirty block does a lazy writeback of dead data to L2, then invalidate, then miss → `lazyWritebacksRead`.
- **B2:** an expired block with an MSHR or write-buffer entry pending is served as a hit → `expiredInflightHits`.
- **B3:** writes to expired blocks used to **hit silently** (the check was `isRead()` only). They now take the B1 path → `lazyWritebacksWrite`.
- **B4:** an expired dirty victim is written back on eviction → `expiredDirtyEvictions`. Clean ones go to `expiredCleanEvictions`.
- **B5:** a functional access (SE syscalls) uses expired data → `expiredFunctional`.
- **B6:** a snoop uses expired data → `expiredSnoops`.
- **B7:** `debug_drt_mode=0`, the count-only mode. **Removed** along with the param.
- **B8 (found later):** the daemon's dirty loop refreshed already-expired blocks, reviving lost data → `daemonRevivedDirty`.
- Every dirty-expired detection anywhere also increments **`invariantViolations`**; `drt_strict=True` panics instead.

Other bugs fixed:
- An expired access skipped `tags->accessBlock` and so missed with zero tag latency. It now pays the tag lookup.
- `isExpired()` overflowed on `MaxTick + drt` for never-charged blocks.
- `getNTopMRU` `static_pointer_cast` the replacement data to `MRU::MRUReplData` while the L1D uses LRURP (undefined
  behavior that happened to work). It also didn't skip invalid blocks. It's replaced by the manager's own `lastTouchTick`,
  and the `mru_rp.hh` protected→public change is reverted.
- A fill into an already-present block writes the full line but didn't recharge it. It now does.

Already correct before the rework (confirmed in code):
- only fills and daemon refreshes recharged (the store/AMO/writeback resets were commented out), so handoff Task 2 was essentially done;
- `drt_cycles` already used the runtime `clockPeriod()`, so handoff Task 4 needed nothing.

### 7.3 Design now in the code
- **`gem5/src/mem/cache/retention/retention_manager.{hh,cc}`** (+ `SConscript`) holds **all** SRC state, logic, the daemon event,
  and the stats (group `<cache>.retention.*`, e.g. `board.cache_hierarchy.l1dcache.retention.forceRefresh`).
  `BaseCache` holds `std::unique_ptr<RetentionManager> retention`, created **only if `drt > 0`** (`friend class RetentionManager`).
- Hooks, each `if (retention) ...`:

  | Hook | Where | What it does |
  |---|---|---|
  | `expireOnAccess(pkt, writebacks)` | `BaseCache::access()`, before `tags->accessBlock` | expiry for reads and writes; records `lastAccessTick` |
  | `onAccessHit(blk)` | after `accessBlock` | updates `lastTouchTick`, `refreshedBlockUtility` |
  | `hitDelay(pkt, blk)` | added to `lat` in the hit branch of `access()` | waits for data-array occupancy, plus the inline refresh |
  | `onFullLineWrite(blk)` | `allocateBlock` and `handleFill` (data fills, not `tempBlock`) | full-line recharge |
  | `onEvict(blk)` | `BaseCache::evictBlock(blk, writebacks)` | eviction accounting |
  | `onFunctional(blk)` | `BaseCache::functionalAccess` | functional-access accounting |
  | `onSnoop(blk)` | `Cache::handleSnoop` (`cache.cc`) | snoop accounting |
  | `startup()` | `BaseCache::startup()` | computes the guarantee, starts the daemon |

- `CacheBlk` retention fields: `fullChargeTick` (was `lastUpdatedTick`), `lastTouchTick`, `wasOppRefreshed`.
- Tags keep `isForgetting()`, `isExpired()`, `getDRT()`, `getSetBlks()` and `getNumSets()` (`tags/base.hh`, `tags/base_set_assoc.hh`).
- **Params** (`src/mem/cache/Cache.py`, BaseCache):

  | Param | Default | Meaning |
  |---|---|---|
  | `drt` (ticks) | 0 | data retention time; 0 = SRAM |
  | `top_mru` | 0 | top-MRU blocks per set the daemon keeps alive |
  | `refresh_dirty_daemon` | False | the daemon keeps dirty blocks alive |
  | `refresh_set_scan_cycles` | 1 | time to scan one set's tags (**unknown, to be swept**) |
  | `refresh_line_cycles` | 0 (= 2 × data_latency) | data-array occupancy of one full-line refresh |
  | `refresh_banks` | 1 | data-array banks (set s in bank s mod B); a refresh occupies only its bank, banks refresh in parallel. **8 is the design point** (step 6) |
  | `refresh_opp_age` | 0.8 | age (fraction of DRT) from which idle-time refreshes start |
  | `retention_margin` | 0.02 | safety margin, fraction of DRT |
  | `inline_refresh` | True | store hits near expiry recharge the line |
  | `inline_refresh_on_read` | False | read hits near expiry also recharge |
  | `inline_refresh_cycles` | 0 (= data_latency) | extra latency of an inline refresh |
  | `drt_strict` | False | panic on an invariant violation instead of counting |

- **Timing:**
  - A daemon step handles one set: the scan takes `scan` cycles, then each refresh occupies the data array for
    `line` cycles, serialized through `dataBusyUntil`. The next set is visited when this step's refreshes finish.
  - A hit that finds the data array busy waits: `refreshStallCycles`.
  - Opportunistic refreshes need an idle data array: no demand access this cycle and no refresh in progress.
- **Banks (step 6; full design, proof and metadata ledger in `docs/src_refresh_design.md`):**
  one central scanner (no new per-line metadata; per-bank sub-controllers were rejected because they need 8 metadata read ports),
  per-bank busy/idle, and `T_sweep = ceil(S/B) × (B·scan + k_max·line)`. At B = 8, 10 µs: T_sweep 832 cycles, T_guard 1440, force at 95.2% (was 77.3%).
  B = 1 is bit-exact with steps 5 and earlier.
- **The one guarantee** (formula shown for B = 1):
  - T_sweep = numSets × (scan + k_max × line) cycles, with k_max = assoc if dirty refresh is on, else top_mru.
  - T_guard = T_sweep + line + margin × DRT.
  - **Daemon:** force-refresh a block when its remaining life < T_guard.
  - **Store hit:** if remaining < T_guard, do an **inline refresh** (+`inline_refresh_cycles` latency, plus one line of occupancy).
    If remaining < the inline read time, it's too late: treated as expired (`inlineTooLate`).
  - **Startup `fatal` if T_guard ≥ DRT.**
  - With no daemon, T_guard = line + margin × DRT.
- **All retention stats** (full meaning of each, what the simulator does, what hardware would do, sweep values:
  **`docs/retention_stats.md`**):
  - misses and write-backs: `retentionMisses`, `lazyWritebacks{,Read,Write}`, `expiredInflightHits`, `expiredDirtyEvictions`,
    `expiredCleanEvictions`, `expiredFunctional`, `expiredSnoops`, `daemonRevivedDirty`, `invariantViolations`;
  - refreshes: `oppRefresh`, `forceRefresh`, `totalRefreshes` (each = 1 line read + 1 line write, for the energy model), `ageAtForceRefresh`;
  - stalls and daemon: `refreshStalledHits`, `refreshStallCycles`, `daemonSweepCycles` (histogram), `tSweepCycles`, `tGuardCycles`;
  - inline: `refreshInlineWrite`, `refreshInlineRead`, `ageAtInlineRefresh`, `cleanToDirtyInDanger`, `inlineRefreshCycles`, `inlineTooLate`;
  - other: `expiredHitPot`, `refreshedBlockUtility`.
- `git -C gem5 diff 7a2b0e413d -- src/mem/cache/base.cc base.hh cache.cc` should show **only** the `retention`
  hooks, the member and friend declaration, `startup()`, and the L4 flag change.

### 7.4 Verification done (everything passed)
Tools: `~/forgetting/src_rework_verify.sh <step>` (env `NEW=<binary>`, `OLDCFG=<old restore_measure.py>`).
It runs palm sp_1, sqlite sp_7 and lbm sp_4 at DRT=0 (32 KiB 8-way), plus palm sp_1 SRC (48 KiB 12-way, DRT 10 µs, top_mru 4,
refresh_dirty), into `src_rework_verify/<step>/`. Compare with `src_rework_verify/compare_stats.py OLD NEW`
(second dump; ignores `host*`; maps moved retention stats).
- **DRT=0 equals the pre-rework SRAM sweep, bit-exact, after steps 2, 3, 4 and 5** (0 differing stats out of 2033–2304;
  the only differences are removed stats).
- **Step 2 (refactor) SRC equals the old binary with its old config:** 0 differences out of 2173 stats, including IPC.
- **Step 3 SRC equals step 2** in all common stats; the new counters are all 0 (`expiredCleanEvictions` = 680).
- **Step 4 SRC:** IPC 2.4799 → 2.4786 (−0.05%), 5765 forced refreshes, 0 opportunistic (see 9.3), 20,690 stall cycles,
  0 violations. Measured sweep: 64 cycles on average vs T_sweep = 6208 (see 9.3).
- **Step 5 SRC equals step 4** on palm sp_1 (no store landed in the danger window).
- **Directed tests:** `tests/retention/run_tests.sh [binary]` gives **17/17 PASS** on `gem5.fast.step5` (about 85 s, 6 cases in parallel).
  The program is `store_loop.c` (stores to one line in a loop, 3M iterations; SE mode from start, config `tests/retention/run_test.py`):
  - no refresh: the looped line expires every DRT (431 lazy writebacks vs simSeconds/DRT = 408);
  - strict panics on the first lost dirty block;
  - inline-only keeps the line alive (423 inline refreshes; write lazy writebacks 431 → 23);
  - daemon + strict and daemon + inline + strict: no panic, 0 violations;
  - DRT 2 µs < T_guard: refused at startup.
  
  The strict case's "Aborted (core dumped)" is expected; no core file is kept.

---

## 8. Smoke run: DRT = 5 µs, strict, all 10 benchmarks (sp_0, 48 KiB 12-way, top_mru 4, refresh_dirty, inline on)
Output in `src_rework_verify/step5_smoke/<bench>/`. Binary `bin/gem5.fast.step5`.
9/10 finished (lbm still running at handoff): **0 invariant violations, 0 lazy writebacks, no panic**. The guarantee holds on real workloads.
**But the cost is large:**

| bench | IPC SRAM 48 KiB | IPC SRC 48 KiB @ 5 µs | ΔIPC | forced refreshes | inline | stall cycles |
|---|---|---|---|---|---|---|
| cactus | 0.518 | 0.518 | 0.0% | 3.0M | 10K | 29M |
| cpython | 1.170 | 0.922 | −21.2% | 9.0M | 38K | 141M |
| femflow | 0.815 | 0.541 | −33.6% | 11.7M | 46K | 141M |
| flightdm | 0.868 | 0.746 | −14.0% | 8.7M | 28K | 101M |
| fotonik3d | 0.404 | 0.402 | −0.5% | 12.4M | 16K | 112M |
| nest | 1.137 | 0.832 | −26.8% | 7.7M | 35K | 98M |
| palm | 2.432 | 2.431 | 0.0% | 0.22M | 0.7K | 3.5M |
| sqlite | 0.703 | 0.626 | −10.9% | 5.7M | 33K | 55M |
| roms | 0.542 | 0.482 | −11.1% | 11.7M | 11K | 160M |

Why: at DRT = 5 µs, T_guard ≈ 2.27 µs, so blocks are force-refreshed from about **55% of DRT**. The forced
refreshes include **clean top-MRU blocks** (4 per set, a performance choice, not a correctness need). Each refresh
occupies the data array for 8 cycles, and hits stall behind it.

---

## 9. State at handoff (sessions 2–3; session 4 is section 11)

### 9.0a Session 3, later: step 6 (8 banks), user rules
- **User rules (saved in memory):**
  - **optimize for DRT = 10 µs only**;
  - **no untracked metadata**: every mechanism lists its bits and ports in the ledger in `docs/src_refresh_design.md`.
    The user rejected a 1-bit "touched" filter and per-bank sub-controllers for this reason.
  - Use **J = 20** while someone else shares the server (superseded in session 4: size J from RAM, keep ≥ 10 GiB free; see §2).
- **Step 6 verified:**
  - DRT = 0 equals the SRAM sweep, bit-exact (palm sp_1, sqlite sp_7, lbm sp_4);
  - B = 1 equals the old 10 µs sweep (palm sp_1, cpython sp_0; only the 3 new bank stats are added);
  - directed tests 29/29 (4 new bank cases).
- **Done:** the 8-bank sweep, launched 2026-09-28 19:58:
  - all 11 benchmarks (no lbm) at 10 µs, `--top_mru=4 --refresh_dirty --refresh_banks=8`;
  - output in `src_sweep/runs_b8`, log `src_sweep/runs_b8/sweep.log`, 81 runs.
  - Afterwards run:
    - `SRC_DRTS=10 SRC_EXCLUDE=lbm_r SRC_RUNS=$PWD/src_sweep/runs_b8 SRC_RESULTS=$PWD/src_sweep/results_b8 venv/bin/python src_sweep/analyze.py`;
    - then `venv/bin/python src_sweep/compare_variants.py b1=src_sweep/results b8=src_sweep/results_b8`.
- **8-bank sweep RESULT** (finished 21:57, 81/81 runs, 0 errors; `src_sweep/results_b8/`, `compare_10us.png`):

  | | 1 bank | 8 banks |
  |---|---|---|
  | forced refreshes | 100% of refreshes | ~0: **98–100% of refreshes are opportunistic** |
  | stall cycles / kinst | 88–649 | 10–79 (−85 to −92%) |

  IPC vs SRAM 32 KiB at 10 µs:

  | bench | 1 bank → 8 banks | bench | 1 bank → 8 banks |
  |---|---|---|---|
  | femflow | −14.3% → **−1.8%** | flightdm | −1.0% → 0.0% |
  | zstd | −2.8% → −0.2% | sealcrypto | −1.2% → −0.1% |
  | sqlite | −2.4% → −0.2% | palm | −0.1% → **+0.2%** |
  | cpython | −1.7% → 0.0% | the rest | ≈ 0 |
  | roms | −1.3% → −0.1% | | |

  - Gain kept (MSHR) is unchanged within ±4 points.
  - Backdoors: 0 lazy writebacks, 0 violations, 0 in-flight hits (snoops 171 and functional 325, all clean).
  - The femflow demand-MPKI "kept > 100%" artifact disappeared (110% → 100%), which confirms it was timing-induced.
  - What remains is femflow −1.8%. It has the most refreshes (46/kinst) and 79 stall cycles/kinst, from opportunistic
    refreshes that start in an idle cycle and then block the next hit to the same bank. The zero-metadata next lever is
    demand-priority (abortable) opportunistic refresh.
- **Not modeled yet** (ledger): the per-line age counter. The simulator uses exact 64-bit ticks, so it assumes perfect
  age knowledge. The future parameter would be `retention_age_bits`.
- **Deferred ideas** (the user chose "banks only" for now):
  - clean top-MRU lines refreshed opportunistically only (no new metadata);
  - demand-priority opportunistic refresh;
  - cleaning cold dirty lines instead of refreshing them;
  - an opp-age sweep.

### 9.0 Session 3 (2026-09-28): SRC sweep analyzed
- **lbm dropped for now** (user's call): its 3 slowest runs were killed; 24 finished runs remain in
  `src_sweep/runs/lbm_r`. Analyze with `SRC_EXCLUDE=lbm_r venv/bin/python src_sweep/analyze.py`.
- New plots: `ipc_vs_sram32.png` (symlog axis, values on bars), `mpki_vs_drt.png` (gain kept % at every dot,
  definition on the figure), `backdoors.png` (raw counts of every backdoor counter, plus all L1D writebacks for scale).
- **Result, 11 benchmarks, top_mru 4:**
  - 0 lazy writebacks and 0 invariant violations everywhere;
  - gain kept at 20 us is 79-99%;
  - IPC is always at or below SRAM 32 KiB, from 0 to -41% (femflow at 5 us).
- **Why IPC falls while MPKI improves:**
  - an avoided L1 miss is worth only 0.04-2.8 cycles on this core; SRAM 48 KiB itself gives at most +0.33% IPC;
  - the loss is refresh stalls (correlation 0.84); the forgetting itself costs about 1 cycle per kinst;
  - demand MPKI "gain kept" above 100% (femflow, roms at 5 us) is a timing artifact: fewer secondary misses
    because the core is slowed. The MSHR-based MPKI shows none.
- **top_mru 0 test** (palm, cpython only; `src_sweep/runs_topmru0`, `results_topmru0`):
  - IPC recovers only about half (cpython at 5 us: -10.6% -> -5.2%);
  - refreshes drop only 30-40%: most refreshes are dirty lines forced at about 55% of DRT, set by the T_sweep bound;
  - the MPKI benefit collapses (cpython at 5 us: MPKI 7.9, above SRAM 32 KiB's 2.76; L2 APKI up 64%).

  **Verdict: not worth a full rerun.** The recommended next step is §9.3-1 (a tighter bound) and/or
  §9.3-2 (clean MRU refreshed only opportunistically). The user has not decided yet.
- `run_sweep.sh` now takes `OUT=` and `SRC_FLAGS=` from the environment (defaults unchanged).
  `analyze.py` takes `SRC_EXCLUDE=`. Both are uncommitted.

### 9.1 In flight (check these first)
- **The SRC DRT sweep** (launched 2026-09-28 12:20, `nohup setsid`, so it survives the session):
  `src_sweep/run_sweep.sh`, log `src_sweep/sweep.log`, output `src_sweep/runs/<b>/sp_<i>/drt_<N>us/`.
  - Runs all 12 benchmarks × 89 SimPoints × DRT 10, 5, 20 µs = 267 runs, J=25, ETA about 3–4 h.
  - Uses SRC 48 KiB 12-way, `--top_mru=4 --refresh_dirty`, **non-strict** (violations counted), 3 GHz.
  - It is resumable: rerunning it skips finished runs.
  - Check: `grep -c launch src_sweep/sweep.log`, then `grep -L "measurement complete" src_sweep/runs/*/sp_*/drt_*/run.log`.
- Afterwards: `venv/bin/python src_sweep/analyze.py` writes `results/results.csv`, the tables, `mpki_vs_drt.png`,
  `ipc_vs_sram32.png` and `refresh_overhead.png`. The SRAM 32/48 KiB points are read from `sram_mpki_sweep/runs`
  (the user agreed to reuse them).
- **Push is blocked:** the server has no GitHub credentials (no `gh auth`, no SSH key). The user authorized pushing
  both `src-rework` branches (no merge into `stable`/`master` yet); push once auth exists.

### 9.1b Session 2 checks (before the sweep)
- Directed tests 17/17 PASS on the HEAD build.
- 10 µs smoke (`src_rework_verify/step5_smoke_10us/`, strict; table in `src_rework_verify/smoke_results.txt`):
  - 9/10 finished (lbm was stopped at the user's request) with 0 violations, lazy writebacks, revived or dirty-expired blocks;
  - the force age is 0.77–0.78 (T_guard 77.3%);
  - IPC vs SRAM 32 KiB ranges from 0 to −12% (femflow −11.7%, nest −7.3%, sqlite −4.2%, cpython −3.1%, roms −2.5%, flightdm −2.6%);
  - MPKI sits between SRAM 32 and 48 KiB (roms slightly below 48 KiB, nest slightly above 32 KiB).
  
  The user judged the results logical and waived the bit-exact SRC comparison.
- The DRT=0 wide check `src_rework_verify/verify_drt0_all.sh` + `show_equivalence.py` was written but **not run** (waived).

### 9.2 Not done yet
- Nothing is pushed yet (auth missing, see 9.1). No merge of `src-rework` into `stable`/`master` until the user says so.
- The old configs (`ForgettingL1ICache.py`, `ForgettingL2Cache.py`, `system*.py`, `run_mibench_cmp.py`) still pass
  `debug_drt_mode` and will **fail** on the new binary. Update or retire them; ask the user which are still used.
- Handoff "later/optional" items not started:
  - big-core point (48 KiB SRAM vs 72 KiB SRC, 18-way);
  - a mid-size core row in FREQ_LATENCIES;
  - prefetcher ablation;
  - frequency robustness;
  - CRLF normalization and `.gitattributes`;
  - centralizing the benchmark table (duplicated in about 8 files).
- Optional handoff items not done: per-granule charge ticks (stats only); poisoning expired dirty data plus
  SPEC `compare.cmd` output verification.

### 9.3 Open design questions for the user and advisor (the next decision)
1. **The T_sweep bound is about 100× pessimistic** (it assumes every way of every set needs a refresh each sweep; the measured sweep is 64 cycles vs 6208).
   It forces refreshes early (~55–77% of DRT) and refuses DRT < ~2.3 µs. Options:
   - a tighter but still sound bound (e.g. the per-set count of dirty and top-MRU blocks, or a cap on refreshes per step);
   - scale the scan with the set count;
   - accept it and pick DRTs well above T_guard.
2. **Should clean top-MRU blocks be force-refreshed?** They are not needed for correctness. Making MRU refresh opportunistic-only
   would cut most of the refresh traffic and stall cycles.
3. **`refresh_opp_age` (0.8) is later than the force point** at DRT ≤ ~10 µs, so opportunistic refreshes never happen there.
4. Realistic values for `refresh_set_scan_cycles`, `refresh_line_cycles` and `inline_refresh_cycles` (GC-eDRAM circuit numbers).
5. The DRT grid: at 10 µs palm has 0 retention misses (lines are replaced faster than they expire). The interesting range is
   narrow and sits right where the guarantee bound starts to bite.
6. The thesis framing given flat IPC (section 6 directions).

### 9.4 Next steps (after 9.3 is decided)
1. Tune the refresh policy and bound (9.3 items 1–3), rebuild, rerun `tests/retention/run_tests.sh` and the DRT=0
   equivalence (`NEW=... ./src_rework_verify.sh <step>`, then compare with `sram_mpki_sweep/runs/...l1d_32k`).
2. **SRC sweep** (handoff Task 6). **Running since session 2 (see 9.1)**, with the current policy at DRT 5/10/20 µs on all 12 benchmarks:
   - **configurations:** the 8 targets plus lbm and nest; SRC 48 KiB 12-way at several DRTs, compared with the 32 KiB 8-way
     and 48 KiB 12-way SRAM baselines (already in `sram_mpki_sweep/runs`, same configuration, don't rerun);
   - **report:** IPC, ΔMPKI (demand-based), L2 APKI, refresh/inline/lazy-writeback counts, retention-miss fraction,
     and DRAM bandwidth for the controls;
   - **mechanics:** use a **frozen binary copy**, J ≤ 25, and model a sweep script on `sram_mpki_sweep/run_sweep.sh`.
3. Also sweep `refresh_set_scan_cycles` (unknown per-set time).

---

## 10. Memory and other context files
- Claude memory: `~/.claude/projects/-home-ilay-forgetting/memory/` (`MEMORY.md` index; `git-commit-identity.md`, `src-rework-branch.md`).
- Global `~/.claude/CLAUDE.md`: the graphify skill trigger.
- The original handoff document (tasks 1–6, gotchas) was pasted into session 1. Its content is folded into this file;
  any details that were uncertain in it have been checked against the code here.

---

## 11. Session 4 (2026-09-30): Alecto-style core and the A / C0 / C1 sweep

The user's handoff for this session: a realistic core instead of the gem5 O3 defaults (8-wide, ROB 192,
LQ/SQ 32/32; several benchmarks stall on a full LSQ). **Rule: use Alecto's Table I values; add no
structure Alecto doesn't model and invent no value it doesn't give.** `default` must stay bit-exact.

State of the repos: both are on branch **`src-prefetch`** (made by the prefetch session from `src-rework`,
see `claude docs/prefetcher_integration_plan.md`). **Nothing of the prefetch or the Alecto work is committed.**
The gem5 tree equals `bin/gem5.fast.prefetch` (source = `d244685c81` + `bin/gem5.fast.prefetch.gem5.patch`).
The Alecto profile needed **no C++ change**. Don't touch `prefetcher_test/`.

### 11.1 The `alecto` profile (`configs/forgetting_cache/cpu_profiles.py`)
Source: Li, Zhang, Ren, Xie, "Integrating Prefetcher Selection with Dynamic Request Allocation Improves
Prefetching Efficiency" (**Alecto**), HPCA 2025, **Table I** (https://arxiv.org/abs/2503.19390); Skylake-like,
"almost consistent with" Bandit (MICRO 2023). Table I checked against the paper this session.

| Parameter | gem5 | alecto | default (before) |
|---|---|---|---|
| ROB / IQ | `numROBEntries` / `instQueues[0].numEntries` | 256 / 256 | 192 / 64 |
| LQ / SQ | `LQEntries` / `SQEntries` | 72 / 56 | 32 / 32 |
| fetch / decode / rename / dispatch / issue / wb / commit | `*Width` | 6 / 6 / **6** / **6** / 8 / 8 / 4 | 8 all |
| L1I | | 32 KiB 8-way, 16 MSHRs, 4-cycle load-to-use | 32 KiB 8-way |
| L1D, 32 KiB configs | | 32 KiB 8-way, 16 MSHRs, **4** cycles | |
| L1D, 48 KiB configs | `--l1d_hit_cycles 5` | 48 KiB 12-way, 16 MSHRs, **5** cycles | |
| L2 | | **256 KiB 8-way, 32 MSHRs, 15 cycles** | sweeps used **1 MiB** 16-way, 20 MSHRs |
| L3 | | none | none |
| DRAM | | DualChannelDDR4_2400 (unchanged) | same |
| Prefetchers | | off | off |

**Deviations from Alecto (report these):**
- **No L3.** Table I has a shared L3 (2 MB/core, 16-way, 35 cycles). The user decided not to model it.
- **DRAM: dual channel kept.** Alecto's single-core runs use a single channel (Table I "SC"). Not changed; ask the user before changing it.
- **Rename / dispatch width 6**: not in Table I, set to the decode width.
- **Physical registers, branch predictor: gem5 defaults** (256 int / 256 FP / 256 vec regs; `BranchPredictor` with `TournamentBP`). Not in Table I.
- **TLBs**: Table I has 64-entry L1 TLBs and a 2048-entry L2 TLB. In SE mode gem5 X86 translation is untimed, as in every earlier run.
- **48 KiB L1D at 5 cycles** (both SRAM and SRC 48 KiB): the standard L1D of Berti (MICRO 2022, "L1D 48KB 12-way, 5-cycle";
  also IPCP ISCA'20, CLIP MICRO'23, Secure Prefetching MICRO'24, Gaze and MOKA HPCA'25) and Intel Ice Lake client
  (Optimization Reference Manual Vol. 1, #248966-050US, Table 2-9: 48 KB, 5 cycles; Intel lists 8 ways, we keep 12 for the 64-set geometry).
- The handoff listed the "current" L2 as 256 KB 16-way; the earlier sweeps actually used **1 MiB** 16-way (`--l2_size=1MiB`).
  So A/C0/C1 differ from all earlier results in the L2 size as well as the core.
- The L1I uses the same latency parameters as the 4-cycle L1D (not measured separately; no fetch-side chase).

### 11.2 Latency calibration (`alecto_sweep/calib/`)
- `chase.c`: random single-cycle (Sattolo) linked list, one pointer per 64 B line, 2 warmup passes, then N dependent
  `mov (%r),%r` loads (8 per loop iteration). `run_chase.py`: SE mode from start, same board / hierarchy / core as
  `restore_measure.py` (both import `cpu_profiles.py`). `calibrate.py`: runs N1 and N2 loads and reports
  (cycles₂ − cycles₁)/(N₂ − N₁), so setup and warmup cancel. Footprints 16 KiB (L1), 128 KiB (L2; cyclic order beats LRU, so 0 L1 hits), 8 MiB (DRAM).
- Measured rule: **load-to-use = L1 tag + 1**, and an L2 hit = L1 tag + max(L2 tag, L2 data) + 4 (xbar and response).
- **Final values (cycles at 3 GHz, tag/data/response):**

  | | L1D | L1I | L2 | measured L1 / L2 / DRAM |
  |---|---|---|---|---|
  | alecto, 32 KiB (and 48 KiB), hit 4 | 3/3/1 | 3/3/1 | 8/8/1 | **4 / 15 / 210** |
  | alecto, 48 KiB, `--l1d_hit_cycles 5` | 4/4/1 | 3/3/1 | 8/8/1 | **5 / 16 / 211** |
  | default (before), 32 KiB, L2 1 MiB | 4/4/1 | 4/4/1 | 10/10/1 | **5 / 18 / 213** |

  - The 5-cycle L1D also makes an L2 hit 16 cycles, because gem5 forwards a miss after the tag latency; with ChampSim-style additive latencies (Berti) it's the same.
  - The old default machine's "4-cycle L1" was really 5 cycles load-to-use, and its L2 was 18.
  - CSVs in `alecto_sweep/calib/results/`.

### 11.3 SRC refresh timing for C1 (user decision, 2026-09-30)
- **`refresh_line_cycles = 2`: a line refresh occupies its data-array bank for 2 cycles, 1 cycle for the read side and 1 for the write side.**
  The user chose a small non-zero number (2 for now) instead of the old default 2 × data latency (= 8 cycles).
- **Guards: force refresh from ~95% of DRT, opportunistic from ~80%.** With line = 2 and the old 2% margin, force would start at 97.1%,
  so the margin is raised: **`retention_margin = 0.0414`**, **`refresh_opp_age = 0.8`** (both passed explicitly; gem5 defaults unchanged).
- Resulting (DRT 10 µs = 30,030 cycles, 64 sets, 8 banks, k_max = 12, scan 1):
  T_sweep = 8 × (8 × 1 + 12 × 2) = **256 cycles** (85,248 ticks), T_guard = 256 + 2 + 0.0414 × DRT = **1501.2 cycles** (499,914 ticks),
  **force from 95.0% of DRT** (startup `info:` line). Before (line 8, margin 2%): T_sweep 832, T_guard 1440.6, 95.2%.
- `inline_refresh_cycles` stays at its default (= data latency = 4 for the 5-cycle L1D).

### 11.4 Sweep (`alecto_sweep/`)
| ID | Config | Flags (plus `--cpu_profile=alecto --freq=3GHz`) |
|---|---|---|
| A | SRAM 32 KiB 8-way, 4 cycles (baseline) | `--l1d_size=32KiB --l1d_assoc=8` |
| C0 | SRAM 48 KiB 12-way, 5 cycles | `--l1d_size=48KiB --l1d_assoc=12 --l1d_hit_cycles=5` |
| C1 | SRC 48 KiB 12-way, 5 cycles, 10 µs, 8 banks (headline, iso-area with A) | `--l1d_size=48KiB --l1d_assoc=12 --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=4 --refresh_dirty --refresh_banks=8 --refresh_line_cycles=2 --retention_margin=0.0414 --refresh_opp_age=0.8` |

One full C1 command line:
```
alecto_sweep/bin/gem5.fast -d OUT alecto_sweep/configs/restore_measure.py --bench_type=palm_r --sample_idx=1 \
  --checkpoint_dir=spec_checkpoints_sp/palm_r --cpu_profile=alecto --freq=3GHz --l1d_size=48KiB --l1d_assoc=12 \
  --l1d_hit_cycles=5 --drt_ticks=10000000 --top_mru=4 --refresh_dirty --refresh_banks=8 \
  --refresh_line_cycles=2 --retention_margin=0.0414 --refresh_opp_age=0.8
```
- 11 benchmarks (lbm excluded), all SimPoints, existing KVM checkpoints, no GAP, non-strict (dirty loss counted).
  `top_mru 4` because the prefetch session concluded "keep top_mru 4".
- `alecto_sweep/run_sweep.sh`: J = 30 (default), `RESERVE_GB=10` guard (launches only while MemAvailable ≥ 10 + 4.5 GiB), resumable,
  restartable while running (counts its gem5 processes, skips runs in progress), A and C1 interleaved first, then C0. Frozen binary
  `alecto_sweep/bin/gem5.fast` (= `bin/gem5.fast.prefetch`, sha256 in `alecto_sweep/binary.txt`), frozen configs copied
  into `alecto_sweep/configs/` on the first launch. Output `alecto_sweep/{A,C0,C1}/runs/<bench>/sp_<i>/`, log `alecto_sweep/sweep.log`.
- Analysis: `venv/bin/python alecto_sweep/analyze.py` writes `alecto_sweep/results/{results.csv,report.md}`
  (IPC, demand MPKI, L2 APKI vs A and C0, refreshes forced/opp, stalls, retention misses, backdoors; geomeans; flags C0 vs A > 1% IPC).

### 11.5 Verification before the sweep (all passed; `alecto_sweep/verify.sh`, `smoke_c1.sh`, output `alecto_sweep/verify/`)
- Directed retention tests on `alecto_sweep/bin/gem5.fast`: **29/29 PASS** (`verify/directed_tests.log`).
- `--cpu_profile default` vs the SRAM sweep (`compare_stats.py`, second dump): **0 differing stats** on palm sp_1 (2166 common),
  sqlite sp_7 (2304), lbm sp_4 (2033); the 33 "only old" are the stats removed in the rework, as before.
  Default-profile SRC 8 banks palm sp_1 vs `src_sweep/runs_b8`: 0 of 2456 differ (12 new prefetch-session stats).
- C1 smoke, palm sp_1 with the exact C1 flags, counting and `--drt_strict`: completes, no panic, **every dirty-loss counter 0**,
  0 retention misses, 0 forced / 32,779 opportunistic refreshes, 491 stall cycles, tSweepCycles 256, tGuardCycles 1501.2, IPC 0.752
  (the old core with 1 MiB L2 gave 2.43 on this SimPoint: palm sp_1 streams, and the L2 is now 256 KiB).
- `config.ini` proof (ROB/IQ 256/256, LQ/SQ 72/56, widths 6/6/6/6/8/8/4, L1 16 MSHRs, L2 256 KiB 8-way 32 MSHRs, no L3, 2 DRAM controllers):
  `alecto_sweep/verify/config_proof.txt`.
- Gotcha: `pkill -f <pattern>` also kills your own shell when its command line contains the pattern.

### 11.6 Sweep status: **DONE** 2026-09-30 13:56, 243/243 runs, no errors (results in 11.7)
- **The sweep**, launched 2026-09-30 10:12 with `nohup setsid alecto_sweep/run_sweep.sh`, J = 20, 243 runs (81 SimPoints × A, C1, C0).
  **Restarted 10:17 at J = 30, RESERVE_GB = 10** (RAM sizing, §2): the J = 20 launcher was killed, its 20 runs kept going and were skipped.
  At 30 jobs: 125.6 GiB RSS, others ~40 GiB, MemAvailable ~22 GiB. ETA ~6 h.
  Check: `grep -c launch alecto_sweep/sweep.log`, `ls alecto_sweep/*/runs/*/sp_*/stats.txt | wc -l`,
  `grep -L "measurement complete" alecto_sweep/*/runs/*/sp_*/run.log`. Rerunning the script resumes.
- Then `venv/bin/python alecto_sweep/analyze.py` and report per handoff §5 (IPC, demand MPKI, L2 APKI vs A and vs C0, refreshes, stalls,
  retention misses, backdoors; flag C0 vs A > 1% IPC). Partial analysis while running works too (missing runs are listed as warnings).
- Nothing committed (both repos on `src-prefetch`, prefetch work also uncommitted). Ask the user how to commit/branch.


### 11.7 RESULT (SPEC, 11 benchmarks, SimPoint-weighted; `alecto_sweep/results/{report.md,results.csv,mpki.png,speedup.png}`)
Plots: `venv/bin/python alecto_sweep/analyze.py && venv/bin/python alecto_sweep/plot_partial.py` (SPEC top, Olden bottom).
- **Compare cores with primary MPKI** (`mpki_primary` column = `demandMshrMisses`, real L2 fetches; `mpki_primary.png`). gem5 demand misses also count
  loads to a line already in flight, which grow with the core's window: SRAM 32 KiB old → new core, demand roms 103 → 164, primary 45.7 → 45.6.
  Primary MPKI vs A, geomean: C0 −28.2%, C1 −18.3%; gain kept by C1: femflow 94, fotonik3d 96, roms 90, cpython 87, palm 71, cactus 64, sqlite 48, zstd 19, flightdm 17%.
  The lower kept on the irregular codes is real: DRT is in time, and the slower core runs fewer instructions per 10 µs (flightdm 25k → 13k), so more lines expire.

| bench | ΔIPC C0/A | ΔIPC C1/A | ΔIPC C1/C0 | MPKI A → C0 → C1 | MPKI gain kept by C1 |
|---|---|---|---|---|---|
| palm | −1.74% | −1.67% | +0.08% | 45.3 → 36.7 → 39.2 | 71% |
| flightdm | −2.05% | −2.77% | −0.74% | 47.0 → 44.7 → 46.8 | 10% |
| femflow | −17.04% | −17.09% | −0.07% | 52.0 → 45.6 → 45.7 | 99% |
| cactus | −4.01% | −3.99% | +0.01% | 114.1 → 107.7 → 109.8 | 67% |
| fotonik3d | −0.34% | −0.35% | −0.01% | 155.4 → 153.5 → 153.5 | 97% |
| cpython | −1.02% | −1.11% | −0.09% | 2.76 → 0.15 → 0.42 | 90% |
| sqlite | −2.82% | −3.06% | −0.24% | 17.9 → 15.7 → 16.9 | 44% |
| roms | −3.63% | −3.65% | −0.02% | 163.7 → 156.9 → 157.3 | 94% |
| nest | −0.42% | −0.41% | +0.01% | 159.0 → 159.1 → 159.1 | – |
| zstd | −2.91% | −2.88% | +0.03% | 18.6 → 18.0 → 18.4 | 31% |
| sealcrypto | −1.23% | −1.25% | −0.02% | 11.3 → 11.3 → 11.3 | – |
| **geomean** | **−3.49%** | **−3.59%** | **−0.10%** | ratio vs A: C0 −27.6%, C1 −19.0% (cpython dominates) | |

- **Forgetting costs ~nothing (C1 vs C0 −0.10% geomean, worst flightdm −0.74%). The whole loss vs A is the 5th L1D cycle**
  (C0 loses the same). 9 of 11 benchmarks have |C0 − A| > 1% IPC (all but fotonik3d, nest). femflow −17%: SRC's own cost is
  ~7 of its 374 lost cycles/kinst; it loses ~0.54 cycles per L1D hit (latency-bound). Olden shows the same (C0 = C1 = −6.0%).
- Why worse than the old sweeps (SRC 48 ≈ SRAM 32 there): the old SRAM 32 and SRC 48 had the **same** L1 latency; now 48 KiB pays +1 cycle
  on every hit and miss. **Open question for user/advisor:** SRC is iso-area with 32 KiB SRAM (short wires), so should it pay the 5th cycle?
  The 5-cycle number comes from 48 KiB **SRAM**. Suggested diagnostic (not run): C1 at `--l1d_hit_cycles 4` (81 runs).
- MPKI gain kept is lower than the old sweep on the irregular codes (flightdm 10%, zstd 31%, sqlite 44%): their retention misses
  (flightdm 1.18/kinst, sqlite 0.63) eat most of the 32→48 gap. 98–100% of refreshes are opportunistic; stalls 0.7–6.3 cycles/kinst.
- **Backdoors: every dirty-loss counter 0** (violations, lazy writebacks, expired dirty evictions, revived dirty, expired prefetch dirty).
  `expiredFunctional` 382 (nest), all clean. `expiredSnoops` 559,677 (flightdm 309k, roms 223k), all clean (a clean line never supplies
  snoop data): they track L2 churn. flightdm sp_0: L2 replacements 395 (1 MiB L2) → 1.64M (256 KiB), l2bus snoops 13k → 1.65M.

### 11.8 Sanity check of the femflow (−17%) and bh (−22.5%) losses: a gem5 store-drain artifact
- **The 5-cycle setting adds exactly +1 cycle.** Pointer chase rerun on the frozen sweep configs (`calib/results/recheck_*.csv`):
  L1 4 → 5, L2 15 → 16, DRAM 210 → 211. `config.ini` of the femflow and bh runs: A tag/data 3/3, C0/C1 4/4, `sequential_access=false`
  (hit = max(tag, data)), so not +2.
- **But +1 cycle costs up to +1 cycle per STORE, not per load.** `X86O3CPU` sets `needsTSO = True`, and the O3 LSQ then keeps **one store
  in flight**: the next store is written back only after the previous store's cache response (`src/cpu/o3/lsq_unit.cc` l.823, 1092, 1206).
  Store drain = 1 store per L1 hit latency. Store microbenchmark `calib/stores.c` (independent stores, L1-resident; `calibrate.py --prog stores`):
  **3.00 cycles/store at the 4-cycle L1D, 4.00 at 5 cycles** (default profile: 4.00). A real x86 core keeps TSO but drains its store buffer pipelined,
  about 1 store per cycle; it doesn't wait a full L1 round trip per store.
- Evidence it drives the extremes (lost cycles/kinst C0 − A vs stores/kinst):
  femflow 372 vs 383 stores (0.97 lost/store), 4.74 cycles/store at A, rename blocked on a full SQ 57% of cycles;
  bh 330 vs 348 (0.95/store), 3.26 cycles/store at A (at the 3-cycle cap), SQ full 50%. Loads can't explain it: bh would need 2.8 lost cycles per load.
  roms (−3.6%, SQ full 40%) is partly store-bound too. Most others lose ≤ 0.4 cycles/store with the SQ rarely full; cactus (−4.0%) and tsp (−9.6%) are load-latency losses.
- **Don't quote femflow/bh as L1-latency sensitivity.** They measure gem5's serialized store drain. Proposed fix (user's decision, not done):
  `needsTSO = False` in the alecto profile (single core, SE mode: no other agent can observe store order), recalibrate stores/loads, rerun A/C0/C1 + Olden.

### 11.9 Rerun with `needsTSO = False` (user's decision, 2026-09-30): `alecto_sweep_notso/`, `olden/runs_notso/`
- `cpu_profiles.py`: `ALECTO_NEEDS_TSO = False`, set in `apply_core` (alecto only; default profile untouched). Frozen copies:
  `alecto_sweep_notso/configs/` (SPEC) and `alecto_sweep/notso/configs/` (identical, used by the Olden rerun).
  The first run (`alecto_sweep/{A,C0,C1}`, `olden/runs`) keeps TSO on and stays reproducible from `alecto_sweep/configs/`.
- Microbenchmarks with TSO off: stores **1.75 cycles/store at both 4 and 5 cycles** (was 3.00 / 4.00: drain no longer tied to L1 latency);
  load-to-use unchanged (L1 4 / 5, L2 15 / 16, DRAM 210 / 211). `config.ini`: `needsTSO=false`.
- Launch: `OUT=$PWD/alecto_sweep_notso SWEEP_GROUPS="A C0 C1" J=30 RESERVE_GB=10 alecto_sweep/run_sweep.sh femflow_r cactus_r roms_r zstd_r
  sqlite_r flightdm_r palm_r sealcrypto_r cpython_r nest_r fotonik3d_r` (worst first, all three configs per SimPoint), log `alecto_sweep_notso/sweep.log`.
  Started 17:27. **Gotchas:** `OUT` must be a direct child of `~/forgetting` (`restore_measure.py` finds the repo as `<config dir>/../..`;
  a first launch under `alecto_sweep/notso/` failed all 243 runs at startup, now refused by the launcher). Don't name a shell variable
  `GROUPS` (bash ignores assignments to it); the launcher uses `SWEEP_GROUPS`.
- Olden: `RUNS=$PWD/olden/runs_notso ALECTO_CFGDIR=$PWD/alecto_sweep/notso/configs J=27 olden/run_sweep.sh`; analysis
  `OLDEN_RUNS=... OLDEN_RESULTS=$PWD/olden/results_notso OLDEN_DIAG=<none> venv/bin/python olden/analyze.py`. 27/27 done, 0 dirty loss.
  **C0 vs A: bh −22.5% → −0.7%, tsp −9.6% → −5.2%, perimeter −5.4% → −0.3%; geomean −6.0% → −0.9% (C1 −1.0%).**
  bh's baseline IPC 0.88 → 1.35. C1 vs C0 ≤ 0.05% everywhere.
- SPEC analysis/plots when done: `ALECTO_OUT=$PWD/alecto_sweep_notso venv/bin/python alecto_sweep/analyze.py`, then
  `ALECTO_RESULTS=$PWD/alecto_sweep_notso/results OLDEN_RESULTS=$PWD/olden/results_notso venv/bin/python alecto_sweep/plot_partial.py`
  (partial results work: only benchmarks with every SimPoint done are plotted).

- **SPEC RESULT (243/243 done 21:0x; `alecto_sweep_notso/results/{report.md,results.csv,ipc.png,mpki_primary.png,mpki.png}`):**
  IPC vs A, geomean: **C0 −0.90%, C1 −0.98% (was −3.49 / −3.59 with TSO); C1 vs C0 −0.08%.** femflow −17.0% → **+2.0%** (A IPC 0.551 → 1.155),
  roms −3.6% → −1.0% (A 0.396 → 0.593), zstd −2.9% → −0.5%, sqlite −2.8% → −1.9%, flightdm −2.0% → −1.3%, palm −1.7% → −0.8%.
  Unchanged: cactus −4.0% (load-latency bound), fotonik3d, nest. Primary MPKI unchanged from the TSO run (C0 −28.0%, C1 −18.2% geomean;
  kept: femflow 98, fotonik3d 96, roms 94, cpython 86, palm 72, cactus 64, sqlite 53, flightdm 25, zstd 20%). Dirty-loss counters all 0;
  ~99% of refreshes opportunistic. **Gotcha: never edit a bash script while it runs** (bash reads it incrementally): editing
  `run_sweep.sh` mid-sweep made the launcher die at its last line without the "done" line (all runs had finished).

### 11.10 Overnight diagnostic: 48 KiB at 4 cycles (user's request, kept for later), `alecto_sweep_notso_h4/`, `olden/runs_notso_h4/`
- Same no-TSO profile as 11.9, but C0 and C1 use `--l1d_hit_cycles 4` (L1D tag/data 3/3, like A). A is **not rerun**: `A` is a symlink to
  the 11.9 run's A (identical config). C1 timing unchanged (T_guard 1501, force from 95.0%); `inline_refresh_cycles` = data latency = 3.
- Chain script `alecto_sweep/run_h4_after.sh` (started 2026-09-30 ~20:45, `nohup setsid`, log `alecto_sweep_notso_h4/chain.log`): waits for the 11.9
  sweep's "done" line, then Olden (C0, C1; J=18), then SPEC (`OUT=alecto_sweep_notso_h4 HIT48=4 CONFIGS="C0 C1"`, J=30, worst first), then analysis
  and plots (`olden/results_notso_h4/`, `alecto_sweep_notso_h4/results/`, labels via `ALECTO_HIT48=4`).
- Launcher options added for this: `HIT48` (both `alecto_sweep/run_sweep.sh` and `olden/run_sweep.sh`, default 5), `CFGS` (Olden).
- Test before launch: treeadd, C1 at 4 cycles, frozen configs: tag/data 3/3, `needsTSO=false`, 0 violations.

---

## 12. Session 4, later: Olden microbenchmarks (`~/forgetting/olden/`)

- Source: llvm-test-suite `MultiSource/Benchmarks/Olden` (sparse clone in `olden/src_repo`, commit `cde6a9c353`).
  `olden/build.sh` builds all 10 static (`-O3 -march=x86-64 -mtune=generic -static -DTORONTO`, the CMake flags) into `olden/bin/`.
  All 10 match the test-suite reference outputs natively.
- **Inputs tuned to a ~40 KiB working set** (`olden/tune/`: cachegrind, LRU D1 at 16–96 KiB, always 64 sets; `cg_grid.csv`, `cg_curve.csv`).
  Chosen in `olden/inputs.txt`: bh 192 20, bisort 1536, em3d 128 3 75, health 4 20 1, mst 48, perimeter 5, treeadd 10, tsp 320,
  voronoi 64 20 32 7. `power` dropped (no size argument, 1.75 B insts, flat). The runs are tiny: 0.6–12M instructions.
- `olden/run_olden.py`: SE mode from start, whole program in one stats dump; same flags as `restore_measure.py`, imports the frozen
  `alecto_sweep/configs`, so A / C0 / C1 are exactly §11.4. `olden/run_sweep.sh` (resumable, J=9, ~0.1 GiB RSS per run), binary `alecto_sweep/bin/gem5.fast`.
  Diagnostic 48 KiB at 4 cycles (SRAM and SRC) in `olden/runs_diag/{C0h4,C1h4}`. `olden/analyze.py` → `olden/results/{results.csv,report.txt,ipc.png}`.
- gem5 output matches native for 8/9. **health** differs (average stay 11.68 vs 13.12): its RNG round-trips a 64-bit seed through `float`,
  which gem5's X86 FP emulation rounds differently. Identical in A/C0/C1 (same instruction count), so the comparison is fair.
- **Result:** MPKI drops 15–70% from 32 to 48 KiB, but IPC vs A is −6.0% geomean for C0 and C1 (bh −22.5%, tsp −9.6%, health +0.4%):
  the 5th hit cycle dominates on these pointer chasers. At 4 cycles, 48 KiB gives +0.5% geomean (health +2.0%, mst +2.2%, the rest ≈ 0).
  SRC vs SRAM at the same size and latency: −0.05% (0 lost dirty data, ~all refreshes opportunistic).

---

## 13. Session 4, night: "bizarre tests" (`~/forgetting/bizzare_tests/`)

Goal (user): known benchmarks engineered to the **32→48 KiB sweet spot**: hot set 32–48 KiB (thrashes 32 KiB 8-way,
fits 48 KiB 12-way), repeated so steady state dominates, so the 48 KiB L1D can **raise IPC** despite the 5th cycle.
No custom benchmarks; only sizes, inputs and flags are engineered. **No SPEC** (user). Directory name keeps the user's spelling, underscore instead of the space.

- **Sources:** llvm-test-suite `cde6a9c353` sparse clone in `src/` (PolyBench 4.2, llubenchmark, Shootout), MiBench dijkstra
  (`~/forgetting/mibench`), GAP marker binaries (`gap_sweep/bin`). `build.sh` builds everything static
  (`-O3 -march=x86-64 -mtune=generic`) into `bin/`; inputs in `inputs/`.
  PolyBench is built the llvm way (kernel + strict-FP rerun; `FMA_DISABLED=1` is broken upstream in several kernels).
  Old MiBench C needs `-std=gnu17 -fpermissive` on gcc 15.
- **Points:** `points.txt` (name bin warmup measure roi args), 55 points: jacobi-2d, seidel-2d, heat-3d, fdtd-2d, gemm, doitgen,
  floyd-warshall, lu (size grids around the 32/48 KiB edges for working-set curves), llubenchmark (40 lists × l), heapsort,
  dijkstra N 88–100, GAP bfs/pr/cc/tc/bc/sssp on tiny graphs (kron g9 k16, g10 k4, uniform u9 k16, u10 k8).
- **Selection:** cachegrind screen (D1 32K/8 vs 48K/12), `screen/*.csv`. Dropped: nussinov, Olden health (hot set grows past 48 KiB),
  patricia (MPKI ≈ 1 at any trie size: sscanf and leaked per-line mallocs dominate), rijndael (0.02 MPKI at 32 KiB: its tables fit),
  and the rest of MiBench. The user's old 16→24 KiB runs (`new_write/refresh_dirty_mru/`) show rijndael +9.7% and patricia +2.4% at 16→24,
  but both already fit in 32 KiB.
- **Runs:** `run_se.py` (copy of `olden/run_olden.py` plus an instruction window: warm up W, then measure M; `--roi` starts the window at m5 `work_begin`).
  The last stats dump is the measurement. Frozen no-TSO configs in `configs/` (copied from `alecto_sweep_notso/configs`), binary `alecto_sweep/bin/gem5.fast` (`binary.txt`).
  Configs: **A** SRAM 32K 4c, **C0** SRAM 48K 5c, **C1** SRC 48K 5c (§11.4 flags), **C0h4**/**C1h4** the same at 4 cycles.
  275 runs, ≤ 52M insts each, ~90k inst/s, ~0.5 GiB each.
- **Automation (survives the session):** cron `*/10 * * * * bizzare_tests/watchdog.sh` restarts `chain.sh` (under `flock .chain.lock`) unless it is running or `DONE` exists.
  `chain.sh`: waits for `alecto_sweep/run_h4_after.sh` and every `alecto_sweep_notso*` gem5 run to exit, then `run_sweep.sh`
  (J=40, RESERVE_GB=10, resumable, skips runs in progress, one retry pass), then `analyze.py`, then `DONE`. The watchdog removes its own crontab line after DONE.
  Logs: `chain.log`, `sweep.log`, `analyze.log`. All scripts are wrapped in `main()`, so they're safe to edit while running.
- **Results:** `results/report.md` (geomean per family, per-point table sorted by C1/A), `results/table.csv`, `results/results.csv`,
  `ipc_ratio.png`, `ws_curve.png`. Re-run with `venv/bin/python bizzare_tests/analyze.py`.
- Early smoke hint (tiny window): jacobi-2d N=50 with primary MPKI 30 moved IPC only +0.07% at C1h4. On this core, streaming L2 hits are hidden,
  so the pointer-chasing points (llu, GAP, dijkstra) are the likelier winners.
- Check: `cat bizzare_tests/chain.log; tail -n 5 bizzare_tests/sweep.log; ls bizzare_tests/runs/*/*/stats.txt | wc -l; crontab -l`.
- **RESULT (2026-10-01; 275/275 runs, 0 failures; done 01:10).** The chain's automatic analysis crashed: gem5 omits zero-valued MSHR stats, so `st[...]` failed.
  Fixed to `st.get(..., 0)` and rerun by hand. The cron line removed itself.
  IPC vs A, geomean of all 55 points: **C0 −0.65%, C1 −0.69%, C0h4 +3.48%, C1h4 +3.42%; C1 vs C0 −0.03%** (worst −0.18%).
  0 dirty loss, 0 forced refreshes, retention misses ≤ 0.66/kinst.
  - **llubenchmark explodes:** l32 (40 KiB) gives C1 **+27.8%** and C1h4 **+52.2%** (primary MPKI 69 → 0); l28 +20.6/+43.5%, l36 +27.0/+51.1%.
    The controls bracket it: l24 (30 KiB, fits in 32 KiB) −15.4% at 5c (pure 5th-cycle cost) and +0.7% at 4c; l40 (50 KiB) +1.4% / +16.3%.
  - fdtd-2d +1.5 to +6.6% (5c) and +4.9 to +7.9% (4c). GAP pr +0.7/+1.0%.
  - **Streaming stencils/BLAS stay flat** (jacobi-2d, seidel-2d, heat-3d, gemm, doitgen ≈ 0%) even with primary MPKI 30 → 0:
    this core hides independent L2 hits completely.
  - The 5th cycle wins elsewhere: floyd −4 to −9% (4c: +3.5 to +5.4%), lu −6 to −13% (4c ≈ 0), dijkstra −7% (4c 0), GAP bfs/cc/tc/bc/sssp −1 to −5% (4c +0.2 to +2.2%).

---

## 14. Session 5, night (2026-10-01): gcc_r and omnetpp_r added; two gem5 X86 fixes (`~/forgetting/spec_add/`)

- **Added to `alecto_sweep_notso/{A,C0,C1}/runs`** (no-TSO profile, §11.9 flags): `gcc_r` (train `scilab.c -O3`, the most
  L1-sensitive of the 3 train commands by cachegrind: 32→48 KiB −13.6%), `omnetpp_r` (train, mesh 22×22), and `omnetpp_m10_r`
  (**tuned, non-standard**: mesh 10×10 + the test input's destAddresses, picked by a cachegrind mesh screen 8–22 for the largest 32→48 drop;
  `spec_tests/omnetpp_m10_r_train/randomMesh.ini`). Native outputs match the SPEC reference (gcc .s identical, omnetpp .sca).
  SimPoints 6/6/7 (BBV + `tools/cluster_bbv.py`, usual settings); checkpoints in `spec_checkpoints_sp/`. Table entries added to
  `configs/forgetting_cache/{kvm_checkpoint_sp,restore_measure}.py` and to the frozen `alecto_sweep_notso/configs/restore_measure.py`
  (still identical to the source copy). Scripts: `spec_add/{stage,cg,bbv,ckpt,run_sweep,chain}.sh`, `analyze_new.py`.
- **Reports** (the 11-benchmark `alecto_sweep_notso/results` is untouched): `spec_add/results_13/` (11 + gcc + omnetpp standard)
  and `spec_add/results_new/` (the 3 new). Run `venv/bin/python spec_add/analyze_new.py`.
- **Binary `spec_add/bin/gem5.fast`** (`spec_add/bin/binary.txt`) = `alecto_sweep/bin/gem5.fast` source + two fixes, **now also in the
  gem5 tree and `build/X86/gem5.fast` (uncommitted)**, so the tree no longer equals `bin/gem5.fast.prefetch`:
  1. `src/arch/x86/linux/syscall_tbl64.cc`: syscall 439 `faccessat2` → `faccessatFunc` (omnetpp's static glibc; gem5 fataled).
  2. `src/arch/x86/isa/insts/.../multiply_and_divide.py`: the DIV/IDIV **memory** operand goes to `t7`, not `t2`. Upstream gem5 bug:
     IDIV m / IDIV_B m keep the negated dividend high half in `t2`, then load the divisor into `t2`. Negative dividend → false #DE
     (gcc panicked in `ira-color.cc`); negative divisor with non-negative dividend → **silently wrong quotient sign** (7/−3 = +2).
     Test `spec_add/idiv_test/` (gem5 atomic and O3 = native checksum).
- **Existing results unaffected:** the fixed binary reran A on all 81 SimPoints + C1 on palm (8): 78/89 bit-identical; the 11 others have
  identical committed instructions/loads/branches and IPC (worst flightdm sp_5 −0.007%): only speculative-access noise from the changed
  micro-op dependency (`spec_add/equiv_report.txt`, runs in `spec_add/{A,C1}/runs`).
- Gotcha: omnetpp calls `chdir()`, and gem5 SE changes the host cwd, so relative gem5 paths (`-d`, `--checkpoint_dir`) land in the
  benchmark directory. Pass absolute paths (the sweep launchers do).
