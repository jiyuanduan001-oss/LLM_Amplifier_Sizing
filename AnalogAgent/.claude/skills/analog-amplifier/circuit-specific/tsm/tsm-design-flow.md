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

## Canonical Device Numbering

The equations below use canonical device numbers as shorthand for roles.
The actual device names come from the user's netlist and are mapped to
roles during circuit-understanding (Stage [2]).

| Role | Canonical Device | Type | Equation variables |
|------|-----------------|------|--------------------|
| DIFF_PAIR | M3, M4 (matched) | nfet | gm3, gds3, Cgs3, Cgd3... |
| LOAD | M1, M2 (matched) | pfet | gm1, gds1, Cgs1, Cgd1... |
| BIAS_GEN | M5 | nfet | gm5, gds5... |
| TAIL | M6 (mirrors M5) | nfet | gm6, gds6... |
| OUTPUT_CS | M7 | pfet | gm7, gds7, Cgs7, Cgd7... |
| OUTPUT_BIAS | M8 (mirrors M5) | nfet | gm8, gds8... |

Mirror constraints: M5/M6/M8 share per-instance W/L; current ratio set by multiplier M.

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

**1d. Determine L from gain requirement (with GBW/ft guard):**

Sweep available L values in the LUT. For each L, query:
```
gm_gds_M3 = lut_query('nfet', 'gm_gds', L, gm_id_val=(gm/ID)_3)
ft_M3     = lut_query('nfet', 'ft',     L, gm_id_val=(gm/ID)_3)
```
Pick the shortest L where **both** conditions hold:
1. `gm_gds_M3 / 1.5 ≥ sqrt(A0_target_linear)`  (gain requirement)
2. `GBW_target / ft_M3 < 0.4`  (analytical PM validity — see `lut-parameter-derivation.md`)

If a candidate L meets the gain requirement but violates GBW/ft < 0.4,
**reject it** and continue to a shorter L. The analytical PM model is
unreliable above this threshold.

This distributes gain roughly equally between the two stages (in dB).
If no L satisfies both, pick L with the highest gm_gds that also keeps
GBW/ft < 0.4; the second stage provides additional gain. Total gain is
verified in Step 6.

**1e. Derive all DIFF_PAIR parameters from LUT:**

```
ID3    = gm3 / (gm/ID)_3
I_tail = 2 × ID3
```

