# SRC refresh design: banks, controller, metadata ledger

This describes the hardware the simulator models for the SRC (GC-eDRAM) L1D refresh, and every assumption behind it.
The code is `gem5/src/mem/cache/retention/retention_manager.{hh,cc}` (branch `src-rework`). For stat meanings see
`docs/retention_stats.md`.

## 1. Data-array banks (`refresh_banks`, default 1)

- **Mapping:** set *s* lives in bank *s* mod B. The banks are set-interleaved sub-arrays: a whole 64 B line sits in one
  bank. The sweeps use B = 8 with 64 sets, so each bank holds 8 sets × 12 ways = 96 lines (6 KiB).
- **What runs in parallel:**
  - a refresh occupies only its own bank for `refresh_line_cycles` (a line read plus a line write, default 8 cycles);
  - a demand hit waits only if **its** bank is refreshing, so a read in one bank proceeds while another bank refreshes;
  - different banks refresh at the same time.
- **Opportunistic refresh** needs only its own bank to be idle: no demand access to that bank this cycle, and no
  refresh in progress there.
- **Not modeled:** conflicts between two demand accesses in the same bank. The SRAM baseline doesn't model them
  either, so the comparison is like for like.
- **Assumption to state in the thesis:** real 8-bank L1Ds such as Sandy Bridge's interleave the banks by 8-byte chunks
  *within* a line, so every line spans all banks. Per-bank refresh needs the set-interleaved organization used here.
  (The Cortex-R7 detail is still to be checked before citing it.)
- **B = 1** is the original single-array model, bit-exact with all earlier results.

## 2. Refresh controller: one central scanner

**Chosen design:** one scanner FSM, the same as with B = 1.
- It walks the sets in order with its set pointer.
- Each step reads one set's metadata (ages, dirty bits, LRU order), decides which lines to refresh, and hands those
  refreshes to that set's bank.
- The bank-local refresh unit performs them. A GC-eDRAM sub-array already has the read and write-back circuitry.
- The scanner waits only if the bank of the **next** set is still busy.

**Rejected alternative:** 8 per-bank sub-controllers, each with its own set pointer over its 8 sets.

| | Central (modeled) | 8 sub-controllers (not modeled) |
|---|---|---|
| Metadata reads per step | 1 set, as with B = 1 | up to 8 sets at once: a banked metadata array or 8 read ports |
| Controller logic | 1 FSM, 1 pointer, age comparators for 12 ways | 8× that; small, but duplicated |
| Clock | cache clock | the same cache clock (no extra domains) |
| Cross-bank coupling | head-of-line: while waiting on a busy bank it visits no other bank | none |
| T_sweep at 10 µs (scan = 1) | 832 cycles, force at 95.2% of DRT | 776 cycles, force at 95.4% |

With a 1-cycle scan the refresh work (up to 12 × 8 = 96 cycles per set) dominates, so sub-controllers would improve
the bound by only about 7% while adding metadata ports. That's why the central scanner was chosen. (The sub-controller
gap grows only if the per-set scan turns out slow: with scan = 8, it's 1,280 vs 832 cycles.)

## 3. Retention guarantee with banks

- **The bound:** `T_sweep = ceil(S/B) × (B·scan + k_max·line)`, where S = sets, and k_max = assoc when dirty
  refresh is on (else top_mru).
- **Proof:** take rounds of B consecutive sets (one set per bank).
  - When the scanner reaches a set in round r, the only work in that set's bank is its refreshes from round r−1.
  - That work was issued no later than the start of round r, and takes at most k_max·line.
  - So round r takes at most B·scan + k_max·line, and a set is revisited within ceil(S/B) rounds.
- For B = 1 the bound reduces to the original `S × (scan + k_max·line)`.
- **The force threshold** is unchanged: `T_guard = T_sweep + line + margin·DRT`. The daemon force-refreshes a line whose
  remaining life is below T_guard, and startup is refused if T_guard ≥ DRT.
