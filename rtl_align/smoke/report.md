# RTL-alignment smoke runs (strict)

CLK = reference (wbfix binary, exact ages, CleanEvict drops); CLK-SD = + silent clean drops; CLK-RTL = + quantized ages (1024-cycle epochs, 5-bit stamp, T_guard 258, F 29).

## palm_r_sp0

Status: CLK ok, CLK-SD ok, CLK-RTL ok

| | CLK | CLK-SD | CLK-RTL |
|---|---|---|---|
| IPC | 0.8122 | 0.8125 | 0.8125 |
| L1D demand MPKI | 174.678 | 174.677 | 174.677 |
| L1D primary MPKI | 22.095 | 22.095 | 22.095 |
| refresh forced /kinst | 0.000 | 0.000 | 0.000 |
| refresh opportunistic /kinst | 0.237 | 0.237 | 0.237 |
| refresh fallback (wb full) /kinst | 0.0000 | 0.0000 | 0.0000 |
| refresh Shared kept /kinst | 0.0000 | 0.0000 | 0.0000 |
| drop clean /kinst | 22.031 | 22.031 | 22.031 |
|   of which silent /kinst | – | 22.031 | 22.031 |
| drop dirty (writeback) /kinst | 0.061 | 0.061 | 0.061 |
| L2 accesses /kinst | 22.095 | 22.095 | 22.095 |
| L2 bus CleanEvict /kinst | 44.065 | 22.034 | 22.034 |
| L2 bus WritebackDirty /kinst | 0.118 | 0.114 | 0.114 |
| L2 bus snoops /kinst | 22.090 | 22.087 | 22.087 |
| snoop filter snoops /kinst | 0.000 | 22.033 | 22.034 |
| hit stall cycles /kinst | 0.000 | 0.000 | 0.000 |
| misses to a dropped line /kinst | 22.053 | 22.053 | 22.053 |
|   before it would expire /kinst | 0.000 | 0.000 | 0.000 |
| T_guard (cycles) | 514 | 514 | 258 |
| deadline F (epochs) | – | 0 | 29 |
| opp age (epochs) | – | 0 | 23 |
| epoch age at deadline min-max | – | 0.00 – 0.00 | 29.00 – 29.00 |
| age at forced refresh, mean (% DRT) | nan | nan | nan |
| age at drop, mean (% DRT) | 98.40 | 98.40 | 97.31 |
| age at drop, min-max (% DRT) | 98.29 – 98.50 | 98.29 – 98.50 | 95.48 – 99.10 |
| age at opp refresh, mean (% DRT) | – | 80.11 | 76.83 |
| checker counters (sum) | 0 | 0 | 0 |

Non-zero checker counters: CLK none, CLK-SD none, CLK-RTL none

## flightdm_r_sp0

Status: CLK ok, CLK-SD ok, CLK-RTL ok

| | CLK | CLK-SD | CLK-RTL |
|---|---|---|---|
| IPC | 0.4655 | 0.4782 | 0.4805 |
| L1D demand MPKI | 44.906 | 44.984 | 45.269 |
| L1D primary MPKI | 21.801 | 21.730 | 21.733 |
| refresh forced /kinst | 0.005 | 0.003 | 0.003 |
| refresh opportunistic /kinst | 21.787 | 21.697 | 21.850 |
| refresh fallback (wb full) /kinst | 0.0000 | 0.0000 | 0.0001 |
| refresh Shared kept /kinst | 1.0997 | 0.9564 | 1.0446 |
| drop clean /kinst | 12.065 | 11.796 | 11.872 |
|   of which silent /kinst | – | 11.796 | 11.872 |
| drop dirty (writeback) /kinst | 5.969 | 5.877 | 5.898 |
| L2 accesses /kinst | 37.645 | 37.526 | 37.530 |
| L2 bus CleanEvict /kinst | 27.032 | 14.710 | 14.577 |
| L2 bus WritebackDirty /kinst | 10.499 | 10.274 | 10.260 |
| L2 bus snoops /kinst | 15.853 | 15.187 | 15.115 |
| snoop filter snoops /kinst | 1.363 | 6.423 | 6.448 |
| hit stall cycles /kinst | 2.229 | 2.270 | 2.402 |
| misses to a dropped line /kinst | 18.028 | 17.668 | 17.765 |
|   before it would expire /kinst | 0.032 | 0.020 | 0.021 |
| T_guard (cycles) | 514 | 514 | 258 |
| deadline F (epochs) | – | 0 | 29 |
| opp age (epochs) | – | 0 | 23 |
| epoch age at deadline min-max | – | 0.00 – 0.00 | 29.00 – 29.00 |
| age at forced refresh, mean (% DRT) | 98.46 | 98.46 | 98.76 |
| age at drop, mean (% DRT) | 98.44 | 98.44 | 98.37 |
| age at drop, min-max (% DRT) | 98.29 – 98.50 | 98.29 – 98.50 | 95.48 – 99.10 |
| age at opp refresh, mean (% DRT) | – | 80.26 | 77.45 |
| checker counters (sum) | 0 | 0 | 0 |

