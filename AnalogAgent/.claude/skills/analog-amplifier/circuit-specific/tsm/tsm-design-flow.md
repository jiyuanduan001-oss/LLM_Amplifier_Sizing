# TSM Design Flow

## Purpose

Step-by-step sizing procedure for the Two-Stage Miller compensated OTA.
Invoked after circuit-understanding identifies the topology as TSM.

## References

- Equations: `tsm-equation.md`
- Root-cause diagnosis: `tsm-root-cause-diagnosis.md`

## Rules

1. Execute steps in order. Do not skip.
2. All computations in Python. No mental arithmetic.
3. After simulation failure, use `tsm-root-cause-diagnosis.md`. Do not improvise fixes.

---

## Bias Current Relationships

```
I_bias → M5 (BIAS_GEN, diode-connected unit cell, M5_M = 1)
I_tail = (M6_M / M5_M) × I_bias        [TAIL mirrors BIAS_GEN]
ID3 = ID4 = I_tail / 2                  [each DIFF_PAIR device]
ID1 = ID2 = ID3                         [LOAD carries same current]
ID7 = ID8 = (M8_M / M5_M) × I_bias     [OUTPUT_BIAS mirrors BIAS_GEN]
P = VDD × (I_bias + I_tail + ID7)
```

---

## Sizing Procedure

### Step 1 — Initial sizing: DIFF_PAIR (M3, M4)

Goal: determine gm, gm/ID, L for the input pair, then derive all
device parameters from LUT.

**1a. Estimate Cc (starting heuristic):**

Cc is needed to derive gm3 but is not yet final. Use:
```
Cc_initial = 0.2 × CL    (for CL > 5 pF)
Cc_initial = 0.5 × CL    (for CL ≤ 5 pF)
```
This will be refined in Step 5.

**1b. Determine gm from GBW spec:**
```
gm3 = 2π × GBW × Cc_initial
```

**1c. Choose gm/ID (empirical, based on bandwidth):**

| GBW range   | Recommended gm/ID | Inversion      | Comment                    |
|-------------|-------------------|----------------|----------------------------|
| < 10 MHz    | 14–30 S/A         | Moderate–weak  | Lower power design         |
| 10–100 MHz  | 10–14 S/A         | Moderate       | Balanced across all aspects |
| > 100 MHz   | 5–10 S/A          | Strong         | High speed                 |

**1d. Determine L from gain requirement:**

Sweep available L values in the LUT. For each L, query:
```
gm_gds_M3 = lut_query('nfet', 'gm_gds', L, gm_id_val=(gm/ID)_3)
```
Pick the shortest L where `gm_gds_M3 / 2 ≥ sqrt(A0_target_linear)`.

This distributes gain roughly equally between the two stages (in dB).
If no L satisfies this, pick L with the highest gm_gds available;
the second stage provides additional gain. Total gain is verified in Step 6.

**1e. Derive all DIFF_PAIR parameters from LUT:**

With (gm3, L3, (gm/ID)_3) now fixed, derive all parameters from LUT:
```
ID3   = gm3 / (gm/ID)_3
I_tail = 2 × ID3
id_w3 = lut_query('nfet', 'id_w',  L3, gm_id_val=(gm/ID)_3)   # µA/µm
W3    = ID3 / id_w3                                              # µm
gds3  = gm3 / lut_query('nfet', 'gm_gds', L3, gm_id_val=(gm/ID)_3)
ft3   = lut_query('nfet', 'ft',    L3, gm_id_val=(gm/ID)_3)    # Hz
Cgs3  = lut_query('nfet', 'cgs_w', L3, gm_id_val=(gm/ID)_3) × W3 × 1e-6  # F
Cgd3  = lut_query('nfet', 'cgd_w', L3, gm_id_val=(gm/ID)_3) × W3 × 1e-6  # F
vov3  = lut_query('nfet', 'vov',   L3, gm_id_val=(gm/ID)_3)    # V
```

### Step 2 — Initial sizing: LOAD (M1, M2)

ID1 = ID3 (already known from Step 1).

**2a. Choose gm/ID for LOAD:**

Use 10–14 S/A (moderate inversion).
Higher gm1 → higher mirror pole p3 → better PM. Do NOT push LOAD into
weak inversion (degrades p3).

**2b. Determine L from gain requirement:**

Step 1d used the approximation `A_v1 ≈ gm_gds_M3 / 2`. Now with the LOAD,
compute the actual first-stage gain `A_v1 = gm3 / (gds3 + gds1)`. Sweep L1 candidates:

```
For each L1:
  gds1 = (gm/ID)_1 × ID1 / lut_query('pfet', 'gm_gds', L1, gm_id_val=(gm/ID)_1)
  A_v1 = gm3 / (gds3 + gds1)
  If A_v1 ≥ sqrt(A0_target_linear): select this L1, BREAK
```