- **Numbers** (48 KiB 12-way, 64 sets, 3 GHz, scan 1, line 8, margin 2%):

  | B | T_sweep | T_guard @ 10 µs | force point @ 10 µs | smallest DRT accepted |
  |---|---|---|---|---|
  | 1 | 6,208 cycles | 6,816 | 77.3% of DRT | about 2.1 µs |
  | 8 | 832 cycles | 1,440 | 95.2% of DRT | about 0.3 µs |

  At 10 µs the 2% margin (600 cycles) is now the largest part of T_guard with 8 banks.
- **Known slack, covered by the margin:**
  - inline refreshes on a bank can delay the scanner slightly beyond the bound;
  - a set's k refreshes finish up to k·line after they are issued.

  The `daemonSweepCycles` histogram records the real sweep times, and the directed tests check that they stay within
  `tSweepCycles`.
- **Per-set revisit check:** `setVisitInterval` and `maxSetVisitCycles` record the interval between two visits of the
  same set, which is what the guarantee needs.
  - **Tighter bound (proof):** visit times satisfy `v(p+1) ≤ max(v(p) + scan, v(p+1−B) + k·line)`. The scanner waits
    only for the next set's bank, whose work was issued one round earlier and takes at most k·line. Unrolling gives
    `v(p+B) − v(p) ≤ max(B·scan, k·line)` for **any** B consecutive steps. So every revisit takes
    ≤ ceil(S/B) · max(B·scan, k·line).
  - With C1 timing that is 8 × max(8, 24) = **192 cycles**, against the formula's 256: the formula adds the scans to the
    refreshes, but they overlap.
  - The directed worst case reaches exactly 192 (`ai_worst`: every line refreshed at every visit).
  - The formula is kept as it is: every existing result uses it, and it is safe.

## 3b. Active invalidation (`active_invalidate`, branch `active_invalidate`)

- **Rule:** at each visit, every valid line with remaining life < T_guard is either refreshed or invalidated:
  - `keep = valid & (dirty | top-4 MRU | Shared)` → refresh (forced);
  - `inv = valid & ~keep & in window` → invalidate (a CleanEvict to L2, as for any clean eviction).

  It replaces the inline refresh, which must be off, because the next-visit bound needs the daemon to be the only bank
  user. It also needs `refresh_dirty`.
- **Guarantee:** after every visit, each valid line has more than T_guard − T_sweep of life left.
  - A store that dirties a clean line between visits is seen at the next visit (≤ T_sweep later), while the line is
    still alive, and the line is then kept.
  - So no valid line is ever expired: no retention misses, no expired snoops/evictions, no lazy writebacks.
- **Threshold:** `retention_guard_sweeps = 2`, margin 0. T_guard = 2·T_sweep + line = 2 × 256 + 2 = **514 cycles** at
  C1 timing, so lines are refreshed or invalidated from **98.3% of DRT** (C1 forced from 95.0%).
  - At the acting visit at least T_sweep + line remain.
  - A clean, unkept line loses at most about 2.6% of its life (invalidated at 97.4–98.3% of DRT).
- **Same-cycle races:** a daemon step is one event: read, decide and apply happen in the same cycle. The daemon event
  (priority 0) runs before the O3 CPU tick (priority 50; checked at startup):
  - an access in the cycle of an invalidation finds the line invalid and misses (L2 has the same clean data);
  - a fill earlier in that cycle makes the line fresh, so it is not touched;
  - a store earlier in that cycle has already made it dirty, so it is kept.
- **Pending upgrade:** a store to a Shared line waits in the MSHR for a data-less UpgradeResp that expects the line to
  stay. Only a non-writable line can have an open transaction: a read hits, and a store to an E or M line hits. So
  Shared lines are kept (refreshed). The rule reads the coherence state with the other tag bits and needs no MSHR
  connection.
  - The simulator checks the claim (`activeInvalidateInflight`, must be 0).
  - Rejected: an MSHR set-index match per step, which means comparators against every MSHR and write-buffer entry plus
    a new MSHR-to-controller connection.

## 3c. RTL alignment (`quantized_age`; branch `rtl_align`)

