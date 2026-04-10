# FC-OTA Equation Skill

## Purpose

Complete equation set for the single-stage Folded-Cascode OTA (fully
differential), organized by analysis branch.

## Quick Reference

| Spec             | Branch | Key equation                              | Primary Role affected        |
|-----------------|--------|-------------------------------------------|------------------------------|
| DC gain (A0)     | §A     | A0 = gm1 × (R_out_n ∥ R_out_p)           | INPUT_PAIR, all cascode Roles |
| GBW              | §C     | GBW = gm1/(2π·CL)                        | INPUT_PAIR                   |
| Phase margin     | §C     | PM ≈ 90° - arctan(GBW/p_fold) - ...      | NMOS_CASC, PMOS_CS           |
| Dominant pole    | §B     | fp1 = 1/(2π·R_out·CL)                    | All (via R_out)              |
| Folding pole     | §B     | p_fold = gm_cg / C_fold                  | NMOS_CASC (or PMOS_CASC)     |
| Zeros            | §B     | No RHP zeros (no Miller cap)              | —                            |
| Slew rate        | §D     | SR = I1/CL (single-stage, no Cc)         | INPUT_PAIR, TAIL             |
| Noise            | §E     | FC has more noise sources than telescopic  | INPUT_PAIR, PMOS_CS, NMOS_CS |
| CMRR             | §F     | Depends on tail ro + CMFB loop gain       | TAIL, CMFB                   |
| PSRR             | §F     | Cascode stacking improves isolation        | All current sources          |
| Output swing     | §G     | Limited by cascode stacks                 | NMOS_CASC, PMOS_CASC         |
| CM input range   | §G     | Wider than telescopic (key FC advantage)  | INPUT_PAIR, TAIL             |
| Settling         | §D     | Single-pole settling, SR + linear         | System-level                 |
| CMFB             | §H     | Separate loop stability                   | CMFB                         |

## Circuit Structure (Fully Differential, NMOS-Input)

```
                          VDD
                           |
              ┌────────────┼────────────┐
             M9a          M9b          (bias)    ← PMOS_CS (current source, top)
              |            |
             M7a          M7b                    ← PMOS_CASC (cascode, top)
              |            |
    ┌─── fold_node_a ─────┤──── fold_node_b ───┐
    |                      |                     |
   M1a ──Vin+      Vin-── M1b                   |   ← INPUT_PAIR (NMOS diff pair)
         └────┬────┘                             |
              M_tail                             |   ← TAIL (NMOS tail current source)
              |                                  |
             VSS                                 |
    |                                            |
   M3a                                         M3b   ← NMOS_CASC (cascode, bottom)
    |                                            |
   M5a                                         M5b   ← NMOS_CS (current source, bottom)
    |                                            |
   VSS                                         VSS

   Outputs: Vout_a = drain(M7a) = drain(M3a)
            Vout_b = drain(M7b) = drain(M3b)

   CMFB senses (Vout_a + Vout_b)/2, controls M9a/M9b gate or M5a/M5b gate
```

## Role Mapping

| Role          | Devices       | Type  | Function                              |
|--------------|---------------|-------|---------------------------------------|
| INPUT_PAIR    | M1a, M1b      | NMOS  | Differential input pair               |
| TAIL          | M_tail        | NMOS  | Tail current source                   |
| NMOS_CASC     | M3a, M3b      | NMOS  | Cascode devices (bottom stack)        |
| NMOS_CS       | M5a, M5b      | NMOS  | Current source (bottom of N-cascode)  |
| PMOS_CASC     | M7a, M7b      | PMOS  | Cascode devices (top stack)           |
| PMOS_CS       | M9a, M9b      | PMOS  | Current source (top of P-cascode)     |
| CMFB          | Error amp + det | Mixed | Common-mode feedback                 |
| BIAS          | Bias mirrors  | Mixed | Generate Vbn_cs, Vbn_casc, Vbp_cs, Vbp_casc |

## Matching and Symmetry

```
M1a ≡ M1b           (input pair)
M3a ≡ M3b           (NMOS cascode)
M5a ≡ M5b           (NMOS current source)
M7a ≡ M7b           (PMOS cascode)
M9a ≡ M9b           (PMOS current source)
```

## Current Distribution

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
I_tail = 2 × I1                    [total tail current]
I_fold = I_PMOS_CS = I_NMOS_CS     [folding branch current per side]

