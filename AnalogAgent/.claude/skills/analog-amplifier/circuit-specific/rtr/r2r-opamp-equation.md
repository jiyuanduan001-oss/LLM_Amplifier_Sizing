# R2R Opamp Equation Skill

## Purpose

Complete equation set for the two-stage Rail-to-Rail Input/Output operational
amplifier with constant-gm complementary input stage, folded-cascode summing
circuit with integrated floating class-AB control, and class-AB push-pull
output stage. Based on Hogervorst et al. (JSSC 1994).

## Quick Reference

| Spec             | Branch | Key equation                              | Primary Role affected        |
|-----------------|--------|-------------------------------------------|------------------------------|
| DC gain (A0)     | §A     | A0 = A_v1 × A_v2                         | Summing circuit + output     |
| GBW              | §C     | GBW = gm_in/(2π·Cc)                      | INPUT_N/P, Cc                |
| gm constancy     | §I     | gm = √(K·I_ref), varies ≤15%             | INPUT_N, INPUT_P, GM_CTRL    |
| Phase margin     | §C     | Miller or cascoded-Miller PM              | OUTPUT, Cc                   |
| Slew rate        | §D     | SR = I_tail/(Cc), varies with V_cm        | INPUT pairs, Cc              |
| Class-AB control | §O     | Translinear loop sets I_q                 | CLASS_AB, OUTPUT             |
| Noise            | §E     | Complementary pair + summing noise        | INPUT_N/P, SUMMING           |
| CMRR             | §F     | Limited by offset change at takeover      | INPUT_N/P, GM_CTRL           |
| Output swing     | §G     | Rail-to-rail: VSS+Vdsat to VDD-Vdsat     | OUTPUT_P, OUTPUT_N           |
| CM input range   | §G     | VSS-0.4V to VDD+0.5V (beyond rails)      | INPUT_N, INPUT_P             |
| Supply voltage   | §G     | V_sup,min = Vgsp + Vgsn + 2·Vdsat        | Fundamental limit            |

## Circuit Structure

```
                          VDD
                           |
     ┌─────────────────────┼────────────────────┐
    Ib1                   M11─M12               Ib8
     |                  (P-mirror)               |
    M3───M4              M13  M14             M21─M22
  (P-input)            (P-casc) (P-casc)      (bias)
     |    |               |     |               |
    Vin+ Vin-     ┌── fold_p ──┤         M20 ──┤──── M25 (PMOS output)
                  |            |      (class-AB) |         |
    Vin+ Vin-     |            |         M19 ──┤    Vo ───┤
     |    |       |            |      (class-AB) |         |
    M1───M2       |         fold_n ──┘         M23─M24   M26 (NMOS output)
  (N-input)      M15  M16                     (bias)      |
     |          (N-casc)(N-casc)                          |
    Ib2          M17─M18                                 VSS
     |          (N-mirror)
    VSS              |
                    VSS

  gm-control: M5(N-switch), M8(P-switch), M6-M7(3× mirror), M9-M10(3× mirror)
  Floating current source: M27-M28 (same structure as class-AB control)
  Miller compensation: Cc1 from Vo to fold_p, Cc2 from Vo to fold_n
  Cascoded-Miller: Cc through cascode M14/M16 instead of directly to fold nodes
```

## Role Mapping

| Role           | Devices          | Type  | Function                                |
|---------------|------------------|-------|-----------------------------------------|
| INPUT_N        | M1, M2           | NMOS  | N-channel input differential pair       |
| INPUT_P        | M3, M4           | PMOS  | P-channel input differential pair       |
| GM_CTRL        | M5–M10, M29–M31  | Mixed | gm control (3× current mirrors + switches) |
| SUMMING_P_MIR  | M11, M12(–M14)   | PMOS  | P-type current mirror in summing circuit |
| SUMMING_N_MIR  | M15(–M16), M17, M18 | NMOS | N-type current mirror in summing circuit |
| SUMMING_CASC   | M13, M14, M15, M16 | Mixed | Cascode devices in summing circuit      |
| CLASS_AB       | M19, M20         | Mixed | Floating class-AB control transistors   |
| CLASS_AB_BIAS  | M21–M24          | Mixed | Stacked diode-connected bias for class-AB |
| OUTPUT_P       | M25              | PMOS  | PMOS output transistor (pull-up)        |
| OUTPUT_N       | M26              | NMOS  | NMOS output transistor (pull-down)      |
| FLOAT_CS       | M27, M28         | Mixed | Floating current source for summing bias |
| TAIL_N         | Ib1              | —     | Tail current for N-input pair           |
| TAIL_P         | Ib2              | —     | Tail current for P-input pair           |