The RTL controller (`docs/SRC_controller_RTL_guide.md`) is the reference. gem5 follows it where the difference changes
**what** the cache keeps, drops or sends. Pure bank-timing details stay as they are and are listed as limitations
below. Both flags are off by default; with them off, results are bit-exact with the CLK binary.

- **Keep rule: CLOCK (`--keep_touched --cold_dirty=touched`, top_mru 0, no clear age).** This matches the RTL, whose
  used-bit clear is wired but tied off. `keep_opp = used`, `keep_dead = used | ~writable`.
- **The used bit (interface definition for the RTL).** In gem5 a line is "used" if
  `lastTouchTick > max(fullChargeTick, refClearTick)`.
  - It is set **only by a demand tag hit** in `BaseCache::access` (hook `onAccessHit`), for loads and stores alike.
  - It is **not** set by the miss whose fill brings the line in, by MSHR targets merged into that miss (they are served
    at the fill, not by a tag hit), by snoops, by functional accesses, or by hardware prefetches.
  - It is cleared by a fill and by a refresh (forced or opportunistic), and by the clear age when that is used (CLK05;
    not in the RTL yet).
- **Clean drops are announced (decision 2026-10-04); `silent_clean_drop` stays in the code, off, unused.** gem5
  models an exact snoop filter on the L2 bus: it forgets a line only when the L1 sends a CleanEvict or writeback, or
  on an invalidating snoop. A silent drop leaves the entry forever. The L2's eviction snoop learns "not cached", but
  the filter never uses it. In the first full sweep with silent drops, 8 of 93 runs panicked ("snoop filter exceeded
  capacity of 131072 cache blocks"). Silent drops also made the SRC send fewer L2 messages than the SRAM baselines,
  which still announce every clean eviction: a protocol difference, not a cache difference.
  - So gem5 keeps its protocol: a clean drop sends a CleanEvict through a write-buffer slot, like any clean eviction
    in gem5, and falls back to a forced refresh when the buffer is full (as dirty drops do).
  - **Required RTL change** (`docs/SRC_controller_RTL_guide.md` §4.3, §4.4, §14.3):
    - a clean, unkept line at its deadline needs a write-buffer slot, like a dirty one;
    - slots go to all drops in way order: `cand_drop = deadline & ~keep_dead`, `slot` = the first `wbuf_free` bits of
      `cand_drop`, `force = deadline & (keep_dead | (cand_drop & ~slot))`, `inv = slot`, `wb_mask = slot & dirty`
      (bank read), new output `ce_mask = slot & ~dirty` (address-only CleanEvict, no bank time);
    - bankSched is unchanged;
    - the cache puts the CleanEvict in the reserved entry through its normal clean-eviction path;
    - check `popcount(wb_mask | ce_mask) <= wbuf_free`;
    - the §4.4 silent-drop protocol assumption becomes "every clean eviction is announced (exact snoop filter
      below)".
- **Quantized ages (`quantized_age`, `age_epoch_log2` 10, `age_bits` 5).** The scanner reads `age = (epoch − stamp)
  mod 2^bits`, where `stamp` is the epoch of the last full-line write (fill or refresh). One epoch is
  P = 2^10 = 1024 cycles.
  - In gem5 the stamp is computed from `fullChargeTick`, so it needs no new state.
  - **Deadline** `F = floor((DRT − T_guard) / P)`, with T_guard from the guard formula. A visit that sees age < F
    knows the exact age is < F·P, so the line has more than T_guard left at the next visit.
  - Startup refuses `F·P + T_sweep + k_max·line ≥ DRT`. It also refuses a stamp that could wrap, with the RTL's two
    checks (since RTL2, §3d): `F ≥ 2^bits − 1`, or `T_sweep ≥ (2^bits − F)·P` (a line seen below F reaches at most
    F − 1 + ceil(T_sweep / P) at the next visit). Until RTL2 the check was `F + 1 ≥ 2^bits − 1`; every config run so
    far passes both.
  - **Operating point:** `--guard_sweeps=1`, margin 0, so T_guard = 256 + 2 = **258** and **F = 29**. A line is
    acted on at a true age of (F−1)·P to F·P + T_sweep = **95.5–99.7% of DRT**. The directed tests measure
    95.5–99.1%.
  - **F = 28** is what T_guard = 514 (the exact-age CLK setting, `guard_sweeps=2`) would give: action at
    92.1–96.3% of DRT. The RTL guide rejects it, because flooring already adds up to one epoch of slack.
  - **Opp age** `floor(refresh_opp_age · DRT / P)` = floor(0.8 × 30030 / 1024) = **23**. **Clear age**
    `round(touched_clear_age · DRT / P)`, at least 1 (CLK05: 1 epoch); 0 in CLK. All three can be overridden
    (`deadline_epochs`, `opp_age_epochs`, `touched_clear_epochs`).
  - Checks at every visit (counted, and a panic under `drt_strict`): no valid line has exact age ≥ DRT
    (`quantExpiredAtVisit`), and no valid line's epoch age reaches 2^bits − 1 (`epochWrapRisk`).