If no L1 satisfies this: increase L3 (from Step 1d) and re-derive.

**2c. Derive all LOAD parameters from LUT:**

With (ID1, L1, (gm/ID)_1) now fixed:
```
gm1   = (gm/ID)_1 × ID1
id_w1 = lut_query('pfet', 'id_w',  L1, gm_id_val=(gm/ID)_1)   # µA/µm
W1    = ID1 / id_w1                                              # µm
gds1  = gm1 / lut_query('pfet', 'gm_gds', L1, gm_id_val=(gm/ID)_1)
ft1   = lut_query('pfet', 'ft',    L1, gm_id_val=(gm/ID)_1)    # Hz
Cgs1  = lut_query('pfet', 'cgs_w', L1, gm_id_val=(gm/ID)_1) × W1 × 1e-6  # F
Cgd1  = lut_query('pfet', 'cgd_w', L1, gm_id_val=(gm/ID)_1) × W1 × 1e-6  # F
vov1  = lut_query('pfet', 'vov',   L1, gm_id_val=(gm/ID)_1)    # V
```

### Step 3 — Initial sizing: OUTPUT_CS (M7)

The second stage must provide sufficient gm7 for phase margin (output pole
p2 must be far above the unity-gain frequency).

**3a. Determine gm7 from PM constraint:**

PM requires p2 > 2.2 × ω_c for 60° PM (single non-dominant pole rule):
```
ω_c = gm3 / Cc_initial
gm7_required ≥ 2.2 × ω_c × CL    (using simplified p2 ≈ gm7/CL)
```

Also check slew rate constraint on second-stage current.
SR- = min(I_tail/Cc, ID7/(Cc+CTL)), so to meet SR-_target from
the ID7 term:
```
ID7_from_SR = SR_neg_target × (Cc_initial + CL)    (if SR- spec exists)
ID7_from_PM = gm7_required / (gm/ID)_7
ID7 = max(ID7_from_PM, ID7_from_SR)
```

**3b. Choose gm/ID and L for OUTPUT_CS:**

Use (gm/ID)_7 = 9–12 S/A (moderate-to-strong inversion for speed).
L7 can be shorter than DIFF_PAIR (M7 gain is secondary to speed).

**3c. Derive all OUTPUT_CS parameters from LUT:**

With (ID7, L7, (gm/ID)_7) now fixed:
```
gm7   = (gm/ID)_7 × ID7
id_w7 = lut_query('pfet', 'id_w',  L7, gm_id_val=(gm/ID)_7)   # µA/µm
W7    = ID7 / id_w7                                              # µm
gds7  = gm7 / lut_query('pfet', 'gm_gds', L7, gm_id_val=(gm/ID)_7)
ft7   = lut_query('pfet', 'ft',    L7, gm_id_val=(gm/ID)_7)    # Hz
Cgs7  = lut_query('pfet', 'cgs_w', L7, gm_id_val=(gm/ID)_7) × W7 × 1e-6  # F
Cgd7  = lut_query('pfet', 'cgd_w', L7, gm_id_val=(gm/ID)_7) × W7 × 1e-6  # F
vov7  = lut_query('pfet', 'vov',   L7, gm_id_val=(gm/ID)_7)    # V
```

### Step 4 — Initial sizing: BIAS_GEN (M5), TAIL (M6), OUTPUT_BIAS (M8)

M5 is the diode-connected reference. M6 and M8 mirror M5.

**4a. Choose gm/ID and L for bias mirrors:**

Use (gm/ID)_5 = 10–14 S/A. Initial L5 = 1.08 µm.

**4b. Determine multiplier ratios:**

M5 (BIAS_GEN) is the unit cell with M5_M = 1:
```
M5_M = 1
M6_M = round(I_tail / I_bias)     [TAIL mirrors BIAS_GEN]
M8_M = round(ID7 / I_bias)        [OUTPUT_BIAS mirrors BIAS_GEN]
```

**Mirror ratio check (MANDATORY):**
```
If max(M6_M, M8_M) > 8: ⚠️ high mirror ratio → risk of VDS compression
  → Recommend increasing I_bias to reduce ratio
```

**4c. Derive single-finger (unit cell) parameters from LUT:**

LUT describes a single transistor. Use the per-finger current
(I_bias = I_tail / M6_M) to derive the unit-cell parameters:

```
ID_finger = I_bias                                                # A per finger
gm_finger = (gm/ID)_5 × ID_finger
id_w5     = lut_query('nfet', 'id_w',  L5, gm_id_val=(gm/ID)_5) # µA/µm
W5        = ID_finger / id_w5                                     # µm (per finger)
gds_finger = gm_finger / lut_query('nfet', 'gm_gds', L5, gm_id_val=(gm/ID)_5)
ft5       = lut_query('nfet', 'ft',    L5, gm_id_val=(gm/ID)_5)  # Hz (same per finger)
Cgs_finger = lut_query('nfet', 'cgs_w', L5, gm_id_val=(gm/ID)_5) × W5 × 1e-6  # F
Cgd_finger = lut_query('nfet', 'cgd_w', L5, gm_id_val=(gm/ID)_5) × W5 × 1e-6  # F
vov5      = lut_query('nfet', 'vov',   L5, gm_id_val=(gm/ID)_5)  # V (same per finger)
```

**4d. Scale to total M6 (TAIL) device:**

```
gm6  = gm_finger × M6_M
gds6 = gds_finger × M6_M
Cgs6 = Cgs_finger × M6_M
Cgd6 = Cgd_finger × M6_M
```

**4e. OUTPUT_BIAS (M8) and BIAS_GEN (M5):**

M8 shares the same W and L as M5 (single finger = unit cell),
scaled by M8_M fingers:
```
L8 = L5,  W8 = W5,  M8_M = round(ID7 / I_bias)
gm8  = gm_finger × M8_M
gds8 = gds_finger × M8_M
```

M5 is the unit cell itself:
```
L5 = L5,  W5 = W5,  M5_M = 1
```

### Step 5 — Compensation: Cc and Rc

**5a. Refine Cc from GBW constraint:**
```
Cc = gm3 / (2π × GBW)
```

Verify PM (with Rc cancelling p2):
```
p3 = gm1 / (2 × Cgs1)                     (simplified, Cgs dominates)
p4 = gm7 / (Cgs7 + Cgd2 + Cgd4)           (simplified C1 at net5)
PM_est = 90° - arctan(ω_c/p3) - arctan(ω_c/p4)
If PM_est < PM_target + 5°: increase Cc (trades GBW for PM)
```

**5b. Nulling resistor Rc (LHP zero cancels output pole p2):**
```
Rc = (1/gm7) × (1 + CL/Cc)
```
This moves the RHP zero to LHP and places it on top of p2 ≈ gm7/CL,
cancelling the output pole. PM is then set by p3 and p4 only.

### Step 6 — Analytical spec evaluation

All devices are now sized with LUT data. Compute every spec using the
full equations from `tsm-equation.md`. **All calculations MUST be
done using Python** — do not compute mentally.

Note: since M3≡M4, `gm4=gm3, gds4=gds3, Cgd4=Cgd3`.
Since M1≡M2, `gm2=gm1, gds2=gds1, Cgs2=Cgs1`.
I_bias is from the spec form.

```
A_v1  = gm3 / (gds3 + gds1)
A_v2  = gm7 / (gds7 + gds8)
A0    = A_v1 × A_v2
GBW   = gm3 / (2π × Cc)
ω_c   = 2π × GBW
C1    = Cgs7 + Cgd2 + Cgd4                  (simplified 1st-stage output cap, net5)
CTL   = CL + Cgd7 + Cgd8                    (simplified total output cap)
Rc    = (1/gm7) × (1 + CL/Cc)              (LHP zero cancels p2)
p3    = gm1 / (2 × Cgs1)                    (simplified mirror pole)
p4    = gm7 / C1                             (compensation pole from Rc–C1)
PM    = 90° - arctan(ω_c/p3) - arctan(ω_c/p4)   (p2 cancelled by Rc)
SR+   = I_tail / Cc
SR-   = min(I_tail / Cc, ID7 / (Cc + CTL))
Swing = VDD - |vov7| - vov8
P     = VDD × (I_bias + I_tail + ID7)

# CMRR (see tsm-equation.md for accuracy caveats near M6 saturation boundary)
CMRR  = 2·gm3·gm1 / [(gds3+gds1)·gds6]

# PSRR⁻: two coupling paths (see tsm-equation.md for derivation)
A_VSS_M8 = gds8 / (gds7 + gds8)
A_VSS_M6 = gds6·gds1·gm7 / [2·(gm1+gds1)·(gds3+gds1)·(gds7+gds8)]
PSRR⁻    = A0 / (A_VSS_M8 + A_VSS_M6)

# PSRR⁺: net5 overshoots VDD, partially cancelling M7 coupling (see tsm-equation.md)
PSRR⁺    = A0 · (gds7 - gds8) / |gds7 - gm7·gds3/gm1|
```

Print the results and compare against user spec targets:

```
ANALYTICAL SPEC CHECK
======================
Spec          | Analytical | Target      | Status
A0            | <> dB      | <> dB       | ✅/❌
GBW           | <> MHz     | <> MHz      | ✅/❌
PM            | <>°        | <>°         | ✅/❌
...
[all active spec targets from spec form]
```