---

## §I. Constant-gm Input Stage

### Operating Regions (CM Input Range)

The CM input range divides into three regions:

**Region 1** (V_cm near VSS): Only P-pair active.
N-switch (M5) ON → steers Iref1 to 3× mirror → P-tail = 4·Iref.

**Region 2** (V_cm in middle): Both pairs active.
Both switches OFF → each tail = Iref.

**Region 3** (V_cm near VDD): Only N-pair active.
P-switch (M8) ON → steers Iref2 to 3× mirror → N-tail = 4·Iref.

### Constant gm Expression

For each region the effective input gm is:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_in = √(K · I_ref)

where K = µ_p · Cox · (W/L)_P = µ_N · Cox · (W/L)_N
```

This requires:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
µ_N/µ_P = (W/L)_P / (W/L)_N
```

gm varies ≤ 15% across full CM range, with two takeover regions of ~300mV
each where the transition occurs.

### Minimum Supply Voltage

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_sup,min = V_gsp + V_gsn + 2·V_dsat
```

Below this, the input stage ceases to operate in the middle of the CM range
(a dead zone appears where neither pair is active).

---

## §A. DC Gain

### First-Stage Gain (Folded-Cascode Summing Circuit)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v1 = gm_in × R_out1

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out1 = (gm_casc_p · ro_casc_p · ro_mirror_p) ∥ (gm_casc_n · ro_casc_n · ro_mirror_n)
```

⚠️ With the floating class-AB control (M19, M20) and floating current source
(M27, M28) embedded in the summing circuit, their output impedances are
in parallel with R_out1. In the compact topology (Fig. 8/11 of the paper),
these are floating and do NOT degrade R_out1 — this is a key design advantage.

In the naive cascaded topology (Fig. 6), the class-AB bias sources (Ib6, Ib7)
ARE in parallel → R_out1 degrades → gain drops. The compact topology avoids this.

### Second-Stage Gain (Class-AB Output)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v2 = gm_out × (ro_M25 ∥ ro_M26)
```

where gm_out is the effective output stage transconductance (combination of
M25 PMOS and M26 NMOS through class-AB action).

### Total DC Gain

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A0 = A_v1 × A_v2
```

Paper measurement: ~85 dB (Miller), ~87 dB (cascoded-Miller).

---

## §B. Poles and Zeros

### Miller Compensation

**Dominant pole** (set by Miller effect):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p1 ≈ 1 / (R_out1 × gm_out × R_out2 × Cc)
```

**Output pole** (shifted up by Miller splitting):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p2_Miller ≈ gm_out / CL
```

**RHP zero** (from feedforward through Cc):
```
z_RHP = gm_out / Cc    → must be above GBW or cancelled
```

### Cascoded-Miller Compensation

By inserting the cascode (M14, M16) in the Miller loop:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p2_cascode ≈ (Cc/Cgs_out) × (gm_out/CL)
```

This is a factor Cc/Cgs_out ≈ 2.5× higher than standard Miller → the main
advantage of cascoded-Miller. The paper achieves 6.4 MHz vs 2.6 MHz.

The RHP zero moves to much higher frequency (through cascode isolation).

### Summing Circuit Poles

The folded-cascode summing circuit has internal poles similar to the FC-OTA:
- Folding node pole at each fold point
- Cascode mid-node poles
These must be > 3× GBW.

---

## §C. Bandwidth and Phase Margin

### GBW

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm_in / (2π × Cc)
```