- **Limitations: RTL behaviour not modeled.** Each is a bank-timing detail, bounded by the measured stall cycles
  (all refresh/writeback stalls together are 0.4–4.6 cycles per kinst in the CLK05 sweep, ≤ 0.5% IPC):
  1. **Opportunistic scheduling.** gem5 decides an opp refresh in the scanner event, before the CPU tick of the same
     cycle, so a same-cycle hit can stall behind it. The RTL queues every opp candidate of a visit per bank and starts
     one only in a cycle with no demand to that bank. It replaces the leftovers when the next list for the bank
     arrives, and its 2-cycle op can still stall a demand in the next cycle. gem5 is pessimistic here.
  2. **Scanner hand-off.** The RTL hands a bank a new list once its deadline work has started. gem5 waits until all
     work in the next set's bank (including opp work) has finished. The sweep bound holds either way.
  3. **Fills, data-reading snoops and victim reads** do not wait for refreshes in gem5. In the RTL they wait behind
     deadline work and block opp starts.
  4. **Writeback data.** gem5 copies the data when it decides; the RTL reads it when the bank executes the writeback
     read, after the set's forced refreshes (≤ 12 × 2 cycles later). A miss to a line whose writeback is still queued
     is served by L2 after the writeback (gem5 has no write-buffer forwarding); the RTL serves it from the write buffer.
  5. **One-cycle offsets.** gem5 starts deadline work in the commit cycle; the RTL starts it the next cycle. gem5
     restamps a refreshed line at the decision; the RTL restamps it at the issue edge, at most 24 cycles later. Both
     are in the safe direction.

## 3d. The 2-bank RTL controller (`refresh_scan=line`; RTL2, 2026-10-06)

The RTL was restructured: the stamps moved from flip-flops into a per-bank GC-eDRAM macro (`gcStampArray`, 384 rows ×
5 bits, synchronous read), which forced 2 banks and one scanner per bank. gem5 models it as an opt-in mode; with the
new flags off, the binary is bit-exact with `bin/gem5.fast.rtl_align` (verified: the RTL config and DRT = 0).

| Parameter | Old RTL | New RTL | gem5 flag |
|---|---|---|---|
| Banks | 8 (bank = set[2:0]) | **2** (bank = set[0]), 32 sets × 12 ways = 384 rows per bank | `--refresh_banks=2` |
| Scanner | one, a whole set per cycle, all 12 ways decided at once | **one per bank, one row per cycle** (ways inner, sets outer), 2-stage stamp pipeline | `--refresh_scan=line` |
| LINE in the bound | 2 | **4** (budget; the bank operation is still 2 cycles) | `--refresh_line_budget_cycles=4` (occupancy stays `--refresh_line_cycles=2`) |
| T_sweep | ceil(64/8) × (8·1 + 12·2) = 256 | **384 × (1 + 4) = 1920** | derived |
| T_guard | 258 | **1920 + 4 = 1924** (needs `--guard_sweeps=1 --retention_margin=0`; line mode warns otherwise) | derived |
| F (DEADLINE_AGE) | 29 | **27** = floor((30030 − 1924) / 1024) | derived |
| Opp age | 23 | 23 | derived |
| Startup checks | F·P + T_sweep + k·line < DRT; F + 1 < 2^b − 1 | **F·P + T_guard ≤ DRT** (29,572 ≤ 30,030); **F < 2^b − 1** and **T_sweep < (2^b − F)·P** (1920 < 5120) | both modes now use the new stamp checks |
| Per-bank scheduling | three 12-bit masks, priority ladder | **one pending slot**: force/wb issue regardless of demand, opp only in a demand-free cycle | modeled |

