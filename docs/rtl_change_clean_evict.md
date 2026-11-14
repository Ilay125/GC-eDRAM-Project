# RTL change: announce clean drops (CleanEvict) instead of dropping them silently

Applies to `docs/SRC_controller_RTL_guide.md` and the `scanner` / `srcCtrl` SystemVerilog.

## Why

The gem5 model the thesis reports uses an **exact snoop filter** below the L1D (the L2 bus snoop filter). It forgets a
line only when the L1 announces the eviction: a CleanEvict for a clean line, a writeback for a dirty one. A silent drop
leaves a stale "L1 holds it" entry that is never removed. In gem5 those entries leak until the filter panics (8 of 93
SPEC runs: "snoop filter exceeded capacity of 131072 cache blocks"). Silent drops also make the SRC send fewer L2
messages than the SRAM baselines, which announce every clean eviction.

So the SRC uses the same protocol as every other cache in the system: **every clean line it drops is announced with an
address-only CleanEvict that takes a write-buffer entry**, exactly like the cache's own clean replacements.

## What changes in behaviour

Only the deadline outcome of a **clean, unkept** line changes. Everything else stays as it is: the per-line state, the
keep rules, the opportunistic refresh, the bank scheduling, `bankExec`, `lineState`, `epochCtr`.

| Condition at the deadline (age ≥ 29) | Before | After |
|---|---|---|
| kept (`used`, or Shared/Owned) | force | force (unchanged) |
| not kept, **clean**, write-buffer slot free | inv (silent): no bank time, no slot | **inv + CleanEvict**: no bank time, **1 slot** (address only, no data) |
| not kept, **clean**, buffer full | inv (silent) | **force** (fallback refresh, decided again one DRT later) |
| not kept, dirty, slot free | wb + inv: LINE of bank time, 1 slot | unchanged |
| not kept, dirty, buffer full | force (fallback) | unchanged |

Slots are handed out **in way order over all drops, clean and dirty together**: the first `wbuf_free` unkept deadline
lines of the set get a slot, and the rest are refreshed. This is what gem5 does: one pass over the ways, and each drop
allocates its write-buffer entry before the next way is checked.

A CleanEvict reads no data, so it needs **no bank operation**: `bankSched` and `bankExec` don't change.

## Changes to the document, section by section

### §2.1 block diagram
Edge label `sc -- "inv / wb masks" --> cache` becomes `sc -- "inv / wb / ce masks" --> cache`.

### §2.3 "The life of one line", item 5
Replace the bullet
> **clean, not kept** → silently invalidated;

with
> **clean, not kept** → invalidated, and a CleanEvict (address only) is sent to L2 through a write-buffer entry (or refreshed if the write buffer is full);

### §4.3 decision table
Replace the row
| age ≥ 29, not kept, clean | **inv** (silent drop) | none | none |

with two rows:
| age ≥ 29, not kept, clean, slot free | **inv + ce** (CleanEvict, address only) | none | 1, reserved now |
| age ≥ 29, not kept, clean, buffer full | **force** (fallback refresh, decided again one DRT later) | LINE | – |

Replace the sentence under the table with:
> Write-buffer slots are handed out **in way order over all drops, clean and dirty**: the first `wbuf_free` unkept deadline lines of the set get a slot (dirty → wb, clean → ce); the rest are force-refreshed.

### §4.4 rules about timing
Replace the bullet "**Silent clean drops.** …" with:
> - **Announced clean drops.** A clean line dropped at its deadline is announced to L2 with an address-only CleanEvict through a write-buffer entry, like every clean eviction of the cache. Protocol assumption: the level below keeps an exact record of what L1 holds (an exact snoop filter), so every eviction must be announced.

### §8 scanner: parameters and ports
- Parameters: unchanged. `WBUF_SIZE` now limits clean drops too.
- Port table: add one output row and change two descriptions.

| Signal | Dir | Width | From / to | Description |
|---|---|---|---|---|
| `wb_mask` | out | 12 | `bankSched`, cache | Dirty drops: write back (cache reserves an entry now, data read later by the bank) |
| `ce_mask` | out | 12 | cache | **New.** Clean drops: send a CleanEvict (cache reserves an entry now, address only, no data) |
| `inv_cache_mask` | out | 12 | cache | Invalidate these ways now (= `wb_mask \| ce_mask`) |
| `wbuf_free` | in | 4 | cache | Free write-buffer entries the scanner may claim this cycle; must already reflect last cycle's `wb_mask` and `ce_mask` reservations |

- Logic text: "Only `wb_cnt` chains across ways (first N dirty drops get a slot)" becomes "Only `slot_cnt` chains across ways (the first N drops, clean or dirty, get a slot)".

### §8 scanner: code
In the port list, after `wb_mask`, add:
```systemverilog
    output logic [NUM_WAYS-1:0]                  ce_mask,
```

