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
I_tail = ID3 = (M3_M / M4_M) × I_bias
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

**1c. Determine L from gain requirement (with GBW/ft guard):**

Sweep available L values in the LUT. For each L, query:
```
gm_gds_M1 = lut_query('nfet', 'gm_gds', L, gm_id_val=(gm/ID)_1)
ft_M1     = lut_query('nfet', 'ft',     L, gm_id_val=(gm/ID)_1)
```
Pick the shortest L where **both** conditions hold:
1. `gm_gds_M1 / 1.5 ≥ A0_target` (linear, not dB)  (gain requirement)
2. `GBW_target / ft_M1 < 0.4`  (analytical PM validity — see `lut-parameter-derivation.md`)

If a candidate L meets the gain requirement but violates GBW/ft < 0.4,
**reject it** and continue to a shorter L.

If no L satisfies both:
→ Print: "INFEASIBLE: 5T OTA cannot achieve required gain while
   maintaining GBW/ft < 0.4."
→ Ask user to relax gain or switch topology. Do NOT proceed.

**1d. Derive all DIFF_PAIR parameters from LUT:**

```
ID1    = gm1 / (gm/ID)_1
I_tail = 2 × ID1
```

> Derive all parameters for **M1** (nfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='nfet', gm_id=(gm/ID)_1, L=L1, ID=ID1
>
> This produces: gm1, W1, gds1, ft1, Cgs1, Cgd1, Cdb1, vdsat1.

### Step 2 — Initial sizing: LOAD (M5, M6)

ID5 = ID1 (already known from Step 1).

**2a. Choose gm/ID for LOAD:**

Use 10–14 S/A (moderate inversion).

**2b. Determine L from gain requirement:**

The gain is `A0 = gm1 / (gds1 + gds_eq_LOAD)`, where `gds_eq_LOAD`
depends on the LOAD sub-block type (from circuit-understanding Step 2b;
see `general/knowledge/mirror-load-structures.md`).

**Single load:** Sweep L5 to find minimum L where gain meets target:
```
For each L5:
  gds5 = (gm/ID)_5 × ID5 / lut_query('pfet', 'gm_gds', L5, gm_id_val=(gm/ID)_5)
  A0 = gm1 / (gds1 + gds5)
  If A0 ≥ A0_target: select this L5, BREAK
```
If no L5 satisfies the gain: increase L1 (from Step 1c) and re-derive.

**Cascode / LV-cascode load:** The cascode device boosts load impedance,
so `gds_eq_LOAD << gds1` and gain is dominated by the diff pair side
(`A0 ≈ gm1/gds1`). Use `L5 = L_min` (shortest available) as a starting
point; actual gain is verified after sizing the cascode in Step 2d.

**2c. Derive all LOAD (main) parameters from LUT:**

> Derive all parameters for **M5** (pfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='pfet', gm_id=(gm/ID)_5, L=L5, ID=ID5
>
> This produces: gm5, W5, gds5, ft5, Cgs5, Cgd5, Cdb5, vdsat5.

**2d. If LOAD sub_block_type != "single" — Size LOAD_CAS:**

Skip this step for single-transistor loads. For cascode and lv_cascode:

The cascode device carries the same current as M5 (in series), so
`ID_cas = ID5`. Free parameters: `gm/ID_cas` and `L_cas`.

**Parameter choices:**
- `(gm/ID)_cas = 10` S/A (strong-to-moderate — high gm_cas for fast p_int)
- `L_cas = L_min` (shortest available — keeps C_int small)

**Derive all LOAD_CAS parameters from LUT:**

> Derive all parameters for **LOAD_CAS** (pfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='pfet', gm_id=(gm/ID)_cas, L=L_cas, ID=ID5
>
> This produces: gm_cas, W_cas, gds_cas, Cgs_cas, Cgd_cas, Cdb_cas, vdsat_cas.
> Also query: `vth_cas = abs(lut_query('pfet', 'vth', L_cas, ...))`

**Compute sub-block effective quantities:**
```
gds_eq_LOAD = (gds5 × gds_cas) / gm_cas
C_eq_LOAD   = Cgd_cas + Cdb_cas                     # at vout
C_int_LOAD  = Cgs_cas + Cdb5 + Cgd5                  # at internal node
p_int_LOAD  = gm_cas / C_int_LOAD                   # rad/s
```

**Verify internal pole vs GBW**:
```
ω_c = 2π × GBW_target
If p_int_LOAD < 3 × ω_c:
  → Reduce L_cas (already at L_min? — then increase (gm/ID)_cas)
  → Or re-derive with stronger inversion (gm/ID = 8)
```

**For lv_cascode — compute required external bias:**
```
# PMOS LV cascode (rail = VDD):
Vbias_cas_p = VDD - (vdsat5 + vdsat_cas + |vth_cas|)

# NMOS LV cascode (rail = VSS):
Vbias_cas_n = vdsat_main + vdsat_cas + vth_cas
```
Record this value — it will be passed to the testbench as the value of
the `Vbias_cas_p` (or `_n`) port at simulation time.

**2e. Refine the first-stage gain with actual cascode values:**

Recompute with the exact LOAD sub-block:
```
A0 = gm1 / (gds1 + gds_eq_LOAD)
```
If `A0 < A0_target`: the design needs more gain. Options:
- Increase L5 (main device longer → smaller gds5 → smaller gds_eq_LOAD)
- Increase L_cas (longer cascode → larger gm_gds_cas → smaller gds_eq_LOAD)
  but verify `p_int_LOAD > 3 × ω_c` still holds.

### Step 3 — Initial sizing: TAIL (M3) and BIAS_GEN (M4)

ID3 = I_tail (already known from Step 1).

**3a. Determine multiplier ratio first:**

M4 (BIAS_GEN) is the unit cell with M4_M = 1. M3 (TAIL) uses multiple
parallel instances (multiplier M) to set the current ratio:

```
M4_M = 1
M3_M = round(I_tail / I_bias)
```

**3b. Choose gm/ID and L:**

Use (gm/ID)_3 = 10–14 S/A. Initial L3 = 1.0 µm (snap to the nearest value in
`list_available_L('nfet', corner, temp)`).

**3c. Derive unit-cell (single-instance) parameters from LUT:**

> Derive per-instance parameters for **M3** (nfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='nfet', gm_id=(gm/ID)_3, L=L3, ID=I_bias (per-instance current)
>
> This produces: gm_inst, W3, gds_inst, ft3, Cgs_inst, Cgd_inst, Cdb_inst, vdsat3.

**3d. Scale to total M3 (TAIL) device:**

Scale total quantities by multiplier M3_M (see `lut-parameter-derivation.md`
mirror scaling section):
```
gm3 = gm_inst × M3_M,  gds3 = gds_inst × M3_M,  (same for Cgs3, Cgd3, Cdb3)
```

**3e. BIAS_GEN (M4):**

M4 is the unit cell itself: `L4 = L3, W4 = W3, M4_M = 1`.

**3f. If TAIL sub_block_type != "single" — Size TAIL_CAS:**

Skip this step for single tail. For cascode / lv_cascode tail
(role `TAIL_CAS`, detected in circuit-understanding Step 2b):

The cascode device carries the full tail current (in series with M3),
so `ID_tcas = I_tail`. Parameter choices:
- `(gm/ID)_tcas = 10` S/A (strong-to-moderate — high gm_tcas)
- `L_tcas = L_min` (shortest available)

**Derive all TAIL_CAS parameters from LUT:**

> Derive all parameters for **TAIL_CAS** (nfet) using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='nfet', gm_id=(gm/ID)_tcas, L=L_tcas, ID=I_tail
>
> This produces: gm_tcas, W_tcas, gds_tcas, Cgs_tcas, Cgd_tcas, Cdb_tcas, vdsat_tcas.
> Also query: `vth_tcas = abs(lut_query('nfet', 'vth', L_tcas, ...))`

**Compute sub-block effective quantities:**
```
gds_eq_TAIL    = (gds3 × gds_tcas) / gm_tcas
V_headroom_TAIL = vdsat3 + vdsat_tcas
```

**For lv_cascode — compute required external bias (NMOS, rail = VSS):**
```
Vbias_cas_n = vdsat3 + vdsat_tcas + vth_tcas
```
Record this value — it will be passed to the testbench as the value of
the `Vbias_cas_n` port at simulation time (emitted as an `extra_ports`
entry when the topology is registered).

### Step 4 — Analytical spec evaluation

All devices are now sized with LUT data. Compute every spec using the
full equations from `5t-ota-equation.md`. **All calculations MUST be
done using Python** — do not compute mentally.

Note: since M1≡M2, `gm2=gm1, gds2=gds1, Cgd2=Cgd1, Cdb2=Cdb1`.
Since M5≡M6, `gm6=gm5, gds6=gds5, Cgs6=Cgs5, Cdb6=Cdb5`.
I_bias is from the spec form.

First, compute sub-block effective quantities for LOAD and TAIL.

> **Read `general/knowledge/mirror-load-structures.md`** and apply the
> formulas from Section B (single), C (cascode), or D (lv_cascode) based
> on the detected `sub_block_type` for each role. Compute these quantities
> for **both** LOAD and TAIL:
> - `gds_eq` — effective output conductance
> - `C_int` and `p_int` — internal cap and pole (None for single)
> - `V_headroom` — minimum voltage from rail to output
>
> Store the results as `gds_eq_LOAD`, `p_int_LOAD`, `V_headroom_LOAD` and
> `gds_eq_TAIL`, `V_headroom_TAIL` for use in the spec equations below.

Then compute node capacitances and all specs (see `5t-ota-equation.md`
and `5tota-transfer-function.md` for derivation).

**All Cgd values below MUST include extrinsic overlap** from
`extrinsic_caps()`. Cdb uses the LUT value directly.
See `lut-parameter-derivation.md` Extrinsic Capacitance Correction section.

```
# Node capacitances (single load — see equation file for cascode variants)
C1     = CL + Cdb1 + Cdb5 + Cgd1 + Cgd5             # total cap at vout
C2     = Cdb2 + Cdb6 + Cgs5 + Cgs6 + Cgd2 + Cgd5    # total cap at net1
C_mir  = Cdb2 + Cdb6 + Cgs5 + Cgs6 + Cgd2            # = C2 − Cgd5
G1     = gds1 + gds_eq_LOAD                           # output conductance
G2     = gds2 + gm6 + gds6                            # mirror node conductance

# DC gain
A0    = gm1 / G1

# Poles and zeros
fp1   = G1 / (2π × C1)                                # dominant pole
fp2   = G2 / (2π × C2)                                # mirror pole
fz_mirror = (gm5 + gm6) / (2π × C_mir)                # LHP mirror zero (≈ 2×fp2)
fz_rhp    = gm1 / (2π × Cgd1)                         # RHP zero from Cgd1 feedforward

# GBW and phase margin
GBW   = gm1 / (2π × C1)
PM    = 90° − arctan(GBW/fp2) + arctan(GBW/fz_mirror) − arctan(GBW/fz_rhp)
# Add cascode internal pole penalty if present:
if p_int_LOAD is not None:
    PM -= arctan(2π·GBW / p_int_LOAD)

# Other specs
SR    = I_tail / (CL + Cdb1 + Cdb5 + Cgd5)                # include output parasitics
# Swing uses V_headroom_LOAD (see mirror-load-structures.md):
#   single:      V_headroom_LOAD = vdsat_M5
#   cascode:     V_headroom_LOAD = Vgs_main + vdsat_cas
#   lv_cascode:  V_headroom_LOAD = vdsat_main + vdsat_cas
Swing = VDD - vdsat1 - V_headroom_TAIL - V_headroom_LOAD
Rout  = 1/G1
ro_eq_TAIL = 1/gds_eq_TAIL
CMRR  = 2·gm1·gm5·Rout·ro_eq_TAIL
PSRR⁺ ≈ A0
PSRR⁻ ≈ CMRR
P     = (I_tail + I_bias) × VDD
```

**GBW/ft validity check (MANDATORY before printing results):**

After computing GBW, verify that GBW/ft < 0.4 for every signal-path
device. This guards against unreliable analytical PM predictions.

```
GBW/ft CHECK
=============
Device | ft (MHz) | GBW/ft | Status
M1     | <>       | <>     | ✅ / ❌ REJECT (≥ 0.4)
M5     | <>       | <>     | ✅ / ❌ REJECT (≥ 0.4)

If any device has GBW/ft ≥ 0.4:
  → Reduce L for that device (shorter L → higher ft)
  → Re-derive LUT parameters for the affected role
  → Repeat Step 4
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
- All specs met AND all GBW/ft < 0.4 → proceed to Step 5 (simulation).
- Any GBW/ft ≥ 0.4 → reduce L for violating device, re-derive, repeat Step 4.
- Any spec failed → invoke `5t-ota-root-cause-diagnosis.md` to identify
  which device parameter to adjust. Apply the fix, re-derive LUT values
  for the affected role, and repeat Step 4.
- After 5 analytical iterations, proceed to Step 5 regardless.

### Step 5 — Submit to simulation

Call `convert_sizing` and `simulate_circuit`:

**⚠️ `id_derived` MUST be the TOTAL current the role carries, not per-instance.**
Step 3 works with per-instance parameters for LUT queries, but `convert_sizing`
needs the total current to compute mirror ratios.  Specifically:
- `TAIL.id_derived = I_tail` (total tail current, e.g. 40 µA), **NOT** `I_bias`
- `BIAS_GEN.id_derived = I_bias` (reference current, e.g. 5 µA)
The bridge computes `M3_M = round(I_tail / I_bias)` from the ratio.
Passing `I_bias` for both produces `M3_M = 1` → 5× current deficit.

```python
from tools import convert_sizing, simulate_circuit

result = convert_sizing(
    topology=topology_name,   # from ensure_topology_registered() in Stage [2]
    roles_raw={
        "DIFF_PAIR": {"gm_id_target": (gm/ID)_1, "L_guidance_um": L1, "id_derived": ID1},
        "LOAD":      {"gm_id_target": (gm/ID)_5, "L_guidance_um": L5, "id_derived": ID5},
        "TAIL":      {"gm_id_target": (gm/ID)_3, "L_guidance_um": L3, "id_derived": ID3},  # ID3 = I_tail, NOT I_bias
        "BIAS_GEN":  {"gm_id_target": 0,          "L_guidance_um": L3, "id_derived": I_bias},
        # Cascode companions (only if sub_block_type != "single" for the parent role):
        # "LOAD_CAS":  {"gm_id_target": (gm/ID)_cas, "L_guidance_um": L_cas, "id_derived": ID5},
        # "TAIL_CAS":  {"gm_id_target": (gm/ID)_tcas, "L_guidance_um": L_tcas, "id_derived": I_tail},
    },
    Ib_a=I_bias,
    l_overrides={"DIFF_PAIR": L1, "LOAD": L5, "TAIL": L3, "BIAS_GEN": L3},
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
    #     "Vbias_cas_p": VDD - (vdsat5 + vdsat_cas + abs(vth_cas)),       # PMOS load lv_cascode
    #     "Vbias_cas_n": vdsat3 + vdsat_tcas + abs(vth_tcas),             # NMOS tail lv_cascode
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

**Vbias_cas_p / Vbias_cas_n update rule:** these values depend on the sized
`vdsat` and `vth` of the cascode stack. Every sizing iteration must
recompute them from the LUT-derived `vdsatX` / `vth_cas` of the current
sizing and pass them as `extra_ports={...}` to `simulate_circuit`. Do NOT
rely on the TOML defaults written at `ensure_topology_registered` time —
those are only initial seed values; the live value comes from this call.

→ Proceed to `general/flow/simulation-verification.md` with the results.

