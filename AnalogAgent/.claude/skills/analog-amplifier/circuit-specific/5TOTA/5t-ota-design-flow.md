# 5T OTA Design Flow

## Purpose

Step-by-step sizing procedure for the 5-transistor single-stage OTA.
Invoked after circuit-understanding identifies the topology as 5T OTA.

## References

- Equations: `5t-ota-equation.md`
- Root-cause diagnosis: `5t-ota-root-cause-diagnosis.md`

## Rules

1. Execute steps in order. Do not skip.
2. All computations in Python. No mental arithmetic.
3. After simulation failure, use `5t-ota-root-cause-diagnosis.md`. Do not improvise fixes.

---

## Bias Current Relationships

```
I_tail = ID3 = (M3_fingers / M4_fingers) × I_bias
ID1 = ID2 = I_tail / 2
ID5 = ID6 = ID1
P = (I_tail + I_bias) × VDD
```

---

## Sizing Procedure

### Step 1 — Initial sizing: DIFF_PAIR (M1, M2)

Goal: determine gm, gm/ID, L for the input pair, then derive all
device parameters from LUT.

**1a. Determine gm from GBW spec:**
```
gm1 = 2π × GBW × CL
```

**1b. Choose gm/ID (empirical, based on bandwidth):**

| GBW range   | Recommended gm/ID | Inversion      | Comment                    |
|-------------|-------------------|----------------|----------------------------|
| < 10 MHz    | 14–30 S/A         | Moderate–weak  | Lower power design         |
| 10–100 MHz  | 10–14 S/A         | Moderate       | Balanced across all aspects |
| > 100 MHz   | 5–10 S/A          | Strong         | High speed                 |

**1c. Determine L from gain requirement:**

Sweep available L values in the LUT. For each L, query:
```
gm_gds_M1 = lut_query('nfet', 'gm_gds', L, gm_id_val=(gm/ID)_1)
```
Pick the shortest L where `gm_gds_M1 / 2 ≥ A0_target` (linear, not dB).

If no L satisfies this:
→ Print: "INFEASIBLE: 5T OTA cannot achieve required gain."
→ Ask user to relax gain or switch topology. Do NOT proceed.

**1d. Derive all DIFF_PAIR parameters from LUT:**

With (gm1, L1, (gm/ID)_1) now fixed, derive all parameters from LUT:
```
ID1   = gm1 / (gm/ID)_1
I_tail = 2 × ID1
id_w1 = lut_query('nfet', 'id_w',  L1, gm_id_val=(gm/ID)_1)   # µA/µm
W1    = ID1 / id_w1                                              # µm
gds1  = gm1 / lut_query('nfet', 'gm_gds', L1, gm_id_val=(gm/ID)_1)
ft1   = lut_query('nfet', 'ft',    L1, gm_id_val=(gm/ID)_1)    # Hz
Cgs1  = lut_query('nfet', 'cgs_w', L1, gm_id_val=(gm/ID)_1) × W1 × 1e-6  # F
Cgd1  = lut_query('nfet', 'cgd_w', L1, gm_id_val=(gm/ID)_1) × W1 × 1e-6  # F
vov1  = lut_query('nfet', 'vov',   L1, gm_id_val=(gm/ID)_1)    # V
```

### Step 2 — Initial sizing: LOAD (M5, M6)

ID5 = ID1 (already known from Step 1).

**2a. Choose gm/ID for LOAD:**

Use 10–14 S/A (moderate inversion).

**2b. Determine L from gain requirement:**

Step 1c used the approximation `A0 ≈ (gm/gds)_M1 / 2`. Now with the LOAD,
compute the actual gain `A0 = gm1 / (gds1 + gds5)`. Sweep L5 candidates:

```
For each L5:
  gds5 = (gm/ID)_5 × ID5 / lut_query('pfet', 'gm_gds', L5, gm_id_val=(gm/ID)_5)
  A0   = gm1 / (gds1 + gds5)
  If A0 ≥ A0_target: select this L5, BREAK
```

If no L5 satisfies the gain: increase L1 (from Step 1c) and re-derive.

**2c. Derive all LOAD parameters from LUT:**

With (ID5, L5, (gm/ID)_5) now fixed:
```
gm5   = (gm/ID)_5 × ID5
id_w5 = lut_query('pfet', 'id_w',  L5, gm_id_val=(gm/ID)_5)   # µA/µm
W5    = ID5 / id_w5                                              # µm
gds5  = gm5 / lut_query('pfet', 'gm_gds', L5, gm_id_val=(gm/ID)_5)
ft5   = lut_query('pfet', 'ft',    L5, gm_id_val=(gm/ID)_5)    # Hz
Cgs5  = lut_query('pfet', 'cgs_w', L5, gm_id_val=(gm/ID)_5) × W5 × 1e-6  # F
Cgd5  = lut_query('pfet', 'cgd_w', L5, gm_id_val=(gm/ID)_5) × W5 × 1e-6  # F
vov5  = lut_query('pfet', 'vov',   L5, gm_id_val=(gm/ID)_5)    # V
```

