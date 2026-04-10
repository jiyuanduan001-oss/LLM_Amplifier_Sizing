# TCO Approximation Skill

## Purpose

Simplification table for every key equation in the TCO circuit. Each entry
maps a full equation to its simplified form with explicit validity conditions.
This is the TCO-specific instantiation of the general Approximation framework.

---

> **All equations in this table (both "Full" and "Simplified" forms) MUST be computed using Python when applied with actual numbers. Show the code execution, do NOT calculate mentally.**

## Simplification Table

### S01: DC Gain — cascode impedance simplification

| Full equation | A_v = gm1 × [(gm3·ro3·ro1) ∥ (gm7·ro7·ro5)] |
|--|--|
| Simplified | A_v ≈ gm1 × (gm3·ro3·ro1) / 2 when NMOS and PMOS cascode impedances are comparable |
| Further simplified | A_v ≈ (gm1/gds1) × (gm3/gds3) / 2 = A_i1 × A_i3 / 2 |
| Validity | Rout_ncas ≈ Rout_pcas (within 2×). True when NMOS and PMOS use similar L and gm/ID. |
| Breaks when | Large asymmetry between N and P cascode impedances (e.g., short NMOS + long PMOS). One side dominates and the /2 factor is wrong. |
| Calibration | Compare A_v_analytical vs SPICE DC gain. If error > 15% → get gm, gds from OP for all 4 devices and recompute Rout_ncas ∥ Rout_pcas exactly. |

### S02: GBW — direct gm1/CL

| Full equation | GBW is the frequency where |H(jω)| = 1 (exact, requires root-finding) |
|--|--|
| Simplified | GBW ≈ gm1/(2π·CL) |
| Validity | p2, p3 > 3×ω_c (non-dominant poles well above crossover); CL >> parasitic output caps |
| Breaks when | Small CL (< 1pF) where parasitic Cdb3+Cdb7+Cgd3+Cgd7+C_cmfb is comparable to CL. In this case, use CL_total instead of CL. |
| Calibration | Compare gm1/(2π·CL) vs SPICE GBW. If SPICE GBW is >10% lower, either CL_total > CL (include parasitics) or non-dominant poles are pulling gain down near crossover. |
| Impact if wrong | Overestimates GBW by 5–15%. PM prediction becomes optimistic. |

### S03: Phase Margin — two non-dominant poles

| Full equation | PM = 90° - arctan(ω_c/p2) - arctan(ω_c/p3) |
|--|--|
| Simplified | PM ≈ 90° - (ω_c/p2 + ω_c/p3) [in radians] |
| Validity | ω_c/p_i < 0.47 for each non-dominant pole (each contributes < 25°) |
| Breaks when | Any single pole contributes > 25° of phase shift. More dangerous than TSM because telescopic has TWO significant non-dominant poles (NMOS and PMOS cascode nodes). |
| Better approx | arctan(x) ≈ 0.75·x^0.7 — valid up to x=1.7 (60° per pole), error < ±3° |
| Calibration | Compare PM_analytical vs SPICE PM. If error > 5° → use exact arctan or read PM from AC sim. |
| Impact if wrong | Optimistic PM prediction. With two non-dominant poles, the cumulative error can be worse than TSM. |

### S04: Output pole p2 — NMOS cascode node

| Full equation | p2 = gm3 / (Cdb1 + Cgd1 + Csb3 + Cgs3) |
|--|--|
| Simplified | p2 ≈ gm3 / Cgs3 [when Cgs3 dominates] |
| Validity | Cgs3 > 3× (Cdb1 + Cgd1 + Csb3). True when M3 has large W·L. |
| Breaks when | M3 is minimum length (small Cgs3) while M1 is wide (large Cdb1). |
| Impact if wrong | p2 may be lower than estimated → PM degraded |

### S05: Output pole p3 — PMOS cascode node

| Full equation | p3 = gm7 / (Cdb5 + Cgd5 + Csb7 + Cgs7) |
|--|--|
| Simplified | p3 ≈ gm7 / Cgs7 [when Cgs7 dominates] |
| Validity | Cgs7 > 3× (Cdb5 + Cgd5 + Csb7). |
| Breaks when | M7 is minimum length while M5 is wide. |
| Impact if wrong | p3 is typically the LOWEST non-dominant pole (PMOS has lower fT) → most critical for PM. |

### S06: Dominant pole — exact

| Full equation | p1 = 1 / (Rout × CL_total) |
|--|--|
| Simplified | p1 ≈ 1 / (Rout × CL) when CL >> output parasitics |
| Validity | CL > 5× (Cdb3 + Cdb7 + Cgd3 + Cgd7 + C_cmfb) |
| Note | p1 is typically not needed directly for sizing — it's implicit in the GBW and gain expressions. |