Constraint: I_fold > I1   (otherwise cascode branch starves)
Typical: I_fold = 1.2–2 × I1

I_nmos_casc = I_fold               [flows through bottom cascode]
I_pmos_casc = I_fold               [flows through top cascode]
Current at fold node: I_fold - I1  [excess current from current source minus input pair]

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
P_total = (I_tail + 2×I_fold) × VDD    [or 2×I_fold × VDD if tail current is part of fold]
```

⚠️ The current distribution depends on the exact topology. In many FC designs,
I_fold = I_tail/2 + I_extra, where I_extra is additional current from the
folding current sources beyond what the input pair provides. The key constraint
is that every branch in the cascode stack must have positive current.

---

## §A. DC Gain

### Output Impedance (Cascode)

Each side of the output has two cascode stacks in parallel:

**NMOS cascode stack** (looking up from VSS):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out_n = gm3 × ro3 × ro5    [gm_casc × ro_casc × ro_cs]
```

**PMOS cascode stack** (looking down from VDD):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out_p = gm7 × ro7 × ro9    [gm_casc × ro_casc × ro_cs]
```

**Total output impedance**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out = R_out_n ∥ R_out_p
```

### DC Gain

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A0 = gm1 × R_out = gm1 × (R_out_n ∥ R_out_p)
   = gm1 × [(gm3·ro3·ro5) ∥ (gm7·ro7·ro9)]
```

This achieves gain of order (gm·ro)² in a single stage — the primary
advantage of the cascode structure.

### Gain in terms of intrinsic gains (from LUT)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out_n ≈ (gm_gds_M3) × (gm_gds_M5) × (1/gm3)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out_p ≈ (gm_gds_M7) × (gm_gds_M9) × (1/gm7)

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A0 ≈ gm1 / (1/R_out_n + 1/R_out_p)
```

For the typical case where R_out_n ≈ R_out_p:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A0 ≈ gm1 × R_out_n / 2
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
   ≈ (gm1/gm3) × gm_gds_M3 × gm_gds_M5 / 2
```

Since I1 ≈ I3 and both are NMOS at similar gm/ID: gm1 ≈ gm3, so:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A0 ≈ gm_gds_M3 × gm_gds_M5 / 2    [when R_out_n dominates or ≈ R_out_p]
```

---

## §B. Poles and Zeros

### Dominant Pole (output node)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p1 = 1 / (R_out × C_out)    [rad/s]

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
C_out = CL + Cdb3 + Cdb7 + Cgd3 + Cgd7 + Cdb_cmfb_loading
```

For CL >> parasitics:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p1 ≈ 1 / (R_out × CL)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
fp1 = p1 / (2π)
```

### Folding Node Pole (p_fold) — CRITICAL for FC

Located at the folding node (source of M3, drain of M1):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p_fold = gm3 / C_fold    [rad/s]

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
C_fold = Cgs3 + Csb3 + Cdb1 + Cgd_M1(Miller) + parasitic_routing
```

⚠️ **This pole is the primary bandwidth limiter of the FC-OTA.**
The cascode device M3 must be "fast" — it needs high gm3 relative to
C_fold. This means:
- Vov_M3 should be LARGE (strong inversion, high gm/Cgs ratio)
- But Vov_M3 must be < Vth_M1 for input CM range to reach VSS

**Design rule**: p_fold > 3× GBW for PM ≥ 60°.
Typical target: p_fold > 5× GBW for comfortable PM.

### PMOS Cascode Node Pole

A secondary pole at the source of M7 (between PMOS cascode and PMOS CS):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p_pmos = gm7 / C_pmos_mid

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
C_pmos_mid = Cgs7 + Csb7 + Cdb9
```

Usually p_pmos > p_fold (PMOS cascode is often faster due to lower parasitic
capacitance at this node), but should be checked.

### Zeros

**No RHP zeros** in the single-stage FC-OTA (no Miller compensation capacitor).
The ideal PM starts at 90°, degraded only by parasitic poles.

This is a significant advantage: no need for nulling resistors or
special zero-cancellation techniques.

---

## §C. Bandwidth and Phase Margin

### Unity-Gain Bandwidth

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm1 / (2π × CL)
```

Same as any single-stage OTA — GBW is set by gm1 and CL.
No compensation capacitor in the GBW expression (unlike two-stage).

### Phase Margin

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PM = 90° - arctan(GBW/fp_fold) - arctan(GBW/fp_pmos) - arctan(GBW/fp_other)
```

