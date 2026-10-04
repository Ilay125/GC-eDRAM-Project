# SRC 48 KiB (RTL-aligned) vs SRAM 32 KiB

A = SRAM 32 KiB 8-way 4-cycle (baseline, iso-area with the SRC). C0 = SRAM 48 KiB 12-way 5-cycle (ideal 48 KiB). RTL = SRC 48 KiB 12-way 5-cycle, DRT 10 µs, CLK + silent clean drops + quantized ages (F 29). Δ = change vs A. Single SimPoints, not weighted.

## IPC

| SimPoint | A (SRAM 32) | C0 (SRAM 48) | RTL (SRC 48) | Δ C0 | Δ RTL |
|---|---|---|---|---|---|
| palm sp0 | 0.8168 | 0.8122 | 0.8125 | -0.56% | -0.53% |
| flightdm sp0 | 0.4674 | 0.4666 | 0.4805 | -0.16% | +2.80% |
| roms sp3 | 0.4314 | 0.4254 | 0.4263 | -1.38% | -1.18% |
| zstd sp0 | 0.6953 | 0.6907 | 0.6896 | -0.66% | -0.82% |
| cpython sp4 | 1.1720 | 1.1646 | 1.1603 | -0.63% | -1.00% |

## L1D primary MPKI

| SimPoint | A (SRAM 32) | C0 (SRAM 48) | RTL (SRC 48) | Δ C0 | Δ RTL |
|---|---|---|---|---|---|
| palm sp0 | 22.095 | 22.091 | 22.095 | -0.02% | +0.00% |
| flightdm sp0 | 22.053 | 20.834 | 21.733 | -5.53% | -1.45% |
| roms sp3 | 66.254 | 62.517 | 62.521 | -5.64% | -5.64% |
| zstd sp0 | 25.236 | 24.176 | 24.604 | -4.20% | -2.50% |
| cpython sp4 | 1.524 | 0.101 | 0.819 | -93.36% | -46.29% |

## L1D demand MPKI

| SimPoint | A (SRAM 32) | C0 (SRAM 48) | RTL (SRC 48) | Δ C0 | Δ RTL |
|---|---|---|---|---|---|
| palm sp0 | 174.677 | 174.657 | 174.677 | -0.01% | +0.00% |
| flightdm sp0 | 45.040 | 43.305 | 45.269 | -3.85% | +0.51% |
| roms sp3 | 384.944 | 379.346 | 379.224 | -1.45% | -1.49% |
| zstd sp0 | 46.502 | 45.176 | 45.754 | -2.85% | -1.61% |
| cpython sp4 | 3.613 | 0.215 | 1.348 | -94.06% | -62.70% |

## L2 accesses /kinst

| SimPoint | A (SRAM 32) | C0 (SRAM 48) | RTL (SRC 48) | Δ C0 | Δ RTL |
|---|---|---|---|---|---|
| palm sp0 | 22.095 | 22.091 | 22.095 | -0.02% | +0.00% |
| flightdm sp0 | 37.917 | 36.588 | 37.530 | -3.51% | -1.02% |
| roms sp3 | 66.577 | 62.836 | 62.840 | -5.62% | -5.61% |
| zstd sp0 | 25.260 | 24.105 | 24.536 | -4.57% | -2.87% |
| cpython sp4 | 11.186 | 9.761 | 10.490 | -12.74% | -6.22% |

## L2 bus packets /kinst

| SimPoint | A (SRAM 32) | C0 (SRAM 48) | RTL (SRC 48) | Δ C0 | Δ RTL |
|---|---|---|---|---|---|
| palm sp0 | 66.285 | 66.272 | 44.251 | -0.02% | -33.24% |
| flightdm sp0 | 113.903 | 109.944 | 100.939 | -3.48% | -11.38% |
| roms sp3 | 199.733 | 188.520 | 185.035 | -5.61% | -7.36% |
| zstd sp0 | 75.778 | 72.598 | 70.235 | -4.20% | -7.31% |
| cpython sp4 | 33.558 | 29.283 | 31.096 | -12.74% | -7.34% |

## MPKI gain kept by the SRC (primary MPKI)

(A − RTL) / (A − C0): the share of the ideal 32→48 KiB miss reduction the SRC keeps.

| SimPoint | A − C0 | A − RTL | kept |
|---|---|---|---|
| palm sp0 | 0.004 | 0.000 | – (no gap) |
| flightdm sp0 | 1.219 | 0.320 | 26% |
| roms sp3 | 3.738 | 3.734 | 100% |
| zstd sp0 | 1.060 | 0.632 | 60% |
| cpython sp4 | 1.423 | 0.706 | 50% |
