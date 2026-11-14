# SRC retention statistics: what each counter means

Every SRC counter is in the stats group `board.cache_hierarchy.l1dcache.retention.*`. The group exists only
when `drt > 0`; an SRAM run (DRT = 0) has none of these lines.
The code is `gem5/src/mem/cache/retention/retention_manager.cc`; line numbers below refer to branch
`src-rework` at `12c5267e26`.

A line **expires** when `now − fullChargeTick ≥ DRT`. `fullChargeTick` is reset only by a full-line write:

- a fill from L2;
- a daemon refresh;
- an inline refresh.

Stores and reads do not reset it.

The counters fall into six groups:

| Group | Question it answers | Expected |
|---|---|---|
| A. Data loss | Did a *dirty* line expire? (red headers in `backdoors.png`) | **0** |
| B. Harmless backdoors | Did the simulator touch an expired *clean* line in a way hardware couldn't? (black headers) | small |
| C. The real cost of forgetting | How many misses did expiry cause? | the SRC cost |
| D. Refresh activity and stalls | How much did keeping lines alive cost? | the SRC cost |
| E. Inline refresh | How often did a store have to recharge its own line? | small |
| F. Guarantee diagnostics | Is the refresh bound sane? | constants |

**Dirty vs clean is the key distinction.**
- A **clean** line that expires loses nothing, because L2 still has the same data. The only cost is one extra
  miss.
- A **dirty** line that expires held the only up-to-date copy. Its loss is real data corruption, which the
  design must never allow.

`invariantViolations` counts every place a dirty expired line is found. With `--drt_strict` the simulator
panics there instead of counting.

---

## A. Data loss: must be 0 (red headers)

Each of these also increments `invariantViolations`.

| Stat | When it counts (code) | What the simulator then does | Meaning |
|---|---|---|---|
| `lazyWritebacksRead` | A **read** finds its line expired and dirty (`expireOnAccess`, l.160–166) | Writes the dead line back to L2 as if it were valid (the *lazy writeback*), invalidates it, and the read misses | **Fallback backdoor.** Real hardware would write back garbage. It is kept so runs finish, and counted to show it never fires. |
| `lazyWritebacksWrite` | Same, but for a **store** (l.162–163) | Same as above | Before the rework, stores to expired lines hit silently ("B3"). Now they take the same path and are counted. |
| `lazyWritebacks` | Formula: read + write | | |
| `expiredDirtyEvictions` | The victim chosen for replacement is expired and dirty (`onEvict`, l.261–263) | Writes it back normally (dead data goes to L2) | The line died before anyone touched it again, and it is thrown out with its lost data. |
| `daemonRevivedDirty` | The daemon reaches a dirty line that has *already* expired (`processRefreshEvent`, l.372–377) | Refreshes it anyway, which "revives" it | The daemon came back too late. The refresh makes lost data look valid again. |
| `invariantViolations` | Any of the above, plus the dirty cases of groups B1, B3 and B4 (`violation()`, l.97–103) | Counts, or panics with `drt_strict` | **The single number to check.** 0 means no dirty data was ever lost. |

**Result in the DRT sweep:** all 0, in every benchmark at every DRT, with top_mru 4 and top_mru 0.

---

## B. Harmless backdoors: expired clean lines (black headers)

These are places where the simulator either
- uses a line that has expired but is **clean**, so it does something real hardware could not; or
- deliberately takes the conservative path and counts it.

None of them loses data while `invariantViolations` = 0: every such line was clean, so its contents
equal L2's copy. If the line were dirty, the event would also count as a violation (group A).

### B1. `expiredInflightHits`: expired line with a request already in flight
- **When:** a read or store finds its line expired (or too late, see B2), but the MSHR queue or write buffer already
  has an entry for that same line (`expireOnAccess`, l.142–149). This can happen in the O3 core, for example
  when a store upgrade or a write-back of this line is still pending.
- **What the simulator does:** leaves the line in place and serves the access **as a normal hit**. Invalidating a
  line that has an outstanding MSHR would break gem5's MSHR bookkeeping.