**Decision:**
- All specs met → proceed to Step 7 (simulation).
- Any spec failed → invoke `tsm-root-cause-diagnosis.md` to identify
  which device parameter to adjust. Apply the fix, re-derive LUT values
  for the affected role, and repeat Step 6.
- After 5 analytical iterations, proceed to Step 7 regardless.

### Step 7 — Submit to simulation

Call `convert_sizing` and `simulate_circuit`:

```python
from tools import convert_sizing, simulate_circuit

result = convert_sizing(
    topology='twostage',
    roles_raw={
        "DIFF_PAIR":    {"gm_id_target": (gm/ID)_3, "L_guidance_um": L3, "id_derived": ID3},
        "LOAD":         {"gm_id_target": (gm/ID)_1, "L_guidance_um": L1, "id_derived": ID1},
        "OUTPUT_CS":    {"gm_id_target": (gm/ID)_7, "L_guidance_um": L7, "id_derived": ID7},
        "BIAS_GEN":     {"gm_id_target": (gm/ID)_5, "L_guidance_um": L5, "id_derived": I_bias},
        "TAIL":         {"gm_id_target": 0,          "L_guidance_um": L5, "id_derived": I_tail},
        "OUTPUT_BIAS":  {"gm_id_target": 0,          "L_guidance_um": L5, "id_derived": ID7},
    },
    Ib_a=I_bias,
    Cc_f=Cc,
    Rc_ohm=Rc,
    l_overrides={"DIFF_PAIR": L3, "LOAD": L1, "OUTPUT_CS": L7,
                 "BIAS_GEN": L5, "TAIL": L5, "OUTPUT_BIAS": L5},
)

sim = simulate_circuit(
    result["params"],
    config_path=result["config_path"],
    corner=corner,            # from validated spec form (e.g. 'ff')
    temperature=temperature,  # from validated spec form (e.g. 40)
)
```

**IMPORTANT:** `corner` and `temperature` MUST come from the validated spec form
(Stage [1]). These are the same values used for LUT queries. Omitting them causes
the simulator to fall back to TOML defaults (typically tt/27°C), creating a
mismatch between the LUT-based sizing and the SPICE verification.

→ Proceed to `general/flow/simulation-verification.md` with the results.

---

## Simulation Interface — Two-Stage Miller OTA

### CircuitCollector Configuration

- **Config path**: `config/skywater/opamp/tsm.toml`
- **Topology**: Two-stage Miller-compensated OTA (tsm), 8 transistors (M1–M8) + Cc

### Role → Device Mapping

| Role | Primary Device | Mirror | Type | CC Param Prefix |
|------|---------------|--------|------|-----------------|
| DIFF_PAIR | M3 | M4 (via TOML) | nfet | M3_L, M3_WL_ratio, M3_M |
| LOAD | M1 | M2 (via TOML) | pfet | M1_L, M1_WL_ratio, M1_M |
| BIAS_GEN | M5 | — | nfet | M5_L, M5_WL_ratio, M5_M |
| TAIL | M6 | — | nfet | M6_L, M6_WL_ratio, M6_M |
| OUTPUT_CS | M7 | — | pfet | M7_L, M7_WL_ratio, M7_M |
| OUTPUT_BIAS | M8 | — | nfet | M8_L, M8_WL_ratio, M8_M |

Mirror constraints:
- M5 (BIAS_GEN) and M6 (TAIL) share per-finger W/L. Ratio via M6_M/M5_M.
- M8 (OUTPUT_BIAS) mirrors M5. Same per-finger W/L. Ratio via M8_M/M5_M.

### How to Run Simulation

After computing sizing targets for each role (gm_id, L, Id), use the tools in this order:

1. **Convert sizing → params**:
   Call `convert_sizing` with `topology='twostage'`, passing each role's `gm_id_target`, `L_guidance_um`, and `id_derived`, plus `Ib_a` and `Cc_f`.
   The tool returns a `params` dict and `config_path`.

2. **Simulate**:
   Call `simulate` with the `params` and `config_path` from step 1.
   Returns `specs` (A0, GBW, PM, power) and `transistors` (per-device OP data).

3. **Evaluate**: Compare SPICE specs against targets. Check all transistors are in saturation. For two-stage, also check p2 placement and PM.

### Default Spec List

The simulator returns: `dcgain_`, `gain_bandwidth_product_`, `phase_margin`, `power`, `vos25`.

### Additional Params

- `ibias`: bias current (A) — automatically set by `convert_sizing`
- `C1_value`: compensation capacitor (F) — automatically set from `Cc_f`
- `Rc_value`: nulling resistor (Ω) — automatically set from `Rc_ohm`
- WL_ratio range: nfet [2.8, 10.0], pfet [3.7, 10.0] — the tool handles finger splitting