**Line-mode model** (`processLineStep`, one event per bank, before the CPU tick):
- Each step decides one row with the same CLK rules as the set scanner, applied to one line: keep = dirty (unless cold)
  or used; at age ≥ F a kept line is force-refreshed, an unkept one dropped (dirty → writeback read, clean →
  CleanEvict), Shared / in-flight / full-buffer → forced refresh; a kept line at age ≥ 23 is an opp candidate.
- **retire = !needs_bank || bank_ready**, `needs_bank = force || wb || opp` (not ce). `bank_ready` = the slot holds no
  unissued force/wb. A row whose own decision needs the bank waits and is decided again when the slot frees; a row that
  needs nothing, or only a CleanEvict, retires that cycle. A CleanEvict never occupies or waits for the bank
  (`applyDrop` panics if it did).
- A force/wb starts at max(now, bank busy-until) and holds the slot until then. An opp sits in the slot until a step
  finds the bank idle (no demand access the previous cycle, no operation running), or the next op replaces it
  (`oppReplaced`); a slot opp whose row changed is dropped (`oppStale`).
- Revisit check per row against T_sweep (`setVisitInterval`, `maxSetVisitCycles`, `visitIntervalOverruns`);
  `daemonSweepCycles` samples each bank's sweep.
- Directed tests (`tests/retention/run_tests.sh`, cases `line_*`): F 27 and T_guard 1924, every deadline action at epoch
  age 27 (true age 88.7–93.3% of DRT), sweeps of 384 cycles, CleanEvicts do not slow the sweep, and the worst case
  (every row force-refreshed with a 4-cycle operation) revisits every 1,536 cycles, within T_sweep 1,920.

**What changes results and what does not.**
- Modeled, changes results: F 29 → 27 (drops and forced refreshes about 2 epochs earlier); 2 banks (a refresh blocks
  half the hits instead of an eighth); the per-bank line scanner (revisits every 384+ cycles instead of about 64, so
  actions land later in the window); the single slot (an opp waits or is replaced; only rows needing the bank wait).
  The LINE budget of 4 acts only through F. Measured step by step in `rtl_align/sweep/results_rtl2/report.md`.
- Matching only, no effect in gem5: sense-amp refresh (no latch, same 2-cycle bank time); the 1-cycle stamp read with
  `lineState` bypass and `scan_kill` (gem5 decides on current state, i.e. a perfect bypass, and a killed row was just
  filled or refreshed, so it would get no action); the metadata contract (gem5 models a compliant cache); write-buffer
  grants across banks (2 scanners, 1 line per cycle each, cannot exceed min(2, free)); `DRT_CYCLES` = 30,030 (already
  used); `clr_used_en` tied to 0 (no clear age, as in CLK); `ifndef SYNTHESIS`.
- Limitations 1–5 of §3c still apply (opp issue is judged on the previous cycle's demand; fills and snoops do not
  wait for bank operations; writeback data copied at the decision; one-cycle offsets).

## 4. Metadata ledger

Everything the model assumes, and what it would cost in hardware. **Rule: nothing new gets in for free.** Every
mechanism must be listed here with its bits and ports.