Replace the declaration of the internal decisions and the whole per-way `always_comb` block with:
```systemverilog
    // Internal (ungated) decisions
    logic [NUM_WAYS-1:0] force_d, opp_d, wb_d, ce_d, inv_d;

    // ---------------- Per-way decision ----------------
    always_comb begin
        logic [STAMP_BITS-1:0] age;
        logic                  deadline, keep_opp, keep_dead, cand_drop, slot;
        logic [WBUF_BITS-1:0]  slot_cnt;               // write-buffer slots granted so far

        force_d  = '0;
        opp_d    = '0;
        wb_d     = '0;
        ce_d     = '0;
        inv_d    = '0;
        slot_cnt = '0;

        for (int way = 0; way < NUM_WAYS; way++) begin
            age       = epoch - stamps_set[way];                 // mod 2^STAMP_BITS
            deadline  = md_valid[way] & (age >= DEADLINE_AGE);

            keep_opp  = used_set[way];                           // | mru when TOP_MRU
            keep_dead = keep_opp | ~md_writable[way];            // Shared/Owned kept at deadline

            // Every unkept deadline line leaves the cache and needs a slot:
            // dirty -> writeback (data), clean -> CleanEvict (address only)
            cand_drop = deadline & ~keep_dead;
            slot      = cand_drop & (slot_cnt < wbuf_free);      // first free slots, way order
            slot_cnt  = slot_cnt + slot;

            force_d[way] = deadline & (keep_dead | (cand_drop & ~slot));  // kept, or no slot
            wb_d[way]    = slot &  md_dirty[way];
            ce_d[way]    = slot & ~md_dirty[way];
            inv_d[way]   = slot;                                          // every granted drop
            opp_d[way]   = md_valid[way] & ~deadline & keep_opp & (age >= OPP_AGE);
        end
    end
```

In the output gating, add:
```systemverilog
    assign ce_mask        = commit ? ce_d    : '0;
```

Nothing else in the module changes. The only register is still `set_ptr`, and no flops are added. The single-cycle
path is the same length: one more AND per way, and the slot chain now counts clean drops too.

### §9 bankSched, §10 bankExec, §7 lineState, §6 epochCtr
No change. `ce_mask` is **not** connected to `bankSched`: a CleanEvict has no bank operation. A clean line that
falls back to a forced refresh arrives as a normal `force_mask` bit.

### §11.1 internal wiring
Add the row:
| `scanner.ce_mask` | clean drops | cache |

### §11.2 external interface of `srcCtrl`
The "To cache" row becomes:
| To cache | `scan_set`, `commit`, `inv_cache_mask`, `wb_mask`, `ce_mask` | Apply invalidations, reserve write-buffer entries (writeback or CleanEvict) |

### §13 what the cache must guarantee
Item 2 becomes:
> 2. For each `wb_mask` bit, reserve a write-buffer entry at the commit edge ("data pending") and capture `sa_data` when `wb_data_valid`. For each `ce_mask` bit, at the same edge, put a CleanEvict for that line (address = the way's tag + `scan_set`, read before the invalidation at that edge) into a write-buffer entry; it carries no data and may leave at once. Update `wbuf_free` for the next cycle with both kinds of reservation.

Item 4 becomes:
> 4. Every clean drop is announced (CleanEvict), so the level below keeps an exact record of what L1 holds, as for the cache's own clean replacements.

### §14.1 unit tests, `scanner` row
Replace "3 dirty drops with `wbuf_free` = 2 → lowest two get wb, third force" with:
> 3 dirty drops with `wbuf_free` = 2 → lowest two get wb, third force; 3 clean drops with `wbuf_free` = 2 → lowest two get ce, third force; mixed: clean way 1, dirty way 3, clean way 5 with `wbuf_free` = 2 → way 1 ce, way 3 wb, way 5 force; `wbuf_free` = 0 → every unkept deadline line forced, `ce_mask` = `wb_mask` = 0; a kept line never gets ce

### §14.2 system test
Add to the checks:
> - every invalidated clean line produces exactly one CleanEvict, and every invalidated dirty line exactly one writeback (no line leaves the cache unannounced);

### §14.3 properties, scanner bullet
Replace it with:
> - Scanner: at most one outcome per way; every valid deadline way gets exactly one of force / wb / ce; `wb_mask & ce_mask == 0`; `inv_cache_mask == (wb_mask | ce_mask)`; `popcount(wb_mask | ce_mask) ≤ wbuf_free`; `ce_mask` only on clean ways and `wb_mask` only on dirty ways; opp never on a Shared line with used = 0.

### §15 open questions
- Row 6 becomes answered: "Silent clean drops → no: gem5's exact snoop filter leaks stale entries and panics (8 of 93 SPEC runs). Clean drops are announced (CleanEvict); see `docs/rtl_change_clean_evict.md`."
- Row 8, add: "fallback refreshes now include clean drops that found the buffer full (gem5 stat `activeWbFullKept`)."

## Matching gem5 configuration
Branch `rtl_align`, binary `bin/gem5.fast.rtl_align`: the CLK flags plus `--quantized_age --age_epoch_log2=10
--age_bits=5 --guard_sweeps=1`, **without** `--silent_clean_drop`. Clean drops then take the gem5 path in
`RetentionManager::invalidateUnkept`: `evictBlock` makes a CleanEvict, and `doWritebacks` puts it in a write-buffer
entry. If `writeBuffer.isFull()`, the line is force-refreshed instead (`activeWbFullKept`). Counters:
`activeInvalidations` (clean drops announced), `coldDirtyWritebacks` (dirty drops), `activeWbFullKept` (fallback
refreshes, clean and dirty), and `l2bus.transDist::CleanEvict` on the L2 bus.