For well-designed FC where fp_fold >> GBW:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PM ≈ 90° - arctan(GBW/fp_fold)
```

**For PM ≥ 60°**: fp_fold ≥ 1.73 × GBW
**For PM ≥ 70°**: fp_fold ≥ 2.75 × GBW
**Conservative**: fp_fold > 3 × GBW

### Relationship between PM and cascode device sizing

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
fp_fold = gm3 / (2π × C_fold)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm1 / (2π × CL)

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
fp_fold/GBW = (gm3/gm1) × (CL/C_fold)
```

Since gm3/gm1 ≈ 1 (same current, similar gm/ID for NMOS), the ratio
depends heavily on CL/C_fold. For large CL (>> C_fold), fp_fold >> GBW
automatically. The FC-OTA is naturally well-suited for large CL applications.

For small CL: fp_fold can approach GBW → PM degrades. Options:
- Increase gm3 (reduce gm/ID of cascode → stronger inversion, larger Vov_M3)
- Reduce C_fold (smaller input pair → less Cdb1)

---

## §D. Large-Signal Analysis

### Slew Rate

For the single-stage FC-OTA:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR = I1 / CL
```

Where I1 = I_tail/2 is the current per input device. During slewing, one
side of the diff pair turns off completely, steering all of I_tail to one side.
The output CL is charged by I1 (not I_tail, because the mirror/fold
structure limits the available current to one branch).

⚠️ **Asymmetric slewing**: In some FC configurations:
- Positive SR: limited by I1 (input pair current)
- Negative SR: limited by I_fold (folding current source)
If I_fold > I1, negative SR > positive SR. Check both directions.

### Settling Time (Switched-Capacitor Applications)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
t_settle = t_slew + t_linear

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
t_slew = V_step / SR   [if SR < V_step × ω_u × β]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
t_linear = (N × ln2) / (2π × GBW × β)
```

where β = Cs/(Cs+Cf) is the feedback factor, N = number of time constants
for desired accuracy (e.g., N=7 for 0.1% settling).

**If SR > V_step × ω_u × β**: entire settling is linear (no slew phase).
This is the desired operating condition.

### Fundamental SR / GBW Relationship (Single-Stage)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR = I1/CL = (gm1/gm_id_1) / CL

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm1/(2π·CL)

Therefore: SR = GBW × 2π / gm_id_1
```

SR and GBW are directly linked through gm/ID. To increase SR without
increasing GBW: decrease gm/ID (stronger inversion → more current per gm).

---

## §E. Noise Analysis

### Input-Referred Noise (FC Has More Sources Than Telescopic)

The FC-OTA has noise contributions from:
1. Input pair (M1a, M1b) — dominant, desired
2. NMOS current sources (M5a, M5b) — fold into signal path
3. PMOS current sources (M9a, M9b) — fold into signal path
4. Cascode devices (M3, M7) — negligible at mid/low frequencies

⚠️ **The folding current sources (M5, M9) inject noise directly into the
signal path.** This is the primary noise disadvantage of FC vs telescopic.

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_in(f)² = 2×S_M1² + 2×(gm5/gm1)²×S_M5² + 2×(gm9/gm1)²×S_M9²
```

### Thermal Noise

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_thermal² = 2 × (8kT)/(3·gm1) × [1 + gm5/gm1 + gm9/gm1]
```

### 1/f Noise

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_1f² = (2·Kf_n)/(Cox·W1·L1·f) × [1 + (Kf_n·µn·W1·L1·gm5²)/(Kf_p·µp·W5·L5·gm1²)
                                     + (Kf_p·µp·W1·L1·gm9²)/(Kf_n·µn·W9·L9·gm1²)]
```

### Noise Optimization Strategy

To minimize noise:
- **Input pair (M1)**: low Vov → high gm/ID → maximize gm1 per unit current
- **Folding current sources (M5, M9)**: HIGH Vov → low gm5, gm9 → minimize
  noise contribution. This is the opposite of the input pair!
- **Cascode devices (M3, M7)**: noise negligible (source impedance << load impedance)
  → size for speed (fT), not noise

⚠️ **Key FC noise insight**: M5 (NMOS_CS) typically carries I_fold > I1,
so if M5 has the same Vov as M1, gm5 > gm1, making current source noise
LARGER than input pair noise. Always make Vov_M5 >> Vov_M1.