### Step 3 — Initial sizing: TAIL (M3) and BIAS_REF (M4)

ID3 = I_tail (already known from Step 1).

**3a. Determine multiplier ratio first:**

M4 (BIAS_REF) is the unit cell with M4_M = 1. M3 (TAIL) uses multiple
parallel fingers to set the current ratio:

```
M4_M = 1
M3_M = round(I_tail / I_bias)
```

**3b. Choose gm/ID and L:**

Use (gm/ID)_3 = 10–14 S/A. Initial L3 = 1.08 µm.

**3c. Derive single-finger parameters from LUT:**

LUT describes a single transistor. Use the per-finger current
(I_bias = I_tail / M3_M) to derive the unit-cell parameters:

```
ID_finger = I_bias                                                # A per finger
gm_finger = (gm/ID)_3 × ID_finger
id_w3     = lut_query('nfet', 'id_w',  L3, gm_id_val=(gm/ID)_3) # µA/µm
W3        = ID_finger / id_w3                                     # µm (per finger)
gds_finger = gm_finger / lut_query('nfet', 'gm_gds', L3, gm_id_val=(gm/ID)_3)
ft3       = lut_query('nfet', 'ft',    L3, gm_id_val=(gm/ID)_3)  # Hz (same per finger)
Cgs_finger = lut_query('nfet', 'cgs_w', L3, gm_id_val=(gm/ID)_3) × W3 × 1e-6  # F
Cgd_finger = lut_query('nfet', 'cgd_w', L3, gm_id_val=(gm/ID)_3) × W3 × 1e-6  # F
vov3      = lut_query('nfet', 'vov',   L3, gm_id_val=(gm/ID)_3)  # V (same per finger)
```

**3d. Scale to total M3 device:**

```
gm3  = gm_finger × M3_M
gds3 = gds_finger × M3_M
Cgs3 = Cgs_finger × M3_M
Cgd3 = Cgd_finger × M3_M
```

**3e. BIAS_REF (M4):**

M4 shares the same W and L as M3 (single finger = unit cell):
```
L4 = L3
W4 = W3
```

### Step 4 — Analytical spec evaluation

All devices are now sized with LUT data. Compute every spec using the
full equations from `5t-ota-equation.md`. **All calculations MUST be
done using Python** — do not compute mentally.

Note: since M1≡M2, `gm2=gm1, gds2=gds1, Cgd2=Cgd1`.
Since M5≡M6, `gm6=gm5, gds6=gds5, Cgs6=Cgs5`.
I_bias is from the spec form.

```
A0    = gm1 / (gds1 + gds5)
GBW   = gm1 / (2π × (CL + Cgd1 + Cgd5))
fp2   = gm5 / (2π × (Cgs5 + Cgs5 + Cgd1))     # gm6=gm5, Cgs6=Cgs5, Cgd2=Cgd1
fz2   = 2 × fp2
PM    = 90° - arctan(GBW/fp2) + arctan(GBW/fz2)
SR    = I_tail / CL
Swing = VDD - vov1 - |vov5|
CMRR  = 2·gm1·gm5·Rout·ro3    (where Rout = 1/(gds1+gds5), ro3 = 1/gds3)
PSRR⁺ ≈ A0
PSRR⁻ ≈ CMRR
P     = (I_tail + I_bias) × VDD
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
- All specs met → proceed to Step 5 (simulation).
- Any spec failed → invoke `5t-ota-root-cause-diagnosis.md` to identify
  which device parameter to adjust. Apply the fix, re-derive LUT values
  for the affected role, and repeat Step 4.
- After 5 analytical iterations, proceed to Step 5 regardless.

### Step 5 — Submit to simulation

Call `convert_sizing` and `simulate_circuit`:

```python
from tools import convert_sizing, simulate_circuit

result = convert_sizing(
    topology='5t_ota',
    roles_raw={
        "DIFF_PAIR": {"gm_id_target": (gm/ID)_1, "L_guidance_um": L1, "id_derived": ID1},
        "LOAD":      {"gm_id_target": (gm/ID)_5, "L_guidance_um": L5, "id_derived": ID5},
        "TAIL":      {"gm_id_target": (gm/ID)_3, "L_guidance_um": L3, "id_derived": ID3},
        "BIAS_REF":  {"gm_id_target": 0,          "L_guidance_um": L3, "id_derived": I_bias},
    },
    Ib_a=I_bias,
    l_overrides={"DIFF_PAIR": L1, "LOAD": L5, "TAIL": L3, "BIAS_REF": L3},
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

