# R2R Opamp Design Flow Skill

## Purpose

Sizing procedure for the two-stage Rail-to-Rail Input/Output opamp with
constant-gm complementary input (3× current mirror control), folded-cascode
summing circuit with integrated floating class-AB control, and class-AB
push-pull output stage.

## References

- Equations: `circuit-specific/r2r-opamp/r2r-opamp-equation.md`
- Approximations: `circuit-specific/r2r-opamp/r2r-opamp-approximation.md`
- LUT queries: `general/knowledge/device-data-lut.md`
- Sub-circuit identification: `general/knowledge/subcircuit-identify.md`

---

## Key Differences from Other Topologies

1. **Complementary input**: NMOS + PMOS diff pairs in parallel → full CM range
2. **gm control circuit**: 3× current mirrors + switches → extra devices to size
3. **Integrated class-AB**: floating control embedded in summing circuit → no extra bias sources
4. **Two compensation options**: standard Miller or cascoded-Miller (2.5× BW improvement)
5. **SR varies 2×** across CM range — inherent, cannot be eliminated
6. **CMRR limited** by offset change at N/P takeover regions (~43 dB worst-case)
7. **Supply voltage constraint**: V_sup,min = Vgsp + Vgsn + 2·Vdsat

---

## Design Procedure

### Step 0 — Supply Voltage Feasibility Check

[EQ §G, §I]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_sup,min = Vgsp + Vgsn + 2·Vdsat

For typical CMOS: Vgsp ≈ 0.7-0.9V, Vgsn ≈ 0.5-0.7V, Vdsat ≈ 0.15-0.2V
→ V_sup,min ≈ 1.5-1.8V (strong inversion)
→ V_sup,min ≈ 1.2-1.5V (moderate inversion)
```

If VDD < V_sup,min: dead zone appears in CM range → not full rail-to-rail.
Consider weak-inversion input pairs or alternative gm-control method.

### Step 1 — Choose gm/ID for Input Pairs

Both N and P input pairs must be sized. The constant-gm condition requires:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
µN·Cox·(W/L)_N = µP·Cox·(W/L)_P = K

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_in = √(K · Iref)     [for each CM region]
```

**gm/ID selection** (same target for both pairs to ease matching):

| GBW range    | gm/ID | Inversion  | Note |
|-------------|--------|------------|------|
| < 5 MHz      | 15-20  | Moderate-weak | Low power |
| 5-50 MHz     | 10-15  | Moderate   | Balanced |
| > 50 MHz     | 5-10   | Strong     | Speed priority |

⚠️ **Low gm/ID (strong inversion) → large Vov → tighter supply constraint.**
Check that V_sup,min is still met after choosing Vov for both input pairs.

### Step 2 — Derive gm_in, Iref, and Current Budget

[EQ §C, APPROX S02]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_in_required = 2π × GBW × Cc

where Cc is the Miller compensation capacitor (design choice, typically 1-5 pF)
```

Start with Cc estimate: larger Cc → better stability but slower.
Typical starting point: Cc = 2-3 pF for single-digit MHz GBW.

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Iref = gm_in² / K = gm_in² / (µ·Cox·(W/L))

Power budget:
  Both pairs active (middle CM): P_mid = 2×Iref × VDD
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  One pair active (outer CM):    P_out = 4×Iref × VDD (tail = 4×Iref)
  Plus summing + output quiescent
```

### Step 3 — Size Input Pairs (M1-M4)

**N-pair (M1, M2)**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
(W/L)_N = K / (µN·Cox)
J_n = lut_query(device='nfet', metric='id_w', L=L_input) at gm_id_target
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W_N = Iref / J_n
L_N: choose for gain + noise (typically ≥ 2×Lmin)
```

**P-pair (M3, M4)**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
(W/L)_P = K / (µP·Cox) = (µN/µP) × (W/L)_N
J_p = lut_query(device='pfet', metric='id_w', L=L_input) at gm_id_target
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W_P = Iref / J_p
L_P: match L_N for symmetry (or adjust for noise)
```

**Verify**: µN·(W/L)_N ≈ µP·(W/L)_P within 10%.
If µN/µP varies ±15% with process → gm varies ±7.5% additional.

### Step 4 — Size gm-Control Circuit (M5-M10, M29-M31)

**Current switches (M5: NMOS, M8: PMOS)**:
- Must switch fully ON/OFF within the takeover region (~300mV)
- Size for low Vdsat when ON (current path), and fast switching
- Typical: moderate W/L, L = Lmin for speed

**3× current mirrors (M6-M7: NMOS, M9-M10: PMOS)**:
- Mirror ratio = 1:3 (M6 = ref, M7 = 3× output)
- Match carefully for accurate 3× ratio → gm constancy depends on it
- L ≥ 2×Lmin for matching
- W_M7 = 3 × W_M6