### S07: Square-law device model (GP0)

| Full equation | ID = (1/2)·µ·Cox·(W/L)·(VGS-VT)²·(1+λ·VDS) |
|--|--|
| Simplified | ID = (1/2)·µ·Cox·(W/L)·Vov² (drop λ·VDS term) |
| Derived | gm = 2·ID/Vov = √(2·µ·Cox·(W/L)·ID) |
| Validity | L ≥ 2×Lmin, moderate inversion (gm/ID ≈ 8–18 S/A) |
| Breaks when | Short channel (velocity saturation), weak inversion (subthreshold), very low Vov |
| Fallback | Use gm/ID from LUT (always preferred when LUT is available) |
| Impact if wrong | gm error up to 2× in deep submicron. Always calibrate against LUT or OP. |

### S08: Output conductance — λ·ID model

| Full equation | gds = λ·ID (long-channel) |
|--|--|
| Simplified | Same (this IS the simplified form) |
| Validity | Long channel, λ approximately constant across bias conditions |
| Breaks when | Short channel, DIBL effects, narrow devices |
| Fallback | Use gds from LUT at (gm/ID, L) operating point, or from OP data |
| Note | For cascode output impedance, gds accuracy is CRITICAL — the gain is proportional to (gm/gds)². A 20% error in gds gives 36% error in gain. |

### S09: Cascode noise negligible

| Full equation | Total noise includes M1, M3, M5, M7 contributions |
|--|--|
| Simplified | S_in² ≈ noise from M1 + noise from M5 (cascode M3, M7 negligible) |
| Validity | Always valid at frequencies below fT of cascode devices. Cascode transistors act as common-gate stages — their noise current sees a low impedance (1/gm of the device below) and is heavily attenuated when referred to input. |
| Breaks when | At frequencies approaching fT of cascode devices (rarely relevant for typical designs). |
| Impact | < 1% noise underestimation typically. |

### S10: Slew rate symmetric

| Full equation | SR+ = I_tail/CL, SR- = I_tail/CL |
|--|--|
| Simplified | SR = I_tail / CL (symmetric by topology) |
| Validity | Always valid for the ideal telescopic cascode. During slewing, one input device cuts off and all tail current steers to the other branch. |
| Breaks when | Very large input overdrive causes one branch to enter triode. Or CMFB cannot track fast enough during slewing → output CM shifts temporarily. |
| Note | This is a significant advantage over folded cascode, which can have asymmetric SR. |

### S11: Output swing — Vov stacking

| Full equation | V_swing_single = VDD - |Vov5| - |Vov7| - Vov3 - Vov1 - headroom_tail |
|--|--|
| Simplified | V_swing_single ≈ VDD - 4×Vov (when all overdrives are similar) |
| Validity | Quick estimation when all devices operate at similar Vov (100–200mV). |
| Breaks when | Different inversion levels for different devices (e.g., input pair at weak inversion, cascode at moderate). Use per-device Vov from LUT. |
| Impact | Overestimates or underestimates swing by up to 50%. Always compute per device. |

---

## Assumption Ledger Template for TCO

When starting a TCO design, initialize the ledger with these entries:

```
ID   | Description                          | Applied to        | Validity condition         | Status
A01  | Square-law gm (S07)                  | gm estimates      | L ≥ 2×Lmin, mod. inv.     | unchecked
A02  | λ·ID for gds (S08)                   | gds estimates      | Long channel               | unchecked
A03  | GBW ≈ gm1/CL (S02)                   | GBW sizing         | p2,p3 > 3×ω_c, CL>>Cpar  | unchecked
A04  | arctan(x) ≈ x for PM (S03)           | PM constraint      | ω_c/p_i < 0.47 each      | unchecked
A05  | Rout_ncas ≈ Rout_pcas (S01)          | Gain estimate      | Balanced N/P cascode      | unchecked
A06  | Cascode noise negligible (S09)        | Noise analysis     | f << fT of cascode        | unchecked
A07  | SR symmetric (S10)                    | SR constraint      | Proper CMFB tracking      | unchecked
A08  | CL >> output parasitics (S02, S06)    | Pole locations     | CL > 5× Cpar_out         | unchecked
A09  | CLM dropped in bias eqs               | Bias currents      | λ·VDS << 1                | unchecked
```

After each simulation, update the Status column using the Calibration Protocol
defined in `general/knowledge/approximation.md`.
