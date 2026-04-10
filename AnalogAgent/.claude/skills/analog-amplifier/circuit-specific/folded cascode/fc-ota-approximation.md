# FC-OTA Approximation Skill

## Purpose

Simplification table for the single-stage Folded-Cascode OTA.

---

> **All equations in this table (both "Full" and "Simplified" forms) MUST be computed using Python when applied with actual numbers. Show the code execution, do NOT calculate mentally.**

## Simplification Table

### S01: DC Gain — cascode output impedance

| Full | A0 = gm1 × [(gm3·ro3·ro5) ∥ (gm7·ro7·ro9)] |
|--|--|
| Simplified | A0 ≈ gm1 × gm3·ro3·ro5 / 2 [when N and P stacks are balanced] |
| Validity | gm·ro >> 1 for all cascode and CS devices; balanced N/P stacks |
| Breaks when | Short L (low ro); very asymmetric N vs P stack impedance |
| Calibration | Compare A0_analytical vs SPICE DC gain. Get gm, gds from OP. |
| Practical | A0_upper from LUT: compute R_out_n and R_out_p from gm_gds at each L, take parallel. |

### S02: GBW — direct from gm1

| Full | GBW where \|A(j2πf)\| = 1 |
|--|--|
| Simplified | GBW = gm1/(2π·CL) |
| Validity | CL >> output parasitics; p_fold, p_pmos >> GBW |
| Breaks when | Small CL (< 1pF), large parasitic caps, p_fold near GBW |
| Calibration | Compare gm1/(2π·CL) vs SPICE GBW. |

### S03: Phase Margin — folding pole dominant

| Full | PM = 90° - arctan(GBW/fp_fold) - arctan(GBW/fp_pmos) - ... |
|--|--|
| Simplified | PM ≈ 90° - arctan(GBW/fp_fold) [drop p_pmos and other terms] |
| Validity | fp_pmos > 3×fp_fold (PMOS mid-node faster than fold node) |
| Breaks when | Large PMOS cascode devices (large Cgs7) or small gm7 |
| Calibration | Compare PM_analytical vs SPICE PM. If error > 5° → include all poles. |

### S04: Folding pole — Cgs dominance

| Full | fp_fold = gm3 / (2π × C_fold), C_fold = Cgs3+Csb3+Cdb1+Cgd1+routing |
|--|--|
| Simplified | fp_fold ≈ gm3 / (2π × Cgs3) [when Cgs3 dominates] |
| Validity | Cgs3 > 3× (Csb3+Cdb1+Cgd1) |
| Breaks when | Very large input pair W1 (large Cdb1) or very short L3 (small Cgs3) |
| ⚠️ Key insight | fp_fold/GBW = (gm3/gm1)×(CL/C_fold). For large CL this is naturally large. For small CL the folding pole becomes the limiting factor. |

### S05: Output capacitance — CL dominance

| Full | C_out = CL + Cdb3 + Cdb7 + Cgd3 + Cgd7 + C_cmfb |
|--|--|
| Simplified | C_out ≈ CL |
| Validity | CL > 5× parasitic sum |
| Breaks when | CL < 1pF; very wide cascode devices; heavy CMFB loading |

### S06: Square-law device model

| Full | ID = (1/2)·µ·Cox·(W/L)·Vov²·(1+λ·VDS) |
|--|--|
| Simplified | gm = 2ID/Vov; gds = λ·ID |
| Validity | L ≥ 2×Lmin, moderate inversion |
| Fallback | Always use gm/ID from LUT when available |

### S07: CMRR — tail dominated

| Full | CMRR = A0 × 2·gm_tail·ro_tail × (1+T_CMFB) |
|--|--|
| Simplified | CMRR ≈ A0 × gm_gds_tail (without CMFB contribution) |
| Validity | CMFB contribution omitted → underestimates CMRR (conservative) |
| Better | Include CMFB loop gain if known |

### S08: Noise — dropping cascode noise

| Full | S_in² = 2S_M1² + 2(gm5/gm1)²S_M5² + 2(gm9/gm1)²S_M9² + cascode terms |
|--|--|
| Simplified | S_in² ≈ 2S_M1² + 2(gm5/gm1)²S_M5² + 2(gm9/gm1)²S_M9² [drop M3,M7] |
| Validity | At frequencies where cascode source impedance << load impedance (always true at mid/low freq) |
| ⚠️ WARNING | Unlike telescopic, the current source noise (M5, M9) is NOT negligible. I_fold > I1 means gm5 can exceed gm1. Always include current source terms. |

### S09: Slew rate — symmetric approximation

| Full | SR+ = I1/CL, SR- = (I_fold)/CL (may differ) |
|--|--|
| Simplified | SR = I1/CL (assumes symmetric) |
| Validity | I_fold ≈ I1 (balanced current distribution) |
| Breaks when | I_fold >> I1 (asymmetric SR), or capacitive loading asymmetric |
| Check | Verify both SR directions in transient simulation |

### S10: Output swing — equal Vov approximation

| Full | V_swing = VDD - Vov_M5 - Vov_M3 - \|Vov_M9\| - \|Vov_M7\| |
|--|--|
| Simplified | V_swing ≈ VDD - 4×Vov_avg |
| Validity | All cascode and CS devices at similar Vov |
| Better | Use actual Vov per device from LUT at the chosen gm/ID |

### S11: Junction capacitance at estimated bias

| Full | Cdb = Cdb0 / (1 + VDB/ψ0)^0.5 |
|--|--|
| Simplified | Cdb = constant at estimated bias |
| Estimates | Output: VDB ≈ Voc1 for M3; VDB ≈ VDD-Voc1 for M7. Fold node: VDB ≈ Vov_M3 for M1. |

---

## Assumption Ledger Template for FC-OTA

```
ID   | Description                          | Applied to        | Validity condition           | Status
A01  | Square-law gm (S06)                  | gm estimates      | L ≥ 2×Lmin, mod. inv.       | unchecked
A02  | λ·ID for gds (S06)                   | gds estimates      | Long channel                 | unchecked
A03  | GBW = gm1/(2π·CL) (S02)             | GBW sizing         | CL >> parasitics, poles>>GBW | unchecked
A04  | PM ≈ 90° - arctan(GBW/fp_fold) (S03) | PM estimation      | fp_pmos > 3×fp_fold         | unchecked
A05  | fp_fold ≈ gm3/(2π·Cgs3) (S04)       | Folding pole       | Cgs3 dominates C_fold        | unchecked
A06  | C_out ≈ CL (S05)                     | GBW/pole calc      | CL >> drain parasitics       | unchecked
A07  | CMRR ≈ A0 × gm_gds_tail (S07)       | CMRR estimation    | Without CMFB (conservative)  | unchecked
A08  | CS noise significant (S08)            | Noise analysis     | Use FULL expr always         | N/A
A09  | Symmetric SR (S09)                    | SR estimation      | I_fold ≈ I1                  | unchecked
A10  | No RHP zeros                          | Transfer function  | Always (no Miller cap)       | validated
A11  | Junction caps at est. bias (S11)      | Parasitic calc     | Design near target bias      | unchecked
```