**Supply-voltage protection (M29-M31)**: only needed for VDD < 2.9V operation.
Prevents positive feedback loop (M5-M10) from activating when both switches
might conduct simultaneously.

### Step 5 — Size Summing Circuit (M11-M18)

The summing circuit is a folded-cascode structure with two current mirrors:

**P-mirror (M11-M14)**: M11-M12 = mirror pair, M13-M14 = cascode
**N-mirror (M15-M18)**: M17-M18 = mirror pair, M15-M16 = cascode

Sizing follows FC-OTA principles:

**Mirror devices (M11-M12, M17-M18)**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_mirror = 8-12 S/A
L_mirror ≥ L_input (for gain)
I_mirror = Iref (loaded by equal CM currents from both input pair halves)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W_mirror = I_mirror / J(gm_id_mirror, L_mirror)
```

**Cascode devices (M13-M14, M15-M16)**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_cascode = 6-10 S/A (speed priority for poles)
L_cascode ≈ L_mirror
W_cascode: size for adequate gm to push summing-node pole above 3× GBW
```

**First-stage gain check** [EQ §A]:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out1 = (gm13·ro13·ro11) ∥ (gm16·ro16·ro18)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v1 = gm_in × R_out1

Target: A_v1 × A_v2 ≥ A0_target
```

### Step 6 — Size Class-AB Control (M19-M24) and Floating CS (M27-M28)

[EQ §O]

**Floating class-AB transistors (M19: NMOS, M20: PMOS)**:
- These are biased by the cascode current in the summing circuit
- Their W/L ratio relative to the output transistors sets the minimum current:
  I_q,min(output) = I_cascode × (W/L)_out / (W/L)_AB
- Size for desired quiescent current in output transistors

**Diode-connected bias stacks (M21-M22: PMOS, M23-M24: NMOS)**:
- Part of the translinear loops
- Size to match the Vgs requirements of the class-AB control
- Two stacked Vgs allowed (since supply ≥ V_sup,min already accommodates this)

**Floating current source (M27: NMOS, M28: PMOS)**:
- ⚠️ **MUST have identical structure to M19-M20** for VDD-independent Iq
- Same W/L ratios as M19/M20 (or scaled proportionally)
- Verify: floating CS current varies ≤5% across CM range

### Step 7 — Size Output Stage (M25, M26)

[EQ §O, §B]

**PMOS output (M25)** and **NMOS output (M26)**:

```
gm_out_required:
  Miller:         gm_out ≥ 2π × p2_target × CL = 2π × (>3×GBW) × CL
  Cascoded-Miller: gm_out ≥ 2π × p2_target × CL × Cgs_out/Cc
```

```
I_q_out: set by class-AB translinear loop (Step 6)
  Typical: I_q_out = 5-20× Iref (output stage draws more current for drive)

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_out = gm_id_out × I_q_out
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W_out = I_q_out / J(gm_id_out, L_out)
L_out: short (Lmin or 2×Lmin) for speed (fT) and output swing
```

**Output swing check**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = VSS + Vdsat_M26
V_out,max = VDD - |Vdsat_M25|
```

### Step 8 — Choose Compensation Scheme and Size Cc

**Option A: Standard Miller**
```
Cc1, Cc2 around output transistors M25, M26
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm_in / (2π·Cc)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p2 = gm_out / CL

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PM ≈ 90° - arctan(GBW/fp2) - arctan(GBW/f_RHP_zero)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
f_RHP_zero = gm_out/(2π·Cc)

For PM ≥ 60°: need gm_out/CL > 3×GBW AND gm_out/Cc > 3×GBW
→ Cc < gm_out/(3×2π×GBW) AND CL < gm_out/(3×2π×GBW)

Paper result: 2.6 MHz, PM = 66°
```

**Option B: Cascoded-Miller** (insert cascode M14/M16 in Miller loop)
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p2_cascode = (Cc/Cgs_out) × (gm_out/CL) ≈ 2.5 × p2_Miller
→ GBW can be 2.5× higher for same PM

Paper result: 6.4 MHz, PM = 53°
⚠️ Cascoded-Miller can cause peaking at high output currents (>3mA in paper).
    If driving large loads, use standard Miller.
```

### Step 9 — Verify Slew Rate

[EQ §D, APPROX S05]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR_worst = Iref / Cc        [middle CM, both pairs active]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR_best  = 2×Iref / Cc      [outer CM, one pair at 4×Iref]

Check: SR_worst ≥ SR_target?
  NO → increase Iref (more power) or decrease Cc (check PM)
```

### Step 10 — Verify Noise

[EQ §E, APPROX S06]

