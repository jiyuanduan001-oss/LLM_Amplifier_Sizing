# R2R Opamp Approximation Skill

## Purpose

Simplification table for the two-stage Rail-to-Rail Input/Output opamp
with constant-gm complementary input, folded-cascode summing circuit,
integrated floating class-AB control, and push-pull output stage.

---

> **All equations in this table (both "Full" and "Simplified" forms) MUST be computed using Python when applied with actual numbers. Show the code execution, do NOT calculate mentally.**

## Simplification Table

### S01: Constant gm — 3× mirror method

| Full | gm varies as √(µ·Cox·(W/L)·I_tail) with I_tail changing across CM range |
|--|--|
| Simplified | gm = √(K·Iref), constant across entire CM range |
| Validity | Current switches (M5, M8) fully ON or fully OFF; W/L ratio obeys µN/µP = (W/L)_P/(W/L)_N |
| Breaks when | Takeover regions (~300mV each, gm varies ≤15%); µN/µP deviates from nominal (±15% process → ±7.5% gm error) |
| Calibration | Sweep V_cm, plot gm from SPICE. Verify ≤15% variation. |

### S02: GBW — set by gm_in and Cc

| Full | GBW where |A(j2πf)| = 1, includes all parasitic poles |
|--|--|
| Simplified | GBW = gm_in/(2π·Cc) |
| Validity | Two-stage Miller compensated; parasitic poles >> GBW |
| Breaks when | Cascoded-Miller (different pole locations); heavy parasitic loading at summing node |
| ⚠️ Key insight | Because gm_in is constant (S01), GBW is approximately constant across CM range — the primary design benefit of constant-gm control. Without it, GBW varies 2× → PM varies drastically. |

### S03: Output pole — Miller vs cascoded-Miller

| Full | Complex expression involving all parasitics at output node |
|--|--|
| Miller simplified | p2_Miller ≈ gm_out/CL |
| Cascode simplified | p2_cascode ≈ (Cc/Cgs_out) × (gm_out/CL) |
| Validity | CL >> output parasitics; gm_out >> 1/R_out2 |
| ⚠️ Key insight | Cascoded-Miller shifts p2 higher by factor Cc/Cgs_out ≈ 2.5×. This is why the paper achieves 6.4 MHz vs 2.6 MHz with the same power. |

### S04: First-stage gain — cascode output impedance

| Full | A_v1 = gm_in × [(gm13·ro13·ro11) ∥ (gm16·ro16·ro18)] |
|--|--|
| Simplified | A_v1 ≈ gm_in × gm_casc·ro_casc·ro_mirror / 2 (balanced P/N stacks) |
| Validity | Floating class-AB and floating CS do not load the summing node (compact topology Fig.11) |
| Breaks when | Naive cascaded topology (Fig.6) where Ib6/Ib7 are in parallel → R_out1 degrades |
| ⚠️ Critical | In the compact topology, the floating architecture of M19-M20 and M27-M28 is essential to preserving R_out1. If they are non-floating (fixed to supply), first-stage gain drops significantly. |

### S05: SR — varies with CM region

| Full | SR depends on which input pair is active and its tail current |
|--|--|
| Simplified | SR_middle = Iref/Cc (both pairs active); SR_outer = 2×Iref/Cc (one pair at 4×Iref) |
| Validity | Current switches fully engaged in outer regions |
| ⚠️ Key insight | SR changes by 2× across CM range. This is inherent to the 3× mirror gm-control and cannot be avoided. Worst-case SR is in the middle CM range. |

### S06: Noise — floating elements negligible

| Full | All noise sources including class-AB control, floating CS, summing, input pairs |
|--|--|
| Simplified | Noise ≈ input pairs + summing circuit mirrors only |
| Validity | Class-AB (M19-M20) and floating CS (M27-M28) are floating → no noise contribution |
| ⚠️ Key insight | This approximation is what makes the compact topology (Fig.11) equivalent to a three-stage amplifier in noise/offset, despite being only two stages. In the naive topology (Fig.6), Ib6/Ib7 contribute at unity current gain → noise is much worse. |

### S07: CMRR — takeover-limited

| Full | CMRR varies across entire CM range |
|--|--|
| Simplified | CMRR ≈ 43 dB in takeover regions; ≈ 70 dB elsewhere |
| Validity | 3× mirror gm-control spreads offset change over two 300mV takeover regions |
| ⚠️ Key insight | CMRR is fundamentally limited by the offset difference between N and P input pairs. The 3× mirror technique improves CMRR by spreading the transition over a wider voltage range, but cannot eliminate it. |

### S08: Class-AB quiescent current — translinear loop

| Full | Iq set by two translinear loops involving M19-M26 |
|--|--|
| Simplified | Iq ≈ I_AB × (W/L)_out / (W/L)_AB where I_AB is the class-AB bias |
| Validity | All devices in saturation; square-law model holds |
| Breaks when | Subthreshold operation; large signal swings pushing devices out of saturation |

### S09: Floating CS tracks class-AB VDD dependency

| Full | Both floating CS (M27-M28) and class-AB (M19-M20) have supply-dependent currents |
|--|--|
| Simplified | Supply dependencies cancel → Iq independent of VDD |
| Validity | M27-M28 have identical structure to M19-M20 |
| ⚠️ Key insight | If the floating CS had a different topology from the class-AB control, Iq would vary with VDD. Structural matching is essential. |

### S10: Floating CS current — CM-independent

| Full | Floating CS current depends on Vgs of mirror devices M11 and M17, which change with CM |
|--|--|
| Simplified | Floating CS ≈ constant (varies ≤5% over full CM range) |
| Validity | When Vgs_M11 decreases, Vgs_M17 increases by the same amount → sum of Vgs is constant |
| Breaks when | Extreme CM where one pair is completely off and the other is at 4×Iref (slight imbalance) |

### S11: Square-law device model

| Full | ID = (1/2)·µ·Cox·(W/L)·Vov²·(1+λ·VDS) |
|--|--|
| Simplified | gm = 2ID/Vov; gds = λ·ID |
| Validity | L ≥ 2×Lmin, strong inversion |
| Fallback | Use gm/ID from LUT when available |

---

## Assumption Ledger Template for R2R Opamp

```
ID   | Description                              | Applied to          | Validity condition               | Status
A01  | Constant gm (S01)                        | Input stage          | W/L ratio matched to µN/µP       | unchecked
A02  | GBW = gm_in/(2π·Cc) (S02)               | BW sizing            | Miller comp; poles >> GBW         | unchecked
A03  | p2 = gm_out/CL (S03)                     | PM estimation         | Standard Miller; CL >> parasitics | unchecked
A04  | Floating elements no noise (S06)          | Noise analysis        | Compact topology (Fig.11)        | validated
A05  | SR varies 2× (S05)                        | SR estimation         | 3× mirror gm-control              | validated
A06  | CMRR ≈ 43dB in takeover (S07)            | CMRR estimation       | Inherent to complementary input   | validated
A07  | Iq indep. of VDD (S09)                    | Class-AB bias         | Floating CS = same structure      | unchecked
A08  | Floating CS ≈ const vs Vcm (S10)         | Bias stability        | Mirror Vgs sum conserved          | unchecked
A09  | Square-law gm (S11)                       | gm estimates          | L ≥ 2×Lmin, strong inv.          | unchecked
A10  | First-stage gain uses cascode Rout (S04)  | Gain calculation      | Compact floating topology         | validated
```