> Derive all parameters for **M3** (nfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='nfet', gm_id=(gm/ID)_3, L=L3, ID=ID3
>
> This produces: gm3, W3, gds3, ft3, Cgs3, Cgd3, Cdb3, vdsat3.

### Step 2 — Initial sizing: LOAD (M1, M2)

ID1 = ID3 (already known from Step 1).

**2a. Choose gm/ID for LOAD:**

Use 10–14 S/A (moderate inversion).
Higher gm1 → higher mirror pole p3 → better PM. Do NOT push LOAD into
weak inversion (degrades p3).

**2b. Determine L from gain requirement:**

The first-stage gain is `A_v1 = gm3 / (gds3 + gds_eq_LOAD)`, where
`gds_eq_LOAD` depends on the LOAD sub-block type (from
circuit-understanding Step 2b; see `general/knowledge/mirror-load-structures.md`).

**Single load:** Sweep L1 to find minimum L where first-stage gain meets target:
```
For each L1:
  gds1 = (gm/ID)_1 × ID1 / lut_query('pfet', 'gm_gds', L1, gm_id_val=(gm/ID)_1)
  A_v1 = gm3 / (gds3 + gds1)
  If A_v1 ≥ sqrt(A0_target_linear): select this L1, BREAK
```
If no L1 satisfies this: increase L3 (from Step 1d) and re-derive.

**Cascode / LV-cascode load:** The cascode device boosts load impedance,
so `gds_eq_LOAD << gds3` and first-stage gain is dominated by the diff
pair (`A_v1 ≈ gm3/gds3`). Use `L1 = L_min` (shortest available) as a
starting point; actual gain is verified after sizing the cascode in
Step 2d.

**2c. Derive all LOAD (main) parameters from LUT:**

> Derive all parameters for **M1** (pfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='pfet', gm_id=(gm/ID)_1, L=L1, ID=ID1
>
> This produces: gm1, W1, gds1, ft1, Cgs1, Cgd1, Cdb1, vdsat1.

**2d. If LOAD sub_block_type != "single" — Size LOAD_CAS:**

Skip this step for single-transistor loads. For cascode and lv_cascode:

ID_loadcas = ID1 (in series with main). Choose:
- `(gm/ID)_loadcas = 10` S/A
- `L_loadcas = L_min` (shortest for speed)

Derive all LOAD_CAS parameters from LUT:
```
ID_lcas = ID1
gm_lcas = (gm/ID)_loadcas × ID_lcas
id_w_c  = lut_query('pfet', 'id_w',  L_loadcas, gm_id_val=(gm/ID)_loadcas)
W_lcas  = ID_lcas / id_w_c
gds_lcas = gm_lcas / lut_query('pfet', 'gm_gds', L_loadcas, gm_id_val=(gm/ID)_loadcas)
Cgs_lcas = lut_query('pfet', 'cgs_w', L_loadcas, gm_id_val=(gm/ID)_loadcas) × W_lcas
Cgd_lcas = lut_query('pfet', 'cgd_w', L_loadcas, gm_id_val=(gm/ID)_loadcas) × W_lcas
Cdb_lcas = lut_query('pfet', 'cdb_w', L_loadcas, gm_id_val=(gm/ID)_loadcas) × W_lcas  # F (real cdb)
vdsat_lcas = lut_query('pfet', 'vdsat', L_loadcas, gm_id_val=(gm/ID)_loadcas)  # V (BSIM4 |Vds|_sat)
vth_lcas   = abs(lut_query('pfet', 'vth', L_loadcas, gm_id_val=(gm/ID)_loadcas))
```

Compute sub-block effective quantities:
```
gds_eq_LOAD = (gds1 × gds_lcas) / gm_lcas
C_eq_LOAD   = Cgd_lcas + Cdb_lcas
C_int_LOAD  = Cgs_lcas + Cdb1 + Cgd1
p_int_LOAD  = gm_lcas / C_int_LOAD
```

For lv_cascode, compute external bias:
```
Vbias_cas_p = VDD - (vdsat1 + vdsat_lcas + |vth_lcas|)
```

Recompute A_v1 with actual gds_eq_LOAD; if still low, increase L1.

### Step 3 — Initial sizing: OUTPUT_CS (M7)

The second stage must provide sufficient gm7 for phase margin (output pole
p2 must be far above the unity-gain frequency).

**3a. Determine gm7 from PM constraint:**

Using a single non-dominant pole estimate, derive the required p2 from
the user's PM target:
```
ω_c = gm3 / Cc_initial
p2_required = ω_c / tan(90° - PM_target)       # e.g. PM=60° → 1.73×ω_c, PM=72° → 3.08×ω_c
gm7_required ≥ p2_required × CL                # using p2 ≈ gm7/CL
```
This is a first estimate; actual PM is validated through simulation.

Also check slew rate constraint on second-stage current.
SR- = min(I_tail/Cc, ID7/CTL), so to meet SR-_target from
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

> Derive all parameters for **M7** (pfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='pfet', gm_id=(gm/ID)_7, L=L7, ID=ID7
>
> This produces: gm7, W7, gds7, ft7, Cgs7, Cgd7, Cdb7, vdsat7.

### Step 4 — Initial sizing: BIAS_GEN (M5), TAIL (M6), OUTPUT_BIAS (M8)

M5 is the diode-connected reference. M6 and M8 mirror M5.

**4a. Choose gm/ID and L for bias mirrors:**

Use (gm/ID)_5 = 10–14 S/A. Initial L5 = 1.0 µm (snap to the nearest value in
`list_available_L('nfet', corner, temp)`).

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

**4c. Derive unit-cell (single-instance) parameters from LUT:**

> Derive per-instance parameters for **M5** (nfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='nfet', gm_id=(gm/ID)_5, L=L5, ID=I_bias (per-instance current)
>
> This produces: gm_inst, W5, gds_inst, ft5, Cgs_inst, Cgd_inst, Cdb_inst, vdsat5.

**4d. Scale to total M6 (TAIL) and M8 (OUTPUT_BIAS):**

M5, M6, M8 share the same per-instance W and L. Scale total quantities
by each device's multiplier M (see `lut-parameter-derivation.md`
mirror scaling section):
```
M6: gm6 = gm_inst × M6_M,  gds6 = gds_inst × M6_M,  (same for Cgs6, Cgd6, Cdb6)
M8: gm8 = gm_inst × M8_M,  gds8 = gds_inst × M8_M,  (same for Cgs8, Cgd8, Cdb8)
    L8 = L5,  W8 = W5,  M8_M = round(ID7 / I_bias)
```

M5 is the unit cell itself:
```
L5 = L5,  W5 = W5,  M5_M = 1
```

**4f. If LOAD sub_block_type != "single" — Size LOAD_CAS:**
(Already covered in Step 2d above — this is a cross-reference reminder.)

**4g. If OUTPUT_BIAS sub_block_type != "single" — Size OUTPUT_BIAS_CAS:**

Skip for single OUTPUT_BIAS. For cascode / lv_cascode on M8:

ID_obcas = ID7 (in series with M8). Choose:
- `(gm/ID)_obcas = 10` S/A
- `L_obcas = L_min`

Derive LUT parameters for OUTPUT_BIAS_CAS (NMOS, same as M8):
```
gm_obcas  = (gm/ID)_obcas × ID7
id_w_c    = lut_query('nfet', 'id_w', L_obcas, gm_id_val=(gm/ID)_obcas)
W_obcas   = ID7 / id_w_c
gds_obcas = gm_obcas / lut_query('nfet', 'gm_gds', L_obcas, gm_id_val=(gm/ID)_obcas)
Cgs_obcas = lut_query('nfet', 'cgs_w', L_obcas, gm_id_val=(gm/ID)_obcas) × W_obcas
Cgd_obcas = lut_query('nfet', 'cgd_w', L_obcas, gm_id_val=(gm/ID)_obcas) × W_obcas
Cdb_obcas = lut_query('nfet', 'cdb_w', L_obcas, gm_id_val=(gm/ID)_obcas) × W_obcas  # F
vdsat_obcas = lut_query('nfet', 'vdsat', L_obcas, gm_id_val=(gm/ID)_obcas)  # V (BSIM4 |Vds|_sat)
vth_obcas   = abs(lut_query('nfet', 'vth', L_obcas, gm_id_val=(gm/ID)_obcas))
```

Compute sub-block quantities:
```
gds_eq_OBIAS = (gds8 × gds_obcas) / gm_obcas
C_eq_OBIAS   = Cgd_obcas + Cdb_obcas
C_int_OBIAS  = Cgs_obcas + Cdb8 + Cgd8
p_int_OBIAS  = gm_obcas / C_int_OBIAS
```

For lv_cascode (NMOS, rail = VSS):
```
Vbias_cas_n = vdsat8 + vdsat_obcas + vth_obcas
```

**4h. If TAIL sub_block_type != "single" — Size TAIL_CAS:**

Skip for single tail. For cascode / lv_cascode TAIL (role `TAIL_CAS`,
detected in circuit-understanding Step 2b):

ID_tcas = I_tail (in series with M6). Choose:
- `(gm/ID)_tcas = 10` S/A
- `L_tcas = L_min`

Derive LUT parameters for TAIL_CAS (NMOS):
```
gm_tcas  = (gm/ID)_tcas × I_tail
id_w_t   = lut_query('nfet', 'id_w', L_tcas, gm_id_val=(gm/ID)_tcas)
W_tcas   = I_tail / id_w_t
gds_tcas = gm_tcas / lut_query('nfet', 'gm_gds', L_tcas, gm_id_val=(gm/ID)_tcas)
Cgs_tcas = lut_query('nfet', 'cgs_w', L_tcas, gm_id_val=(gm/ID)_tcas) × W_tcas
Cgd_tcas = lut_query('nfet', 'cgd_w', L_tcas, gm_id_val=(gm/ID)_tcas) × W_tcas
Cdb_tcas = lut_query('nfet', 'cdb_w', L_tcas, gm_id_val=(gm/ID)_tcas) × W_tcas
vdsat_tcas = lut_query('nfet', 'vdsat', L_tcas, gm_id_val=(gm/ID)_tcas)
vth_tcas   = abs(lut_query('nfet', 'vth',  L_tcas, gm_id_val=(gm/ID)_tcas))
```

Compute sub-block quantities:
```
gds_eq_TAIL     = (gds6 × gds_tcas) / gm_tcas
V_headroom_TAIL = vdsat6 + vdsat_tcas
```

For lv_cascode (NMOS, rail = VSS):
```
Vbias_cas_n_tail = vdsat6 + vdsat_tcas + vth_tcas
```

Record `Vbias_cas_n_tail` — it will be passed to the testbench as the
value of the `Vbias_cas_n` port at simulation time (emitted as an
`extra_ports` entry when the topology is registered).

### Step 5 — Compensation: Cc and Rc

**5a. Refine Cc from GBW constraint:**
```
Cc = gm3 / (2π × GBW)
```

Compute node capacitances and derive exact poles via KCL cubic.
**All Cgd and Cdb values MUST include extrinsic components** from
`extrinsic_caps()` — see `lut-parameter-derivation.md`:
```
from scripts.lut_lookup import extrinsic_caps
# For each device, after deriving LUT intrinsic Cgd/Cdb:
#   ex = extrinsic_caps(dev_type, W_meters, M=multiplier)
#   Cgd_total = Cgd_intrinsic + ex['cgd_ov']
#   Cdb_total = Cdb_intrinsic + ex['cdb_sw']

C1     = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4           (cap at net5, excluding Cgd7)
CTL    = CL + Cdb7 + Cdb8 + Cgd8                     (cap at vout, excluding Cgd7)
C2     = Cgs1 + Cgs2 + Cdb1 + Cdb3 + Cgd2 + Cgd3   (cap at net1)
G_net1 = gm1 + gds1 + gds3
p3     = G_net1 / C2                                 (mirror pole — separate node, accurate)
fz_mirror = 2 × p3 / (2π)                            (LHP mirror zero)
```

**5b. Exact poles via KCL cubic (see `tsm-equation.md` for derivation):**
```python
import numpy as np
Go   = gds7 + gds_eq_OBIAS
G1   = gds_eq_LOAD + gds3          # gds2≡gds_LOAD, gds4≡gds3
tau  = Rc_approx * Cc               # use approximate Rc for initial cubic
Ccomp = Cc + Cgd7;  Gt = gm7 + Go + G1;  Ct = CTL + C1

d0 = Go * G1
d1 = Go*C1 + G1*CTL + Go*G1*tau + Ccomp*Gt
d2 = C1*CTL + (Go*C1 + G1*CTL)*tau + Ccomp*Ct + tau*Cgd7*Gt
d3 = C1*CTL*tau + tau*Cgd7*Ct

poles = sorted(np.roots([d3, d2, d1, d0]), key=lambda x: abs(x))
p1_kcl, p2_kcl, p4_kcl = [abs(p) for p in poles]   # rad/s
```

**5c. Nulling resistor Rc (LHP zero cancels KCL-derived p2):**
```
Rc = 1/gm7 + 1/(p2_kcl × Cc)
```
Then recompute the cubic with the updated Rc (one iteration is sufficient).

**5d. Verify PM:**
```
z_Rc   = 1 / (Cc × (Rc - 1/gm7))
fz_rhp = gm3 / (2π × Cgd3)
PM_est = 90° − arctan(ω_c/p2_kcl) + arctan(ω_c/z_Rc)
         − arctan(ω_c/p3) − arctan(ω_c/p4_kcl)
         + arctan(ω_c/(fz_mirror×2π)) − arctan(ω_c/(fz_rhp×2π))
If PM_est < PM_target + 5°: increase Cc (trades GBW for PM)
```

### Step 6 — Analytical spec evaluation

All devices are now sized with LUT data. Compute every spec using the
full equations from `tsm-equation.md`. **All calculations MUST be
done using Python** — do not compute mentally.

Note: since M3≡M4, `gm4=gm3, gds4=gds3, Cgd4=Cgd3`.
Since M1≡M2, `gm2=gm1, gds2=gds1, Cgs2=Cgs1`.
I_bias is from the spec form.

First, compute sub-block effective quantities for LOAD and OUTPUT_BIAS.

> **Read `general/knowledge/mirror-load-structures.md`** and apply the
> formulas from Section B (single), C (cascode), or D (lv_cascode) based
> on the detected `sub_block_type` for each role. Compute these five
> quantities for **LOAD**, **OUTPUT_BIAS**, and **TAIL**:
> - `gds_eq` — effective output conductance
> - `C_eq` — capacitance at output node
> - `p_int` — internal pole (None for single)
> - `V_headroom` — minimum voltage from rail to output
> - `Vbias_ext` — external bias voltage (None unless lv_cascode)
>
> Store the results as:
> - `gds_eq_LOAD`, `p_int_LOAD`, `V_headroom_LOAD`
> - `gds_eq_OBIAS`, `p_int_OBIAS`, `V_headroom_OBIAS`
> - `gds_eq_TAIL`, `p_int_TAIL`, `V_headroom_TAIL`

Then compute node capacitances and all specs (see `tsm-equation.md`
and `tsm-transfer-function.md` for derivation).

**All Cgd and Cdb values below MUST include extrinsic components** from
`extrinsic_caps()`. Call `extrinsic_caps(dev_type, W, M=M)` for each
device and add `cgd_ov` to Cgd, `cdb_sw` to Cdb (see
`lut-parameter-derivation.md`).

```python
# DC gain
A_v1  = gm3 / (gds3 + gds_eq_LOAD)
A_v2  = gm7 / (gds7 + gds_eq_OBIAS)
A0    = A_v1 × A_v2

# Node capacitances (single load/output-bias — see tsm-equation.md for cascode variants)
# NOTE: Cgd and Cdb here are corrected totals (intrinsic + extrinsic)
# Cgd7 is excluded from C1 and CTL — it couples net5↔vout and is handled by the KCL cubic.
C1     = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4             (cap at net5, excl. Cgd7)
CTL    = CL + Cdb7 + Cdb8 + Cgd8                       (total output cap, excl. Cgd7)
C2     = Cgs1 + Cgs2 + Cdb1 + Cdb3 + Cgd2 + Cgd3     (cap at net1)
G_net1 = gm1 + gds1 + gds3                             (net1 conductance)

# GBW
GBW   = gm3 / (2π × Cc)
ω_c   = 2π × GBW

# KCL-derived exact poles for net5-vout coupled system (see tsm-equation.md)
Go    = gds7 + gds_eq_OBIAS
G1    = gds_eq_LOAD + gds3
Rc_approx = (1/gm7) × (Cc + C1) × (Cc + CTL) / Cc²   (initial estimate)
tau   = Rc_approx × Cc
Ccomp = Cc + Cgd7;  Gt = gm7 + Go + G1;  Ct = CTL + C1

d0 = Go × G1
d1 = Go×C1 + G1×CTL + Go×G1×tau + Ccomp×Gt
d2 = C1×CTL + (Go×C1 + G1×CTL)×tau + Ccomp×Ct + tau×Cgd7×Gt
d3 = C1×CTL×tau + tau×Cgd7×Ct

poles = sorted(numpy.roots([d3, d2, d1, d0]), key=lambda x: abs(x))
p1_kcl, p2_kcl, p4_kcl = [abs(p) for p in poles]     (rad/s)

# Recompute Rc to cancel the KCL-derived p2
Rc    = 1/gm7 + 1/(p2_kcl × Cc)

# Mirror pole (separate node — not part of the cubic)
p3    = G_net1 / C2                                     (mirror pole)

# Zeros
z_Rc      = 1 / (Cc × (Rc - 1/gm7))                   (LHP zero, ≈ p2_kcl)
fz_mirror = 2 × p3 / (2π)                              (LHP mirror zero)
fz_rhp    = gm3 / (2π × Cgd3)                          (RHP diff pair Cgd zero)

# Phase margin (using KCL-derived poles)
PM    = 90° − arctan(ω_c/p2_kcl) + arctan(ω_c/z_Rc)
        − arctan(ω_c/p3) − arctan(ω_c/p4_kcl)
        + arctan(ω_c/(fz_mirror×2π)) − arctan(ω_c/(fz_rhp×2π))
# Add cascode internal pole penalties if present:
if p_int_LOAD  is not None: PM -= degrees(arctan(ω_c / p_int_LOAD))
if p_int_OBIAS is not None: PM -= degrees(arctan(ω_c / p_int_OBIAS))
if p_int_TAIL  is not None: PM -= degrees(arctan(ω_c / p_int_TAIL))

# Slew rate (see tsm-equation.md for full derivation)
SR+   = I_tail / Cc                     # sustained (conservative)
# Note: with Rc > 0, SPICE SR+ will be higher (Rc delays Cc feedback)
CTL_eff = CTL + Cgd7 * A_v2             # M7 Cgd Miller effect
SR-   = min(I_tail / Cc, ID7 / CTL_eff)
Swing = VDD - vdsat7 - V_headroom_OBIAS
P     = VDD × (I_bias + I_tail + ID7)

# CMRR — uses effective gds of LOAD and TAIL:
CMRR  = 2·gm3·gm1 / [(gds3 + gds_eq_LOAD)·gds_eq_TAIL]

# PSRR⁻: uses effective gds of LOAD and OUTPUT_BIAS:
A_VSS_M8 = gds_eq_OBIAS / (gds7 + gds_eq_OBIAS)
A_VSS_M6 = gds6·gds_eq_LOAD·gm7 / [2·gm1·(gds3+gds_eq_LOAD)·(gds7+gds_eq_OBIAS)]
PSRR⁻    = A0 / (A_VSS_M8 + A_VSS_M6)

# PSRR⁺ (same structure; substitute gds_eq for single gds where applicable):
PSRR⁺    = A0 · (gds7 - gds_eq_OBIAS) / |gds7 - gm7·gds3/gm1|
```

**GBW/ft validity check (MANDATORY before printing results):**

After computing GBW, verify that GBW/ft < 0.4 for every signal-path
device. This guards against unreliable analytical PM predictions.

```
GBW/ft CHECK
=============
Device | ft (MHz) | GBW/ft | Status
M3     | <>       | <>     | ✅ / ❌ REJECT (≥ 0.4)
M1     | <>       | <>     | ✅ / ❌ REJECT (≥ 0.4)
M7     | <>       | <>     | ✅ / ❌ REJECT (≥ 0.4)

If any device has GBW/ft ≥ 0.4:
  → Reduce L for that device (shorter L → higher ft)
  → Re-derive LUT parameters for the affected role
  → Repeat Step 6
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
- All specs met AND all GBW/ft < 0.4 → proceed to Step 7 (simulation).
- Any GBW/ft ≥ 0.4 → reduce L for violating device, re-derive, repeat Step 6.
- Any spec failed → invoke `tsm-root-cause-diagnosis.md` to identify
  which device parameter to adjust. Apply the fix, re-derive LUT values
  for the affected role, and repeat Step 6.
- After 5 analytical iterations, proceed to Step 7 regardless.

### Step 7 — Submit to simulation

Call `convert_sizing` and `simulate_circuit`:

```python
from tools import convert_sizing, simulate_circuit

result = convert_sizing(
    topology=topology_name,   # from ensure_topology_registered() in Stage [2]
    roles_raw={
        "DIFF_PAIR":    {"gm_id_target": (gm/ID)_3, "L_guidance_um": L3, "id_derived": ID3},
        "LOAD":         {"gm_id_target": (gm/ID)_1, "L_guidance_um": L1, "id_derived": ID1},
        "OUTPUT_CS":    {"gm_id_target": (gm/ID)_7, "L_guidance_um": L7, "id_derived": ID7},
        "BIAS_GEN":     {"gm_id_target": (gm/ID)_5, "L_guidance_um": L5, "id_derived": I_bias},
        "TAIL":         {"gm_id_target": 0,          "L_guidance_um": L5, "id_derived": I_tail},      # gm_id=0 → mirror device (bridge uses mirror_of logic)
        "OUTPUT_BIAS":  {"gm_id_target": 0,          "L_guidance_um": L5, "id_derived": ID7},         # gm_id=0 → mirror device (bridge uses mirror_of logic)
        # Cascode companion roles (include only when detected):
        # "LOAD_CAS":        {"gm_id_target": (gm/ID)_loadcas, "L_guidance_um": L_loadcas, "id_derived": ID1},
        # "OUTPUT_BIAS_CAS": {"gm_id_target": (gm/ID)_obcas,   "L_guidance_um": L_obcas,   "id_derived": ID7},
        # "TAIL_CAS":        {"gm_id_target": (gm/ID)_tcas,    "L_guidance_um": L_tcas,    "id_derived": I_tail},
    },
    Ib_a=I_bias,
    Cc_f=Cc,
    Rc_ohm=Rc,
    l_overrides={"DIFF_PAIR": L3, "LOAD": L1, "OUTPUT_CS": L7,
                 "BIAS_GEN": L5, "TAIL": L5, "OUTPUT_BIAS": L5,
                 # Add L overrides for cascode companions when present:
                 # "LOAD_CAS": L_loadcas, "OUTPUT_BIAS_CAS": L_obcas,
                 # "TAIL_CAS": L_tcas,
                 },
)

sim = simulate_circuit(
    result["params"],
    config_path=result["config_path"],
    corner=corner,                       # from validated spec form
    temperature=temperature,             # from validated spec form
    supply_voltage=VDD,                  # from validated spec form
    CL=CL,                              # from validated spec form (Farads)
    # Mismatch is slow (~35 s of Monte Carlo). Honor the spec form:
    #   user's Mismatch field is BLANK → measure_mismatch=False
    #   user provided a numeric Mismatch target → measure_mismatch=True
    measure_mismatch=mismatch_enabled,   # bool from Stage [1] spec form
    # LV-cascode bias overrides — ONLY if any role has sub_block_type == "lv_cascode":
    # Uncomment and populate when lv_cascode is detected in circuit-understanding.
    # For single or regular cascode sub-blocks, omit extra_ports entirely.
    # extra_ports={
    #     "Vbias_cas_p": VDD - (vdsat1 + vdsat_lcas + abs(vth_lcas)),  # PMOS load lv_cascode
    #     "Vbias_cas_n_tail": vdsat6 + vdsat_tcas + abs(vth_tcas),     # NMOS tail lv_cascode
    #     "Vbias_cas_n": vdsat8 + vdsat_obcas + abs(vth_obcas),        # NMOS OUTPUT_BIAS lv_cascode
    # },
)
```

**IMPORTANT:** `corner`, `temperature`, `supply_voltage` (VDD), and `CL` MUST
come from the validated spec form (Stage [1]). These are the same values used
for LUT queries and analytical sizing. Omitting them causes the simulator to
fall back to TOML defaults (typically tt/27°C/1.8V/5pF), creating a mismatch
between the LUT-based sizing and the SPICE verification. The `CL` parameter
accepts **Farads** (SI); the bridge converts to picoFarads internally for
CircuitCollector.

**Vbias_cas_* update rule:** these values depend on the sized `vdsat` and
`vth` of the cascode stack and MUST be recomputed from the current
sizing every iteration, then passed via `extra_ports={...}` to
`simulate_circuit`. The TOML-baked defaults are only initial seed values;
they become stale as soon as sizing changes vdsat/vth.

→ Proceed to `general/flow/simulation-verification.md` with the results.

