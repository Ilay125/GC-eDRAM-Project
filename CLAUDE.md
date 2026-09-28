# CLAUDE.md: SRC (Selective Retention Cache) thesis project

Handoff for future Claude Code sessions. Last updated 2026-09-28 (session 2: SRC DRT sweep launched).
Read all of it before touching anything. Section 9 says what is in flight and what comes next.

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
- **OOM:** 50 parallel O3 runs exceed 187 GB. Use `J=25` (or 15 if palm-heavy).
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

outer:
- `7263e91` Track restore_measure.py and kvm_checkpoint_sp.py as-is (pre-rework snapshot)
- `26fb15d` configs: Drop debug_drt_mode, add --drt_strict
- `ffe2a22` configs: Pass SRC retention params, add timing/inline flags
- `a192f1f` Add SRC directed retention tests and rework equivalence checks
- `acec9ea` tests: Build the retention test binary if missing
- `befe4d2`, `6d9e382` CLAUDE.md
- `a928f1b` Add SRC smoke results and the SRC DRT sweep tooling (session 2)

### Frozen binaries (`~/forgetting/bin/`)
- `gem5.fast.pre-rework`: the binary every earlier result (incl. the SRAM MPKI sweep) came from.
  gem5 `ac48641acd`, built 2026-09-27 12:45 (details in `gem5.fast.pre-rework.txt`). It needs the **old**
  configs, which have `debug_drt_mode`; a copy of those lives in the session scratchpad only, and the git
  snapshot is commit `7263e91`.
- `gem5.fast.step2` (built session 2), `gem5.fast.step3`, `gem5.fast.step4`, `gem5.fast.step5`: the binary after each rework step.
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
`--refresh_line_cycles N` (0 = 2 × data latency) `--no_inline_refresh` `--inline_refresh_on_read`.
`--debug_drt_mode` **no longer exists**; the user asked to remove it, and SRC always uses the former mode 1.
With `--drt_ticks 0`, the daemon flags are ignored and the cache is plain SRAM.

---

## 6. Completed: SRAM (DRT=0) MPKI sweep, formerly "knee sweep"

Everything is in **`~/forgetting/sram_mpki_sweep/`** (moved there at the user's request; `run_all.sh` points to it):
`run_sweep.sh` (was `knee_sweep.sh`), `analyze.py`, `sweep.log`, `runs/<bench>/sp_<i>/l1d_<N>k/{stats.txt,config.ini,run.log}`,
`results/results.csv`, `results/mpki_vs_size.png`.

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
- **The one guarantee:**
  - T_sweep = numSets × (scan + k_max × line) cycles, with k_max = assoc if dirty refresh is on, else top_mru.
  - T_guard = T_sweep + line + margin × DRT.
  - **Daemon:** force-refresh a block when its remaining life < T_guard.
  - **Store hit:** if remaining < T_guard, do an **inline refresh** (+`inline_refresh_cycles` latency, plus one line of occupancy).
    If remaining < the inline read time, it's too late: treated as expired (`inlineTooLate`).
  - **Startup `fatal` if T_guard ≥ DRT.**
  - With no daemon, T_guard = line + margin × DRT.
- **All retention stats:**
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

## 9. State at handoff

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