- **What hardware would do:** notice the expiry and wait for the in-flight request, like any access to a line
  already being fetched.
- **Effect:** timing only. The access gets hit latency instead of waiting, which is optimistic. The value it
  returns is correct, because the line is clean.
- **Sweep:** 0 everywhere.

### B2. `inlineTooLate`: a store arrived in the last few cycles of a line's life
- **Background:** a store to a line close to expiry (remaining life < T_guard) does an **inline refresh**:
  1. read the whole line;
  2. merge the store;
  3. write the full line back, which recharges it.

  Step 1 takes `inline_refresh_cycles` (default = data latency = 4 cycles).
- **When:** the line has not expired yet, but has **less than those 4 cycles** of life left, so it would die during
  the read (`expireOnAccess`, l.128–136).
- **What the simulator does:** treats the line as expired. It invalidates the line (lazy writeback if dirty) and the
  store **misses**, so the line is refetched from L2. This counter is also included in `retentionMisses`.
- **This is not a backdoor at all:** it's the strict, correct handling, counted separately because it marks a spot
  where the guarantee was exactly at its edge.
- **Why it's rare:** the store has to land in a ~1.3 ns window at the end of a 5 µs life, on a line the daemon was not
  keeping alive (clean, not top-MRU).
- **Sweep:** 2 in total (sqlite and zstd, at 5 µs). Both lines were clean, so each cost one extra miss and nothing else.

### B3. `expiredSnoops`: a coherence snoop reached an expired line
- **When:** a snoop request arrives at the L1D for a line it holds that has expired (`onSnoop`, called from
  `Cache::handleSnoop`, `cache.cc` l.1058). Snoops come from other agents on the coherent L2 crossbar, such as
  the instruction cache or the page-table walker, touching a line the L1D also holds.
- **What the simulator does:** handles the snoop as usual. In gem5 a line answers a snoop **with data only if it
  is dirty** (`cache.cc`, `respond = blk->isSet(DirtyBit) && ...`). A clean line only has its state changed:
  invalidated, or made non-writable. So an expired clean line never supplies data.
- **Effect:** none on values or timing that matters. The line is dead either way, and the snoop at most removes it
  or downgrades it.
- **Sweep:**
  - 820 in total with top_mru 4 (flightdm 234 at 5 µs is the largest; cpython, sqlite, roms, nest, fotonik3d have tens);
  - 7,783 with top_mru 0, because more expired clean lines sit in the cache.

### B4. `expiredFunctional`: a gem5-internal access touched an expired line
- **When:** a **functional** access finds an expired line (`onFunctional`, called from
  `BaseCache::functionalAccess`, `base.cc` l.785). Functional accesses aren't hardware traffic: they are gem5 reading
  or writing memory instantly, bypassing timing. In SE mode the main source is **system-call emulation**: `read()`
  and `write()` copy user buffers through the functional path. The loader and debugging are others.
- **What the simulator does:**
  - a functional **read** takes the value from the expired line; since it's clean, the value equals L2's copy;
  - a functional **write** updates every copy (this line, L2, memory).
- **Effect:** none on results. No real hardware operation corresponds to it, and the value is correct.
- **Sweep:** about 315 per DRT, **nest only**. Most likely nest's file output (syscalls on buffers still in the L1D); not verified.

---

## C. The real cost of forgetting

| Stat | Meaning |
|---|---|
| `retentionMisses` | Reads or stores whose line was present but expired, so they **missed** and refetched from L2 (`expireOnAccess`, l.151). Includes `inlineTooLate`. This is **the** cost of SRC: capacity that was there but had forgotten. `analyze.py` reports it as `rmiss_frac` = retentionMisses / demand accesses. |
| `expiredCleanEvictions` | Replacement victims that had already expired but were clean (`onEvict`, l.265). No data loss and no extra miss: the line was going to be thrown out anyway. It shows how many lines die without being touched again. |
| `expiredHitPot` | Retention misses whose line had died **recently**, less than 1.2 × DRT after its last charge (l.154–156). These misses a slightly longer DRT, or one more refresh, would have saved. |

