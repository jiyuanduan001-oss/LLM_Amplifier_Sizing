# FC-OTA Design Flow Skill

## Purpose

Sizing procedure for the single-stage fully-differential Folded-Cascode OTA.
Invoked by Circuit Design Flow when topology is identified as FC-OTA.

## References

- Equations: `circuit-specific/fc-ota/fc-ota-equation.md` (cite as [EQ §X])
- Approximations: `circuit-specific/fc-ota/fc-ota-approximation.md` (cite as [APPROX S##])
- LUT queries: `general/knowledge/device-data-lut.md` (cite as [LUT])
- Mismatch/PVT: `general/knowledge/mismatch-pvt.md`

---

## Key Differences from 5T OTA and TSM

1. **Single-stage, high gain**: (gm·ro)² gain without needing a second stage
2. **No compensation capacitor**: single dominant pole → no Cc, no RHP zero
3. **More noise sources**: folding current sources inject noise directly
4. **Output swing limited by 4×Vov**: cascode stacks consume headroom
5. **Wider input CM range** than telescopic (fold decouples input from output)
6. **CMFB mandatory** for fully-differential version
7. **Vov optimization is critical**: input pair wants LOW Vov (noise, gm), current sources want HIGH Vov (reduce noise, save headroom)

---

## Design Procedure

### Step 1 — Select gm/ID for INPUT_PAIR (M1)

gm/ID sets the noise-speed-power tradeoff for the input pair.

| GBW range     | Recommended gm/ID | Inversion   |
|--------------|--------------------|-------------|
| < 10 MHz      | 15–20 S/A          | Moderate–weak |
| 10–100 MHz    | 10–15 S/A          | Moderate     |
| > 100 MHz     | 5–10 S/A           | Strong       |

**For low noise**: push gm/ID higher (more gm per µA → lower thermal noise).
But: higher gm/ID → lower fT → folding pole may approach GBW.

**LUT query** [LUT]:
```
lut_query(device='nfet', metric='gm_id', L=L_candidate)
→ verify target gm/ID exists
→ read fT (must be > 5× GBW)
→ read gm_gds for gain check in Step 3
```

### Step 2 — Derive gm1, I1, and Current Budget from GBW

[EQ §C]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm1_required = 2π × GBW × CL

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
I1 = gm1_required / gm_id_target
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
I_tail = 2 × I1
```

**Current distribution**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
I_fold = k × I1    where k = 1.2–2.0 (design choice)
```

Larger k → more headroom margin, better CMRR, but more power and more noise
from current sources. Start with k = 1.5.

```
I_NMOS_CS = I_PMOS_CS = I_fold
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
P_total = (I_tail + 2×I_fold) × VDD
```

**Power check**:
```
If P_total > P_max → increase gm/ID of input pair or reduce k
```

### Step 3 — Select L for Gain Requirement

[EQ §A, APPROX S01]

The FC-OTA achieves gain ≈ (gm·ro)² in a single stage. The gain requirement
sets minimum L for the cascode and current source devices.

**Sweep procedure** [LUT]:
```
For L_candidate in [Lmin, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0] µm:
  For each stack (NMOS and PMOS):
    gm_gds_casc = lut_query(device, metric='gm_gds', L=L_candidate)
    gm_gds_cs   = lut_query(device, metric='gm_gds', L=L_cs_candidate)
    R_out_stack ≈ gm_gds_casc × gm_gds_cs    [in units of 1/gm]

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  A0_upper = gm1 × R_out_n ∥ R_out_p    [compute numerically]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  A0_upper_dB = 20 × log10(A0_upper)

  If A0_upper_dB ≥ A0_target_dB + 3:
    L_selected = L_candidate
    BREAK
```

**Typical L assignment**:
- INPUT_PAIR (M1): L_selected (moderate — balance gain and speed)
- NMOS_CASC (M3): L_selected or shorter (speed-critical for p_fold)
- NMOS_CS (M5): L_selected or longer (gain, low noise)
- PMOS_CASC (M7): L_selected
- PMOS_CS (M9): L_selected or longer (gain, low noise)
- TAIL: ≥ L_selected (CMRR benefits from long L)

### Step 4 — Size INPUT_PAIR (M1)

```
J_n = lut_query(device='nfet', metric='id_w', L=L_M1) at gm_id_target
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W1 = I1 / J_n
```

**Noise check**: if noise spec exists, verify W1·L1 provides adequate 1/f noise.
If not → increase W1·L1 (trade area for noise).

### Step 5 — Size NMOS_CASC (M3) — CRITICAL for Speed

[EQ §B — folding pole, APPROX S04]

M3 is the speed bottleneck. It must provide high gm3 relative to C_fold.

**gm/ID selection**: LOW gm/ID (5–10 S/A) → strong inversion → high Vov_M3
→ high gm3/Cgs3 ratio → fast cascode.

⚠️ **Constraint**: Vov_M3 < Vth_M1 (for CM input range to reach VSS).
Check: if Vov_M3 > Vth_M1, the input pair cannot turn on at V_cm = VSS.

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_M3 = 5–8 S/A (strong inversion, speed priority)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W3 = I_fold / J_n(gm_id_M3, L_M3)
```

**Verify folding pole** [EQ §B]:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm3 = gm_id_M3 × I_fold
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Cgs3 ≈ (2/3)·W3·L3·Cox    [or from LUT Cgg]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
fp_fold = gm3 / (2π × (Cgs3 + Csb3 + Cdb1))

Check: fp_fold > 3 × GBW?
  YES → ✅
  NO  → reduce gm/ID of M3 further, or reduce L3 (but check gain)
```

### Step 6 — Size NMOS_CS (M5) — Noise vs Gain

[EQ §E — noise, EQ §A — gain]

M5 carries I_fold per side. Its gm5 directly adds to input-referred noise.

**gm/ID selection**: LOW gm/ID (4–8 S/A) → very strong inversion → HIGH Vov_M5
→ minimizes gm5 → reduces noise contribution.

But: Vov_M5 consumes output headroom [EQ §G].

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_M5 = 5–8 S/A
L_M5 ≥ L_selected (long L for high ro5 → gain, and low 1/f noise)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W5 = I_fold / J_n(gm_id_M5, L_M5)
```

### Step 7 — Size PMOS_CASC (M7) and PMOS_CS (M9)

Mirror the NMOS cascode/CS sizing strategy for the PMOS stack:

**M7 (PMOS_CASC)**: moderate-to-strong inversion for speed.
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_M7 = 6–10 S/A
L_M7 = L_selected
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W7 = I_fold / J_p(gm_id_M7, L_M7)
```

**M9 (PMOS_CS)**: strong inversion for low noise, long L for gain.
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_M9 = 5–8 S/A
L_M9 ≥ L_selected
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W9 = I_fold / J_p(gm_id_M9, L_M9)
```

### Step 8 — Size TAIL (M_tail)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
I_tail = 2 × I1
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
gm_id_TAIL = 10–12 S/A (accuracy, not speed)
L_TAIL ≥ max(L_selected, 1.0 µm)  (long L for CMRR)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
W_tail = I_tail / J_n(gm_id_TAIL, L_TAIL)
```

### Step 9 — Verify Output Swing

[EQ §G]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = Vov_M5 + Vov_M3
V_out,max = VDD - |Vov_M9| - |Vov_M7|
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_swing = V_out,max - V_out,min

Check: V_swing ≥ V_swing_required?
  NO → reduce Vov of cascode/CS devices (higher gm/ID, but check noise/speed)
     → or use wide-swing cascode biasing
```

### Step 10 — Verify Noise

[EQ §E, APPROX S08]

⚠️ **Always use full noise expression** — current source noise is NOT negligible.

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_thermal² = 2×(8kT)/(3·gm1) × [1 + gm5/gm1 + gm9/gm1]

Check: S_thermal at target frequency ≤ spec?
  NO → increase gm1 (more current or lower gm/ID for input pair)
     → decrease gm5, gm9 (increase Vov of current sources)
     → increase L5, L9 (reduce 1/f noise from current sources)
```

### Step 11 — Verify CMRR, PSRR

[EQ §F, APPROX S07]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
CMRR ≈ A0 × gm_gds_TAIL
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PSRR⁻ ≈ A0 × gm3·ro3
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PSRR⁺ ≈ A0 × gm7·ro7
```

If below target → increase L of the limiting device.

### Step 12 — CMFB Sizing (if fully differential)

[EQ §H]

The CMFB is a separate design sub-problem. Key requirements:
- CMFB UGB ≥ (1/3) × DM UGB
- CMFB PM ≥ 45°
- CMFB detection must not load the DM output (use large R or SC detection)
- CMFB output CM reference = (V_out,min + V_out,max) / 2

For CT-CMFB with resistive detection:
```
R_detect >> R_out (to avoid loading)
Error amp: simple diff pair, gm_error × R_out_error provides loop gain
```

For SC-CMFB:
```
C2 (sense cap) samples output CM
C1 (reference cap) sets Vcmref
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
C1 ≈ C2/4 to C2/10 (Ken Martin guideline)
Clock: two-phase non-overlapping
```

### Step 13 — Package and Hand Off to Simulation

Assemble:
- All W, L, M for each Role
- Bias voltages: Vbn_cs, Vbn_casc, Vbp_cs, Vbp_casc
- CMFB component values
- Record all assumptions in Assumption Ledger

→ Proceed to `general/flow/simulation-verification.md`

---

## Exit Criteria

| Flag              | Condition                          | Source       |
|-------------------|------------------------------------|-------------|
| A0                | SPICE DC gain ≥ A0_target          | SPICE AC     |
| GBW               | SPICE GBW ≥ GBW_target             | SPICE AC     |
| PM                | SPICE PM ≥ PM_target               | SPICE AC     |
| SR                | SPICE SR ≥ SR_target               | SPICE tran   |
| output_swing      | Measured swing ≥ swing_target      | SPICE tran   |
| all_saturated     | All transistors in saturation      | OP (DC)      |
| CMFB_stable       | CMFB loop PM > 45°                 | CMFB AC sim  |
| Voc1_correct      | Output CM ≈ Vref within 10mV       | OP (DC)      |
| noise (if spec)   | SPICE noise ≤ target               | SPICE noise  |
| CMRR (if spec)    | SPICE CMRR ≥ target                | SPICE AC     |
| PSRR (if spec)    | SPICE PSRR ≥ target                | SPICE AC     |

---

## Output Format

```
FC-OTA INITIAL SIZING — Iteration 1
=====================================

Role: INPUT_PAIR (M1a, M1b) [NMOS]
  gm/ID target : 14 S/A (moderate inversion, low noise)
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  gm1 required : 188 µS (= 2π × 30MHz × 1pF)
  I1 derived   : 13.4 µA
  I_tail       : 26.8 µA
  L            : 0.5 µm
  W            : 12 µm

Role: NMOS_CASC (M3a, M3b) [NMOS]
  gm/ID target : 7 S/A (strong inversion, speed priority)
  I_fold       : 20 µA (k=1.5 × I1)
  L            : 0.5 µm
  W            : 8 µm
  fp_fold      : 850 MHz >> 30 MHz ✅

Role: NMOS_CS (M5a, M5b) [NMOS]
  gm/ID target : 6 S/A (strong inversion, low noise)
  L            : 1.0 µm (long L for gain + noise)
  W            : 10 µm

Role: PMOS_CASC (M7a, M7b) [PMOS]
  gm/ID target : 8 S/A
  L            : 0.5 µm
  W            : 15 µm

Role: PMOS_CS (M9a, M9b) [PMOS]
  gm/ID target : 6 S/A (strong inversion, low noise)
  L            : 1.0 µm
  W            : 18 µm

Role: TAIL (M_tail) [NMOS]
  gm/ID target : 10 S/A
  L            : 1.5 µm (CMRR priority)
  W            : 8 µm

Summary:
  A0_upper     : 72 dB (target 60 dB, margin +12 dB ✅)
  GBW_est      : 30 MHz ✅
  PM_est       : ~85° (fp_fold >> GBW) ✅
  SR_est       : 13.4 V/µs
  V_swing      : 1.2V (VDD=1.8V, 4×Vov≈0.6V)
  P_est        : 120 µW
  Noise note   : gm5/gm1 ≈ 0.64 → CS noise adds 64% to thermal

→ Proceeding to simulation
```