Non-zero checker counters: CLK none, CLK-SD none, CLK-RTL none

## roms_r_sp3

Status: CLK ok, CLK-SD ok, CLK-RTL ok

| | CLK | CLK-SD | CLK-RTL |
|---|---|---|---|
| IPC | 0.4254 | 0.4261 | 0.4263 |
| L1D demand MPKI | 379.352 | 379.224 | 379.224 |
| L1D primary MPKI | 62.522 | 62.521 | 62.521 |
| refresh forced /kinst | 0.000 | 0.000 | 0.000 |
| refresh opportunistic /kinst | 25.937 | 25.944 | 28.023 |
| refresh fallback (wb full) /kinst | 0.0001 | 0.0001 | 0.0415 |
| refresh Shared kept /kinst | 0.0000 | 0.0000 | 0.0000 |
| drop clean /kinst | 3.468 | 3.426 | 3.497 |
|   of which silent /kinst | – | 3.426 | 3.497 |
| drop dirty (writeback) /kinst | 3.635 | 3.652 | 3.728 |
| L2 accesses /kinst | 62.841 | 62.841 | 62.840 |
| L2 bus CleanEvict /kinst | 81.819 | 78.248 | 78.173 |
| L2 bus WritebackDirty /kinst | 38.553 | 38.607 | 38.606 |
| L2 bus snoops /kinst | 57.850 | 57.760 | 57.755 |
| snoop filter snoops /kinst | 1.798 | 4.942 | 5.000 |
| hit stall cycles /kinst | 2.530 | 2.541 | 2.538 |
| misses to a dropped line /kinst | 7.096 | 7.071 | 7.220 |
|   before it would expire /kinst | 0.000 | 0.000 | 0.000 |
| T_guard (cycles) | 514 | 514 | 258 |
| deadline F (epochs) | – | 0 | 29 |
| opp age (epochs) | – | 0 | 23 |
| epoch age at deadline min-max | – | 0.00 – 0.00 | 29.00 – 29.00 |
| age at forced refresh, mean (% DRT) | 98.36 | 98.37 | 96.93 |
| age at drop, mean (% DRT) | 98.44 | 98.44 | 98.34 |
| age at drop, min-max (% DRT) | 98.29 – 98.50 | 98.29 – 98.50 | 95.48 – 99.10 |
| age at opp refresh, mean (% DRT) | – | 80.11 | 76.94 |
| checker counters (sum) | 0 | 0 | 0 |

Non-zero checker counters: CLK none, CLK-SD none, CLK-RTL none

## zstd_r_sp0

Status: CLK ok, CLK-SD ok, CLK-RTL ok