## D. Refresh activity and stalls

The daemon visits one set per step. It scans the tags (`refresh_set_scan_cycles`), then refreshes the chosen lines
one after another. Each refresh reads and rewrites the line, and occupies the data array for `refresh_line_cycles`
(default 2 × data latency = 8 cycles). Which lines it considers:
- every dirty line (`--refresh_dirty`);
- the `top_mru` most-recently-touched valid lines of the set.

| Stat | Meaning |
|---|---|
| `forceRefresh` | Refreshes forced by the guarantee: the line would expire before the daemon's next visit (remaining life < T_guard, `maybeRefresh` l.352). These happen whatever the load. |
| `oppRefresh` | Opportunistic refreshes: the line is older than `refresh_opp_age` × DRT (default 0.8) and the data array is idle, meaning no demand access this cycle and no refresh in progress (l.354). |
| `totalRefreshes` | forced + opportunistic daemon refreshes. Each is **one line read + one line write** (for the energy model). Inline refreshes are counted separately (group E). |
| `ageAtForceRefresh` | Distribution of line age at a forced refresh, as a fraction of DRT. It sits at 1 − T_guard/DRT: about 0.57 at 5 µs and 0.77 at 10 µs. This is "how early we refresh". |
| `refreshStalledHits` | Hits that found the data array busy with a refresh and had to wait (`hitDelay`, l.199–203). |
| `refreshStallCycles` | Total cycles those hits waited. **This is what costs the IPC** (correlation 0.84 with the IPC loss). |
| `refreshedBlockUtility` | Hits on a line whose last recharge was a daemon refresh; counted once per refresh, on the first such hit (l.181–184). A refresh with no later hit was wasted. (The flag is named `wasOppRefreshed` but is set for forced refreshes too.) |
| `daemonSweepCycles` | Histogram of how long a full sweep over all 64 sets actually took. Compare with `tSweepCycles`: e.g. mean 66 vs the bound 6,208 for palm at 5 µs. |

## E. Inline refresh (store-triggered)

| Stat | Meaning |
|---|---|
| `refreshInlineWrite` | Store hits on a line with remaining life < T_guard. The store recharges the line itself (read, merge, write the full line) and adds `inline_refresh_cycles` of latency (`hitDelay`, l.213–234). This covers the case where a store dirties a line just after the daemon passed its set. |
| `refreshInlineRead` | Same, triggered by a read hit. Only with `--inline_refresh_on_read`; off by default, so 0. |
| `ageAtInlineRefresh` | Line age at an inline refresh, as a fraction of DRT. |
| `cleanToDirtyInDanger` | Inline refreshes where the store made a **clean** line dirty inside T_guard. These are exactly the stores that would have become lost data without inline refresh. |
| `inlineRefreshCycles` | Total latency added to stores by inline refreshes. |
| `inlineTooLate` | See B2. |

## F. Guarantee diagnostics (constants per run)

| Stat | Meaning |
|---|---|
| `tSweepCycles` | The worst-case time the guarantee assumes for the daemon to come back to a set: numSets × (scan + k_max × line), with k_max = assoc if `--refresh_dirty`, else top_mru. 64 × (1 + 12 × 8) = **6,208** cycles for the 48 KiB 12-way sweep configuration. |
| `tGuardCycles` | Force-refresh threshold on remaining life: T_sweep + line + margin × DRT. At 5 µs (15,000 cycles) it is 6,516 cycles, so lines are forced at 56.6% of DRT. If T_guard ≥ DRT the run refuses to start. |

---

## Where these appear
- `src_sweep/analyze.py` prints groups A and B per benchmark and DRT, and draws them in `results/backdoors.png`.
  In that chart, red headers are group A; black headers are group B; the grey column is all L1D writebacks, for scale.
- Weighted per kilo-instruction in `results/results.csv`: `rmiss_pki`, `force_pki`, `opp_pki`, `inline_pki`,
  `stall_pki`, `rmiss_frac`, `refresh_pki`.
- Raw sums over SimPoints in `results/results.csv`: the group A/B counters and `l1d_writebacks`.