```
Noise sources (compact topology): input pairs + summing mirrors only
Class-AB and floating CS do NOT contribute (floating architecture)

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_in² ≈ 2×S_input² + summing_mirror_contributions

Check: noise at target frequency ≤ spec?
  NO → increase W·L of input pairs (1/f noise)
     → increase gm_in (thermal noise)
     → increase L of summing mirrors
```

### Step 11 — Verify CMRR

[EQ §F, APPROX S07]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
CMRR_takeover ≈ 43 dB (limited by N/P offset difference over 300mV transition)
CMRR_other ≈ 70 dB

If CMRR_takeover < target:
  → Cannot fundamentally improve beyond ~50 dB in takeover regions
  → Can improve by: better N/P matching, wider takeover regions, trimming
  → Alternative gm-control methods (e.g., max-current selector) may help
```

### Step 12 — Package and Hand Off to Simulation

Assemble all W, L, M for every Role:
- INPUT_N (M1, M2), INPUT_P (M3, M4)
- GM_CTRL (M5-M10, M29-M31)
- SUMMING (M11-M18) with bias voltages Vb1-Vb4
- CLASS_AB (M19-M20), CLASS_AB_BIAS (M21-M24)
- FLOAT_CS (M27-M28)
- OUTPUT_P (M25), OUTPUT_N (M26)
- Compensation: Cc1, Cc2

Record all assumptions in Ledger → proceed to `general/flow/simulation-verification.md`

---

## Exit Criteria

| Flag              | Condition                              | Source          |
|-------------------|----------------------------------------|-----------------|
| A0                | SPICE DC gain ≥ A0_target              | SPICE AC        |
| GBW               | SPICE GBW ≥ GBW_target at all Vcm     | SPICE AC sweep  |
| PM                | SPICE PM ≥ PM_target at all Vcm       | SPICE AC sweep  |
| gm_constancy      | gm variation ≤ 15% over CM range      | SPICE DC sweep  |
| SR                | SR_worst ≥ SR_target                   | SPICE tran      |
| output_swing      | Rail-to-rail output verified           | SPICE tran      |
| input_range       | Full CM range functional               | SPICE DC sweep  |
| all_saturated     | All transistors in saturation          | OP (DC)         |
| class_AB_Iq       | Output quiescent current correct       | OP (DC)         |
| Iq_vs_VDD         | Iq varies ≤5% over VDD range          | SPICE sweep     |
| noise (if spec)   | SPICE noise ≤ target                   | SPICE noise     |
| CMRR (if spec)    | SPICE CMRR ≥ target                    | SPICE AC        |

---

## Output Format

```
R2R OPAMP INITIAL SIZING — Iteration 1
=========================================

Role: INPUT_N (M1, M2) [NMOS]
  gm/ID target : 12 S/A
  L            : 2 µm
  (W/L)_N      : 45/2
  Iref         : 2.5 µA
  gm_N         : 30 µS

Role: INPUT_P (M3, M4) [PMOS]
  gm/ID target : 12 S/A
  L            : 2 µm
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  (W/L)_P      : 135/2  [= (µN/µP) × (W/L)_N ≈ 3×]
  Iref         : 2.5 µA
  gm_P         : 30 µS  [matched to gm_N ✅]

Role: GM_CTRL — 3× mirrors
  M6 (ref)     : 30/3, M7 (3×): 90/3 [NMOS]
  M9 (ref)     : 30/3, M10(3×): 90/3 [PMOS]
  M5 (N-switch): 30/2, M8 (P-switch): 90/2

Role: SUMMING (M11-M18)
  P-mirror M11-M12 : 90/2 each
  P-cascode M13-M14: 50/2 each
  N-mirror M17-M18 : 30/3 each
  N-cascode M15-M16: 50/2 each

Role: CLASS_AB (M19-M20) + FLOAT_CS (M27-M28)
  M19 (NMOS) : 5/1, M20 (PMOS): 15/1
  M27 (NMOS) : 5/1, M28 (PMOS): 15/1 [identical structure ✅]

Role: OUTPUT (M25 PMOS, M26 NMOS)
  M25: 200/1, M26: 100/1
  Iq_out: 90 µA per device
  gm_out: 1.2 mS

Compensation: Miller, Cc = 2 pF

Summary:
  A0_est       : 85 dB (A_v1 ≈ 55dB × A_v2 ≈ 30dB)
  GBW_est      : 2.4 MHz (= 30µS / (2π×2pF))
  PM_est       : ~65°
  SR_worst     : 1.25 V/µs (middle CM)
  SR_best      : 2.5 V/µs (outer CM)
  Input range  : VSS-0.4V to VDD+0.5V ✅
  Output swing : VSS+0.1V to VDD-0.2V ✅
  P_total      : ~0.5 mW @ 3V
  gm variation : ≤15% ✅

→ Proceeding to simulation
```
