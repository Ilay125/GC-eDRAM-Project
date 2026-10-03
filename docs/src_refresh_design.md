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

## 4. Metadata ledger

Everything the model assumes, and what it would cost in hardware. **Rule: nothing new gets in for free.** Every
mechanism must be listed here with its bits and ports.

| Item | In the simulator | In hardware | Cost | Status |
|---|---|---|---|---|
| Per-line age (time since the last full-line write) | `fullChargeTick`, exact 64-bit tick | a b-bit age counter per line plus a global epoch counter; decisions would round conservatively | b × 768 bits for 48 KiB (b = 3: 288 B; b = 4: 384 B) | **free in the simulator, not yet modeled.** Results assume perfect age knowledge. Future: `retention_age_bits` |
| Top-MRU order | `lastTouchTick` | the L1D's existing LRU replacement state, updated by the same events (hit, fill) | 0 extra | reused |
| Dirty, valid, coherence | existing gem5 bits | existing | 0 extra | — |
| Bank of a line | set mod B | 3 low set-index bits (address) | 0 | — |
| Per-bank busy | `bankBusyUntil[B]` | a down-counter per bank (a refresh lasts 8 cycles) | 8 × 4 = 32 bits total | added in step 6 |
| Scanner state | `refreshSetIdx` | 6-bit set pointer + FSM | about 10 bits | since step 4 |
| Per-bank last-access (idle detect) | `bankLastAccess[B]` | "bank accessed this cycle" signal from the decoder | 0 stored | — |
| Stats-only flags | `wasOppRefreshed` | not hardware | — | stats only |
| Active invalidation: clear a line's valid bit | `evictBlock` (CleanEvict) | a tag-side write in the scanned set, like the age reset of a refresh | 0 new bits | active_invalidate |
| Active invalidation: keep Shared lines | `WritableBit` | the coherence state, read with the tag bits the scanner already reads | 0 new bits, no MSHR connection | active_invalidate |
| Revisit check, invalidated-address set | `lastVisit[S]`, `invalidatedAddrs`, `inFlight()` check | not hardware | — | stats only |

**Area note for the equal-area claim.** 48 KiB of SRC has 768 lines against 512 for 32 KiB of SRAM. So its **tag array**,
which must be SRAM because it cannot forget, is 50% larger (about 44 bits per line: tag, state, LRU), plus the age bits.
The claim "48 KiB SRC in the area of 32 KiB SRAM" has to include that.