Since gm_in is constant (±15%) across CM range, GBW is also approximately
constant — this is the primary benefit of the constant-gm technique.

Paper: 2.6 MHz (Miller), 6.4 MHz (cascoded-Miller), CL = 10 pF.

### Phase Margin

Miller: 66°. Cascoded-Miller: 53°.

---

## §D. Slew Rate

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR = I_tail_active / Cc
```

⚠️ **SR varies by 2× across CM range** because:
- Middle CM: both pairs active, tail = Iref each → SR = Iref/Cc
- Outer CM: one pair active, tail = 4·Iref → SR = 4·Iref/Cc → 2× the current
  available to charge Cc (since 4·Iref but split into 2 half-circuits = 2·Iref per Cc)

Paper: Miller = 2/4 V/µs, cascoded-Miller = 4/8 V/µs (inner/outer CM range).

---

## §E. Noise Analysis

### Noise Sources

In the compact topology (class-AB embedded in summing circuit):
- **INPUT_N (M1, M2)**: noise during N-pair active region
- **INPUT_P (M3, M4)**: noise during P-pair active region
- **SUMMING mirrors (M11–M18)**: contribute like FC-OTA current sources
- **Cascode devices (M13–M16)**: negligible
- **Class-AB (M19, M20)**: floating → does NOT contribute (key advantage)
- **Floating CS (M27, M28)**: floating → does NOT contribute

This makes noise comparable to a three-stage amplifier despite being two-stage.

### Input-Referred Noise (per active region)

When only P-pair active (low V_cm):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_in² ≈ 2·S_M3² + 2·(gm_mirror/gm3)²·S_mirror²
```

When both pairs active (middle V_cm):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_in² ≈ 2·S_M1² + 2·S_M3² + summing_contributions
```
(noisier because both pairs contribute, but gm is same → NEF may be worse)

Paper: 22 nV/√Hz @10kHz (Miller), 31 nV/√Hz (cascoded-Miller).

---

## §F. CMRR

CMRR is limited by the **offset change at the takeover regions**.

In the takeover ranges (VSS+1V to VSS+1.3V and VDD-1.3V to VDD-1V),
the offset changes by ~2 mV as the active pair transitions.

```
CMRR_takeover ≈ 43 dB    [worst case, during transition]
CMRR_other ≈ 70 dB       [outside takeover ranges]
```

The 3× current mirror gm-control spreads the offset change over two 300mV
takeover ranges, improving CMRR compared to uncontrolled complementary input.

---

## §G. Swing and Supply Constraints

### Rail-to-Rail Output Swing

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = VSS + Vdsat_M26     [NMOS output device]
V_out,max = VDD - |Vdsat_M25|   [PMOS output device]
```

Paper: VSS+0.1V to VDD-0.2V.

### Rail-to-Rail (and Beyond) Input Range

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm,min = VSS - 0.4V    [P-pair can go below VSS]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm,max = VDD + 0.5V    [N-pair can go above VDD]
```

---

## §O. Class-AB Output Stage

### Translinear Loop (Quiescent Current Setting)

Two translinear loops set the quiescent output current:
```
Loop 1: M20, M21, M22, M25  → sets I_q for PMOS output
Loop 2: M19, M23, M24, M26  → sets I_q for NMOS output
```

The voltage between gates of M25 and M26 is kept constant by the
floating class-AB control (M19, M20). This determines I_q through
W/L ratios of the class-AB transistors relative to the output transistors.

### Class-AB Action

In-phase signal currents (Iin1, Iin2) drive both gates of the output
transistors in the same direction:
- Push into class-AB → both gate voltages move up → output pulls current
- Pull from class-AB → both gate voltages move down → output pushes current

The minimum current in either output transistor is set by the translinear
loop, preventing either device from turning off completely.

### Floating Current Source (M27, M28)

Same structure as class-AB control → supply voltage dependency matches →
quiescent current is independent of VDD variations.

The floating architecture means M27/M28 do NOT contribute to noise or offset.
Current varies only ±5% across full CM range.
