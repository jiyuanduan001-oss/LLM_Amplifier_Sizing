# TCO Design Flow Skill

## Purpose

Capture the reasoning process of a senior designer sizing a Fully Differential
Telescopic Cascode OTA. This skill is invoked by the Circuit Design Flow Skill
when the Circuit Understanding Skill identifies the topology as TCO.

## References

- Equations: `circuit-specific/tco/tco-equation.md` (cite as [EQ §Branch])
- Approximations: `circuit-specific/tco/tco-approximation.md` (cite as [APPROX S##])
- LUT queries: `general/knowledge/device-data-lut.md` (cite as [LUT])
- Mismatch/PVT: `general/knowledge/mismatch-pvt.md`

---

## Pre-Design Check: Is TCO the Right Topology?

Before beginning, verify that the telescopic cascode is appropriate:

**Use TCO when**:
- Single-stage gain is sufficient (typically 40–70 dB without gain boosting)
- Lowest power is required (only one bias current path)
- High speed / high GBW is needed
- Application is switched-capacitor (feedback factor β < 1, so V_in_CM ≠ V_out_CM is OK)
- Load is primarily capacitive
- Output swing limitation is acceptable

**Do NOT use TCO when**:
- Need unity-gain feedback (V_in_CM = V_out_CM required) → use folded cascode
- Need rail-to-rail output → use folded cascode or two-stage
- VDD < 4 × Vov_min (insufficient headroom for 4 stacked devices)
- Need gain > 70 dB without gain boosting → use two-stage or gain-boosted TCO

**Headroom feasibility check** (MANDATORY):
```
VDD ≥ Vov_tail + VGS_input + Vov_ncas + Vov_pcas + |VGS_pload|
    ≈ Vov + (VT + Vov) + Vov + Vov + (|VTP| + Vov)
    = VTN + |VTP| + 5×Vov

For VTN=0.4V, |VTP|=0.4V, Vov=0.15V:
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  VDD_min ≈ 0.4 + 0.4 + 0.75 = 1.55V

If VDD < VDD_min: ⚠️ Telescopic cascode is NOT feasible. Use folded cascode.
```

---

## Design Procedure

### Step 1 — Derive gm1 from GBW Spec

[EQ §C, APPROX S02]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm1_required = 2π × GBW × CL_total
```

For initial sizing, assume CL_total ≈ CL (refine after parasitic estimation):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm1_required = 2π × GBW × CL
```

**No compensation capacitor** — the telescopic cascode uses CL directly.
This is more efficient than TSM where GBW = gm1/(2π·Cc) and Cc < CL.

### Step 2 — Select gm/ID for DIFF_PAIR (M1a, M1b)

This is the primary design decision. gm/ID determines inversion region.

| GBW range     | Recommended gm/ID | Inversion   |
|--------------|--------------------|-------------|
| < 10 MHz      | 15–20 S/A          | Weak–moderate |
| 10–200 MHz    | 10–15 S/A          | Moderate     |
| > 200 MHz     | 5–10 S/A           | Strong       |

**LUT query**: confirm that the target gm/ID exists at the candidate L.
```
lut_query(device='nfet', metric='gm_id', L=L_candidate)
→ verify gm/ID_target is on the curve
→ read fT at this operating point (fT must support GBW with margin)
```

**For TCO specifically**: favor moderate-to-strong inversion for M1.
Lower gm/ID → lower Vov → more headroom for the stacked cascode.
This is a tradeoff unique to telescopic: weak inversion gives best
gm/current but eats into headroom.

### Step 3 — Derive ID and I_tail

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
ID1 = gm1_required / gm_id_target
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
I_tail = 2 × ID1
```

Power check:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
P = I_tail × VDD
If P > P_max → increase gm/ID (reduce current), or relax GBW
```

**Advantage over TSM**: P = I_tail × VDD (no second-stage current).
For same GBW spec, TCO typically uses 40–60% less power than TSM.

### Step 4 — Select L for Gain Requirement

[EQ §A, APPROX S01, S08]

The gain requirement sets the minimum L. For TCO, gain scales as (gm·ro)²:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v ≈ (gm1/gds1) × (gm3/gds3) / 2
```

**Procedure**:
1. From LUT, query intrinsic gain A_i = gm/gds as a function of L at the target gm/ID.
2. Gain upper bound: A_v_upper ≈ A_i_n × A_i_n / 2 (if symmetric N cascode)
   or A_v_upper = (A_i_n × A_i_p) / 2 (for mixed N/P).
3. Select minimum L where A_v_upper ≥ A0_target + 6 dB margin.

**Note**: TCO typically achieves 50–65 dB gain at moderate L. For higher gain,
increase L (but check GBW impact) or add gain boosting.

Record L_selected for DIFF_PAIR. Cascode and load L may differ.

### Step 5 — Determine W for DIFF_PAIR (M1a, M1b)

From LUT at (gm/ID_target, L_selected):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W1 = ID1 / J_n(gm/ID_target, L_selected)
```
where J_n is the current density (A/µm) from the nfet LUT.

If W1 < W_min (layout constraint) → increase W1 to W_min, recalculate ID1.

**Check fT**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
fT_M1 = gm1 / (2π × Cgg1)    [from LUT]
Require: fT_M1 > 5 × GBW     [comfortable margin]
```

### Step 6 — Size NMOS Cascode (M3a, M3b)

[EQ §B — non-dominant pole p2]

The NMOS cascode must provide:
1. High output impedance: gm3·ro3 as large as possible
2. High p2: gm3/Cp2 well above ω_c

**gm/ID selection**: moderate-to-strong inversion (8–14 S/A).
- Higher gm3 → higher p2 → better PM
- Stronger inversion (lower gm/ID) → higher Vov3 → reduced output swing

**L selection**: L3 ≥ L1 for gain. Often L3 = L1 (same gain contribution).
Increasing L3 helps gain but hurts p2 (larger Cgs3).

**PM constraint on gm3**:
```
p2 = gm3 / Cp2  must be  > 3 × ω_c

→ gm3 > 3 × ω_c × Cp2
→ gm3 > 3 × (gm1/CL) × Cp2
```

Since M3 carries the same current ID1 as M1:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W3 = ID1 / J_n(gm_id_M3, L3)
```

### Step 7 — Size PMOS Load (M5a, M5b)

[EQ §A — gain, EQ §E — noise]

M5 carries the same current ID1. Its role:
1. Provide high ro5 for gain (gm7·ro7·ro5)
2. Minimize noise contribution (keep gm5/gm1 small)

**gm/ID selection**: moderate inversion (10–15 S/A).
- Lower gm5/gm1 → less noise contribution from M5
- But PMOS at moderate inversion needs larger W for same ID → check area

**L selection**: L5 should be LONG (maximize ro5 for gain).
L5 ≥ L1 is typical. Can be longer since M5 is not speed-critical
(p3 is set by M7, not M5).

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W5 = ID1 / J_p(gm_id_M5, L5)
```

**Noise check**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Noise_factor = 1 + gm5/gm1
Target: gm5/gm1 < 0.5 (load noise < 50% of input pair noise)
```

### Step 8 — Size PMOS Cascode (M7a, M7b)

[EQ §B — non-dominant pole p3]

This is typically the SPEED-LIMITING device. p3 = gm7/Cp3 is usually
the lowest non-dominant pole because PMOS has lower fT than NMOS.

**gm/ID selection**: strong-to-moderate inversion (8–12 S/A).
- Maximize gm7 for highest p3
- Strong inversion gives highest fT for PMOS

**L selection**: L7 can be shorter than L5 (M7 provides cascoding,
not primary ro). L7 = L_min or 2×L_min for speed.

**PM constraint on gm7**:
```
p3 = gm7 / Cp3  must be  > 3 × ω_c

→ gm7 > 3 × ω_c × Cp3
→ gm7 > 3 × (gm1/CL) × Cp3
```

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W7 = ID1 / J_p(gm_id_M7, L7)
```

**CRITICAL check**: p3 vs p2. If p3 < p2 (likely for PMOS cascode):
p3 is the binding constraint for PM. Optimize M7 for speed first.

### Step 9 — Size TAIL Current Source (M9)

M9 carries I_tail and sets the common-mode rejection.

**gm/ID selection**: moderate-to-weak inversion (12–18 S/A).
Weak inversion maximizes ro9 → best CMRR.

**L selection**: L9 LONG (maximize ro9 for CMRR and low noise coupling).
L9 = 2–5 × L_min is typical.

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W9 = I_tail / J_n(gm_id_M9, L9)
```

### Step 10 — Set Bias Voltages

The telescopic cascode requires 4 bias voltages:
```
Vbn_cas  : gate of NMOS cascode M3  → sets VDS of M1
Vbp      : gate of PMOS load M5      → sets ID through M5
Vbp_cas  : gate of PMOS cascode M7   → sets VDS of M5
Vbn      : (if separate NMOS load)    → or use CMFB to control M5 gate
```

**Vbn_cas setting** (critical for headroom):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Vbn_cas = Vov1 + Vov3 + VTN3
        [ensures M1 stays in saturation with minimum headroom waste]
```

For a wide-swing (Sooch) cascode bias:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Vbn_cas = Vov1 + VTN3
        [saves one Vov of headroom — M1 operates at VDS = Vov1]
```

**Vbp_cas setting**:
```
Vbp_cas = VDD - |Vov5| - |Vov7| - |VTP7|
```

### Step 11 — Verify All Constraints

[EQ §D — slew rate, §G — swing, §E — noise]

**Phase margin check** (MANDATORY for TCO):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
ω_c = gm1 / CL_total
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p2 = gm3 / Cp2     [compute Cp2 from parasitic caps]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p3 = gm7 / Cp3     [compute Cp3 from parasitic caps]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PM_est = 90° - arctan(ω_c/p2) - arctan(ω_c/p3)
If PM_est < PM_target + 5°: increase gm3 and/or gm7, or reduce gm1 (lower GBW)
```

**Slew rate check**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR = I_tail / CL_total
If SR < SR_target → increase I_tail (but check power)
```

**Output swing check**:
```
V_out,max = VDD - |Vov5| - |Vov7|   [compute Vov from LUT or 2ID/gm]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = Vov1 + Vov3
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_swing_diff = 2 × (V_out,max - V_out,min)
Check vs user spec. If insufficient → reduce Vov (increase gm/ID, larger W) or increase VDD.
```

**ICMR check**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm,min = Vov9 + VTN + Vov1
V_cm,max = VDD - |Vov5| - |Vov7| + VTN + Vov1
Check: V_cm_ref falls within [V_cm,min, V_cm,max]
If not → adjust V_cm_ref or consider folded cascode
```

**Noise check** (if noise spec exists):
```
S_in(f)² at specified frequency [EQ §E]
If noise too high → increase W1·L1 (for 1/f) or increase gm1 (for thermal)
```

**Gain check**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout_ncas = gm3·ro3·ro1  [from LUT values]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout_pcas = gm7·ro7·ro5
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v = gm1 × (Rout_ncas ∥ Rout_pcas)
If A_v < A0_target → increase L (for higher ro) or add gain boosting
```

**Power check**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
P_total = VDD × I_tail
If P_total > P_max → increase gm/ID of DIFF_PAIR (same gm with less current)
```

### Step 12 — Design CMFB Circuit

**Set V_cm_ref**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm_ref = (V_out,max + V_out,min) / 2
         = (VDD - |Vov5| - |Vov7| + Vov1 + Vov3) / 2
```

**Choose CMFB type**:
- For SC applications: switched-capacitor CMFB (standard choice)
- For continuous-time: resistive or active CMFB

**CMFB loop bandwidth**:
```
f_cmfb > 2 × GBW   [CMFB must be faster than signal path]
```

### Step 13 — Mismatch Check (if offset spec exists)

→ Invoke `general/knowledge/mismatch-pvt.md`

```
σ(Vos) from Pelgrom model at chosen W1·L1
If 3σ(Vos) > Vos_max → increase W1·L1 (but check BW impact)
```

**Note**: TCO offset is determined primarily by M1/M2 mismatch and M5/M6
(or M3/M4) mismatch, same as any cascode topology. Cascode devices
M3 and M7 contribute negligible offset.

### Step 14 — Package and Hand Off to Simulation

Assemble the complete sizing:
- All W, L, M (multiplier) for each Role
- Bias voltages: Vbn_cas, Vbp, Vbp_cas
- V_cm_ref for CMFB
- I_tail value
- Record all assumptions in the Assumption Ledger [APPROX template]

→ Hand off to `general/flow/simulation-verification.md`

---

## Output Format

Present sizing by Role. Include the reasoning chain for each parameter.

```
TCO INITIAL SIZING — Iteration 1
=================================

Role: DIFF_PAIR (M1a, M1b)
  gm/ID target : 12 S/A (moderate inversion)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  gm1 required : 628 µS (= 2π × 100MHz × 1pF)
  ID1          : 52.3 µA (= 628µS / 12)
  I_tail       : 104.6 µA
  L            : 0.3 µm (from A0 sweep: A_i = 28 → A0_upper = 28²/2 = 53 dB ✅)
  W            : 12 µm (from LUT at gm/ID=12, L=0.3)
  fT           : 8.5 GHz >> 5×GBW = 500 MHz ✅
  Vov          : 167 mV

Role: NCAS (M3a, M3b)
  gm/ID target : 10 S/A (moderate inversion, speed priority)
  L            : 0.3 µm (match DIFF_PAIR for gain)
  W            : 10 µm
  gm3          : 523 µS
  Vov          : 200 mV
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  p2 check     : Cp2 ≈ 60fF → p2 = 523µ/60f = 8.7 GHz >> 3×ω_c = 1.9 GHz ✅

Role: PLOAD (M5a, M5b)
  gm/ID target : 12 S/A (moderate, balance noise and area)
  L            : 0.5 µm (long for gain — ro5 sets Rout_pcas)
  W            : 18 µm
  gm5          : 628 µS
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  Noise factor : gm5/gm1 = 1.0 → noise penalty 2× ⚠️ reduce gm5 if noise-critical
  Vov          : 167 mV

Role: PCAS (M7a, M7b)
  gm/ID target : 10 S/A (speed priority — p3 is binding)
  L            : 0.18 µm (short for speed)
  W            : 20 µm
  gm7          : 523 µS
  Vov          : 200 mV
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  p3 check     : Cp3 ≈ 90fF → p3 = 523µ/90f = 5.8 GHz > 3×ω_c = 1.9 GHz ✅

Role: TAIL (M9)
  gm/ID target : 15 S/A (moderate-weak, maximize ro9 for CMRR)
  L            : 1.0 µm (long for high impedance)
  W            : 24 µm
  I_tail       : 104.6 µA

Bias Voltages:
  Vbn_cas      : 0.57 V (= Vov1 + VTN3 for wide-swing bias)
  Vbp_cas      : 1.23 V (= VDD - |Vov5| - |VTP7|)
  V_cm_ref     : 0.90 V (mid-swing)

Summary:
  A0_est       : 53 dB (target 50 dB, margin +3 dB ✅)
  GBW_est      : 100 MHz (target 100 MHz ✅)
  PM_est       : ~72° (target 60° ✅) [two NDP at 5.8 and 8.7 GHz]
  SR_est       : 105 V/µs (target 50 V/µs ✅)
  P_est        : 188 µW (budget 500 µW ✅)
  V_swing_diff : 2 × (1.8 - 0.167 - 0.200 - 0.200 - 0.167) = 2.13 Vpp
  ICMR         : [0.57V, 1.23V]

→ Proceeding to simulation
```