| | CLK | CLK-SD | CLK-RTL |
|---|---|---|---|
| IPC | 0.6905 | 0.6898 | 0.6896 |
| L1D demand MPKI | 45.746 | 45.757 | 45.754 |
| L1D primary MPKI | 24.592 | 24.596 | 24.604 |
| refresh forced /kinst | 0.003 | 0.002 | 0.002 |
| refresh opportunistic /kinst | 11.952 | 11.961 | 12.204 |
| refresh fallback (wb full) /kinst | 0.0000 | 0.0000 | 0.0115 |
| refresh Shared kept /kinst | 0.0000 | 0.0000 | 0.0000 |
| drop clean /kinst | 3.571 | 3.576 | 3.645 |
|   of which silent /kinst | – | 3.576 | 3.645 |
| drop dirty (writeback) /kinst | 9.629 | 9.661 | 9.864 |
| L2 accesses /kinst | 24.520 | 24.526 | 24.536 |
| L2 bus CleanEvict /kinst | 10.392 | 6.858 | 6.792 |
| L2 bus WritebackDirty /kinst | 30.357 | 30.287 | 30.291 |
| L2 bus snoops /kinst | 16.159 | 16.128 | 16.127 |
| snoop filter snoops /kinst | 0.078 | 2.666 | 2.712 |
| hit stall cycles /kinst | 1.935 | 1.937 | 2.203 |
| misses to a dropped line /kinst | 12.676 | 12.712 | 12.976 |
|   before it would expire /kinst | 0.018 | 0.019 | 0.025 |
| T_guard (cycles) | 514 | 514 | 258 |
| deadline F (epochs) | – | 0 | 29 |
| opp age (epochs) | – | 0 | 23 |
| epoch age at deadline min-max | – | 0.00 – 0.00 | 29.00 – 29.00 |
| age at forced refresh, mean (% DRT) | 98.42 | 98.42 | 97.89 |
| age at drop, mean (% DRT) | 98.42 | 98.42 | 97.77 |
| age at drop, min-max (% DRT) | 98.29 – 98.50 | 98.29 – 98.50 | 95.48 – 99.10 |
| age at opp refresh, mean (% DRT) | – | 80.30 | 77.34 |
| checker counters (sum) | 0 | 0 | 0 |

Non-zero checker counters: CLK none, CLK-SD none, CLK-RTL none

## cpython_r_sp4

Status: CLK ok, CLK-SD ok, CLK-RTL ok

| | CLK | CLK-SD | CLK-RTL |
|---|---|---|---|
| IPC | 1.1604 | 1.1604 | 1.1603 |
| L1D demand MPKI | 1.346 | 1.346 | 1.348 |
| L1D primary MPKI | 0.817 | 0.817 | 0.819 |
| refresh forced /kinst | 0.000 | 0.000 | 0.000 |
| refresh opportunistic /kinst | 6.982 | 6.982 | 7.126 |
| refresh fallback (wb full) /kinst | 0.0000 | 0.0000 | 0.0000 |
| refresh Shared kept /kinst | 0.0619 | 0.0619 | 0.0617 |
| drop clean /kinst | 0.372 | 0.372 | 0.373 |
|   of which silent /kinst | – | 0.372 | 0.373 |
| drop dirty (writeback) /kinst | 0.386 | 0.386 | 0.386 |
| L2 accesses /kinst | 10.489 | 10.488 | 10.490 |
| L2 bus CleanEvict /kinst | 0.401 | 0.028 | 0.028 |
| L2 bus WritebackDirty /kinst | 0.417 | 0.417 | 0.417 |
| L2 bus snoops /kinst | 0.000 | 0.000 | 0.000 |
| snoop filter snoops /kinst | 0.000 | 0.000 | 0.000 |
| hit stall cycles /kinst | 1.404 | 1.402 | 1.435 |
| misses to a dropped line /kinst | 0.749 | 0.749 | 0.750 |
|   before it would expire /kinst | 0.003 | 0.003 | 0.001 |
| T_guard (cycles) | 514 | 514 | 258 |
| deadline F (epochs) | – | 0 | 29 |
| opp age (epochs) | – | 0 | 23 |
| epoch age at deadline min-max | – | 0.00 – 0.00 | 29.00 – 29.00 |
| age at forced refresh, mean (% DRT) | 98.46 | 98.46 | 98.88 |
| age at drop, mean (% DRT) | 98.45 | 98.45 | 98.55 |
| age at drop, min-max (% DRT) | 98.29 – 98.50 | 98.29 – 98.50 | 95.49 – 99.09 |
| age at opp refresh, mean (% DRT) | – | 80.18 | 78.35 |
| checker counters (sum) | 0 | 0 | 0 |

Non-zero checker counters: CLK none, CLK-SD none, CLK-RTL none

