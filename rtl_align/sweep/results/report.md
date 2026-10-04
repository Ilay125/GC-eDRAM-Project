# RTL-aligned SRC sweep (SimPoint-weighted)

Benchmarks complete: 8 of 13 (incomplete: fotonik3d_r, sqlite_r, roms_r, nest_r, gcc_r)

Configs: **A** = SRAM 32 KiB 4c; **C0** = SRAM 48 KiB 5c; **C1** = SRC 48 KiB C1 (exact, top-4 MRU); **CLK** = SRC 48 KiB CLK (exact, CleanEvict); **RTL** = SRC 48 KiB RTL-aligned. CLK runs exist for 11 benchmarks only (older binary, before the write-buffer fix).

## IPC

| bench | IPC A | C0 vs A | C1 vs A | CLK vs A | **RTL vs A** | RTL vs C0 | RTL vs CLK |
|---|---|---|---|---|---|---|---|
| palm_r | 0.8957 | -0.76% | -0.61% | -0.75% | **+0.44%** | +1.21% | +1.19% |
| flightdm_r | 0.4459 | -1.28% | -1.92% | -0.60% | **+1.63%** | +2.94% | +2.24% |
| femflow_r | 1.1547 | +1.98% | +1.94% | – | **+1.90%** | -0.08% | – |
| cactus_r | 0.4725 | -4.01% | -4.01% | -3.91% | **-3.89%** | +0.12% | +0.02% |
| cpython_r | 1.2255 | -0.74% | -0.82% | -0.97% | **-0.98%** | -0.24% | -0.00% |
| zstd_r | 0.8665 | -0.52% | -0.53% | -0.44% | **-0.37%** | +0.15% | +0.07% |
| sealcrypto_r | 1.2832 | -0.88% | -0.89% | -0.91% | **-0.94%** | -0.06% | -0.02% |
| omnetpp_r | 0.5283 | -1.01% | -1.27% | – | **-1.03%** | -0.02% | – |
| **geomean** | | -0.91% | -1.03% | -1.27% | **-0.42%** | +0.50% | +0.58% |

CLK geomean covers its 11 benchmarks only.

## Primary L1D MPKI and the gain kept

Primary MPKI = demand MSHR misses (real L2 fetches). Kept = (A − X) / (A − C0).

| bench | A | C0 | C1 | CLK | RTL | kept C1 | kept CLK | **kept RTL** |
|---|---|---|---|---|---|---|---|---|
| palm_r | 21.83 | 16.00 | 17.64 | 16.77 | 16.77 | 72% | 87% | **87%** |
| flightdm_r | 25.82 | 24.39 | 25.46 | 25.28 | 25.27 | 25% | 38% | **39%** |
| femflow_r | 13.62 | 12.49 | 12.52 | – | 13.10 | 98% | – | **46%** |
| cactus_r | 103.83 | 98.01 | 100.13 | 99.54 | 99.55 | 64% | 74% | **74%** |
| cpython_r | 1.14 | 0.07 | 0.22 | 0.55 | 0.55 | 86% | 55% | **55%** |
| zstd_r | 12.49 | 12.03 | 12.39 | 12.41 | 12.42 | 20% | 16% | **14%** |
| sealcrypto_r | 5.92 | 5.87 | 5.87 | 5.95 | 5.94 | 100% | -48% | **-30%** |
| omnetpp_r | 64.49 | 59.97 | 60.86 | – | 60.54 | 80% | – | **87%** |
| **sum** | 249.2 | 228.8 | | | 234.1 | | | **74%** |

## L2 traffic and SRC activity (per kinst)

| bench | L2 bus pkts A | C0 | RTL | CleanEvict A | RTL | refreshes CLK | RTL | drops CLK | RTL | stall cyc RTL | checkers RTL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| palm_r | 78.8 | 61.3 | 59.1 | 23.1 | 15.8 | 19.31 | 19.69 | 5.62 | 5.59 | 3.62 | 0 |
| flightdm_r | 127.5 | 123.1 | 112.3 | 32.2 | 17.5 | 24.60 | 24.80 | 19.82 | 19.49 | 2.40 | 0 |
| femflow_r | 42.6 | 39.2 | 39.8 | 6.1 | 4.8 | – | 8.60 | – | 6.28 | 5.59 | 0 |
| cactus_r | 612.0 | 594.5 | 591.7 | 116.0 | 107.2 | 9.65 | 10.06 | 7.10 | 7.41 | 0.93 | 0 |
| cpython_r | 23.3 | 20.1 | 21.3 | 0.4 | 0.0 | 6.42 | 6.54 | 0.53 | 0.54 | 1.35 | 0 |
| zstd_r | 37.5 | 36.1 | 30.3 | 14.1 | 7.1 | 9.25 | 9.35 | 9.87 | 9.97 | 1.02 | 0 |
| sealcrypto_r | 17.8 | 17.6 | 16.3 | 3.2 | 1.7 | 5.00 | 5.19 | 5.49 | 5.42 | 0.87 | 0 |
| omnetpp_r | 207.1 | 193.7 | 191.6 | 45.4 | 40.2 | – | 17.19 | – | 5.24 | 1.54 | 0 |