| Item | In the simulator | In hardware | Cost | Status |
|---|---|---|---|---|
| Per-line age (time since the last full-line write) | `fullChargeTick`, exact 64-bit tick | a b-bit age counter per line plus a global epoch counter; decisions would round conservatively | b × 768 bits for 48 KiB (b = 3: 288 B; b = 4: 384 B) | **free in the simulator, not yet modeled.** Results assume perfect age knowledge. Future: `retention_age_bits` |
| Per-line age, RTL-aligned (`quantized_age`) | stamp = epoch of `fullChargeTick` mod 2^5, compared in epochs of 1024 cycles | a 5-bit stamp per line plus a 10-bit cycle counter and a 5-bit epoch counter | 5 × 768 = 3,840 bits (480 B) plus 15 bits | rtl_align; supersedes the exact age when on |
| Clean deadline drop, announced | `evictBlock` (CleanEvict, one write-buffer entry) | valid-bit clear + an address-only write-buffer entry (`ce_mask`) | 0 new bits; one more 12-bit mask on the scanner-cache interface | rtl_align (silent drop: off, see §3c) |
| Top-MRU order | `lastTouchTick` | the L1D's existing LRU replacement state, updated by the same events (hit, fill) | 0 extra **only with true LRU** (gem5 `LRURP`, used in all runs). A real 12-way L1D uses tree-PLRU: there only top-1 is exact (follow the inverted node bits from the root); top-k > 1 is not available | **open (user, 2026-10-03)**: top_mru 4 is not free under PLRU; alternatives top_mru 1, or a per-line reference bit (`cold_dirty=touched`) |
| Dirty, valid, coherence | existing gem5 bits | existing | 0 extra | — |
| Bank of a line | set mod B | 3 low set-index bits (address) | 0 | — |
| Per-bank busy | `bankBusyUntil[B]` | a down-counter per bank (a refresh lasts 8 cycles) | 8 × 4 = 32 bits total | added in step 6 |
| Scanner state | `refreshSetIdx` | 6-bit set pointer + FSM | about 10 bits | since step 4 |
| Per-bank last-access (idle detect) | `bankLastAccess[B]` | "bank accessed this cycle" signal from the decoder | 0 stored | — |
| Stats-only flags | `wasOppRefreshed` | not hardware | — | stats only |
| Active invalidation: clear a line's valid bit | `evictBlock` (CleanEvict) | a tag-side write in the scanned set, like the age reset of a refresh | 0 new bits | active_invalidate |
| Active invalidation: keep Shared lines | `WritableBit` | the coherence state, read with the tag bits the scanner already reads | 0 new bits, no MSHR connection | active_invalidate |
| Cold dirty writeback, `cold_dirty=mru` | top-MRU order | the existing LRU state | 0 new bits; the writeback reads the line in its bank | experiment |
| Cold dirty writeback, `cold_dirty=touched` | `lastTouchTick > fullChargeTick` | **a reference bit per line**: set by a hit, cleared by a fill or refresh (CLOCK-like, but cleared per charge, not per scan) | **768 bits** (96 B) | experiment; new metadata, needs the user's approval |
| Stamps, RTL2 | the same stamp from `fullChargeTick` | per-bank GC-eDRAM macro `gcStampArray`, 384 × 5 bits, synchronous read (rewritten at every fill and refresh, so a live row's stamp is refreshed within DRT) | 2 × 384 × 5 = 3,840 bits, as before, now GC-eDRAM instead of flip-flops | RTL2 |
| Scanner metadata reads, RTL2 | free (gem5 reads current state) | each of the 2 scanners reads one row's `md_valid/md_dirty/md_writable` per cycle from the tag array: **2 scanner read ports** (or banked tag metadata), next to the demand lookups | ports, not bits | **open, to state**: the old scanner read one set (12 ways) through one port |
| Per-bank scanner state, RTL2 | `scanRow`, `slotFreeAt`, `pendingOpp` | 2 × (9-bit row pointer + pipeline regs) + one op slot per bank (valid, is_opp, is_wb, 9-bit row) | about 50 bits | RTL2; replaces the three 12-bit pending masks per bank and the 512-bit refresh latch per bank (sense-amp refresh) |
| Revisit check, invalidated-address set | `lastVisit[S]`, `invalidatedAddrs`, `inFlight()` check | not hardware | — | stats only |

**Area note for the equal-area claim.** 48 KiB of SRC has 768 lines against 512 for 32 KiB of SRAM. So its **tag array**,
which must be SRAM because it cannot forget, is 50% larger (about 44 bits per line: tag, state, LRU), plus the age bits.
The claim "48 KiB SRC in the area of 32 KiB SRAM" has to include that.