### Total Integrated Noise

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V²_noise = S_1f² × ln(fH/fL) + S_thermal² × (fH - fL)
```

For noise bandwidth limited by GBW:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V²_noise,total ≈ S_thermal² × (π/2) × GBW    [single-pole approximation]
```

---

## §F. CMRR and PSRR

### CMRR

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
CMRR_intrinsic = A_DM × 2 × gm_tail × ro_tail
```

With CMFB active:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
CMRR ≈ CMRR_intrinsic × (1 + T_CMFB)
```

where T_CMFB is the CMFB loop gain.

**Design implication**: Increase L_tail for higher ro_tail → better CMRR.
The CMFB loop gain provides additional CM suppression.

### PSRR

The cascode stacking provides excellent supply rejection:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PSRR⁺_LF ≈ A0 × (gm7·ro7)     [VDD rejection through PMOS cascode stack]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PSRR⁻_LF ≈ A0 × (gm3·ro3)     [VSS rejection through NMOS cascode stack]
```

Both are much better than simple mirror topologies (5T OTA) because the
cascode provides an additional factor of (gm·ro) in supply isolation.

At high frequencies, PSRR degrades as loop gain drops:
```
|PSRR(f)| ≈ PSRR_LF / √(1 + (f/fp1)²)
```

---

## §G. Bias and Swing Constraints

### CM Input Range (FC Advantage)

The folded structure decouples the input pair from the output stack:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm,min = VSS + Vov_tail + Vgs_M1 = Vov_tail + Vth_n + Vov_M1
V_cm,max = VDD - |Vov_M9| - |Vov_M7| + Vth_n
```

The key advantage: V_cm,max is NOT limited by the PMOS cascode stack
sitting ON TOP of the input pair (as in telescopic). The fold allows the
input pair to swing independently.

**For V_cm to reach VSS**: Need Vov_M3 < Vth_M1 (cascode device overdrive
must be less than input pair threshold). This constrains M3 sizing.

### Output Swing

Both cascode stacks limit the output swing:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = Vov_M5 + Vov_M3    [NMOS cascode stack: 2 × Vov above VSS]
V_out,max = VDD - |Vov_M9| - |Vov_M7|  [PMOS cascode stack: 2 × |Vov| below VDD]
```

Total swing:
```
V_swing = VDD - Vov_M5 - Vov_M3 - |Vov_M9| - |Vov_M7|
        = VDD - 4×Vov  (if all overdrive voltages are similar)
```

⚠️ **Output swing is the primary limitation of the FC-OTA.**
For VDD = 1.8V and Vov ≈ 150mV: swing ≈ 1.8 - 4×0.15 = 1.2V.
For VDD = 1.0V: swing ≈ 1.0 - 4×0.15 = 0.4V (very tight!).

**Low-voltage solutions**: wide-swing cascode biasing reduces headroom
to 2×Vov (one per stack) instead of 2×(Vov + margin).

### First-Stage Output CM Level (Voc1)

For fully differential FC, the output CM must be set by CMFB:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Voc1 = (V_out,min + V_out,max) / 2    [ideally mid-swing]
```

---

## §H. CMFB Equations

### Why CMFB is Required

The fully-differential FC-OTA has no internal mechanism to set the output
CM voltage. Without CMFB, any mismatch in the P/N cascode current sources
will drive the output CM to a rail, putting devices in the linear region.

### CMFB Control Point

The CMFB typically controls:
- **PMOS_CS (M9)**: adjust gate voltage of M9a/M9b
- OR **NMOS_CS (M5)**: adjust gate voltage of M5a/M5b
- OR **split TAIL**: split M_tail into fixed + CMFB-controlled halves

Controlling PMOS_CS (M9) is common: fewer poles in the CM loop than
controlling through the input pair path.

### CMFB Loop Gain

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
T_CMFB = gm_error × R_out_error × gm_controlled / (1/R_out_main)
```

### CMFB Bandwidth

Rule of thumb: CMFB UGB ≥ (1/3) × DM UGB.
If CMFB is too slow, CM settling limits overall settling time in
switched-capacitor applications.

### CMFB Stability

The CMFB loop has its own poles. Must ensure PM_CMFB > 45°.
Compensation may be needed (small cap at CMFB output).
