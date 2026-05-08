# Simulation & Verification Skill

## Purpose

After the circuit-specific design flow calls the simulator, this skill
verifies the results: check operating points, check spec compliance,
compare with analytical predictions, and decide next action.

The circuit-specific design flow is responsible for calling `convert_sizing()`
and `simulate_circuit()`. This skill takes the returned `specs` and
`transistors` as input.

---

## Step 1 — Check Operating Points

For EVERY transistor (skip entries with id=0, these are measurement probes):

```
OP TABLE — Iteration <N>
=========================
Device  | gm/id | gm/gds | id(µA) | vds(V)  | vdsat(V) | margin(V) | region
M1      | <>    | <>     | <>     | <>      | <>      | <>        | sat ✅ / linear ❌
...
```

Where:
- `vdsat` from BSIM4 OP (positive magnitude — minimum |VDS| for saturation)
- `margin = |vds| - vdsat` (positive = saturated)
- Flag ❌ if `margin < 0` or `region != saturation`
- Flag ⚠️ if `margin < 50mV`

Also check symmetry for matched pairs:
```
Symmetry: |gm_M1 - gm_M2| / gm_M1 = <>%  [pass if < 1%]
```

## Step 2 — Check Spec Compliance

Compare SPICE results against the **Active Targets** from the validated
spec form (Stage [1]). Only check specs that the user specified — inactive
specs are reported but not checked.

**Mismatch**: If the Mismatch spec was left blank in the spec form,
mismatch is **completely disabled** — do not include `vos_mismatch_3sigma`
in the pass/fail evaluation, do not report it, and do not diagnose it.
Mismatch simulation (Monte Carlo) is slow and should only run when the
user explicitly requested it with a numeric target value.

```
SPEC COMPLIANCE — Iteration <N>
================================
Spec          | Target      | Achieved    | Margin  | Status
DC gain       | > <> dB     | <> dB       | +<>%    | ✅/❌
GBW           | > <> MHz    | <> MHz      | +<>%    | ✅/❌
PM            | > <>°       | <>°         | +<>%    | ✅/❌
[active targets only]

Reported (no target):
  <spec> = <value>
  ...
```

If a spec returns `None` from the simulator but has a user target,
estimate it from OP data using the circuit-specific equation skill.
Mark as "estimated from OP" in the table.

## Step 3 — Compare with Analytical Predictions

Compare the sizing-stage analytical predictions against SPICE results:

```
ANALYTICAL vs SPICE — Iteration <N>
=====================================
Metric  | Analytical | SPICE    | Error
A0      | <> dB      | <> dB    | <>%
GBW     | <> MHz     | <> MHz   | <>%
PM      | <>°        | <>°      | <>°
[any other metrics predicted analytically]
```

## Step 3b — Post-Simulation Analytical Recalculation (MANDATORY)

After comparing LUT-based analytical predictions with SPICE in Step 3,
perform a **second analytical pass** using the SPICE operating-point
data as inputs. This eliminates LUT interpolation error, VDS-dependence
error, and W/L quantization error — isolating model-structure error
(unmodeled poles, NQS effects) as the only remaining discrepancy.

**Procedure:**

1. **Extract from SPICE OP** (the `transistors` dict returned by
   `simulate_circuit`): for every signal-path device, read `gm`, `gds`,
   and `cgs`, `cgd`, `cdb` (all from the simulator's BSIM4 OP output).
   Note: SPICE `cgd` and `cdb` are signed (negative by convention in
   ngspice); take `abs()`.

2. **Compute node capacitances** using extracted SPICE caps instead of
   LUT-derived caps. Use the same node-cap formulas from the circuit-
   specific equation file, but substitute SPICE values. For matched
   pairs (e.g. M1≡M2), the SPICE OP already reflects per-instance
   values including multiplier scaling.

3. **Recompute gain, GBW, and PM** using the circuit-specific equations
   with SPICE-extracted gm, gds, and node caps.

**Output format — print this table immediately after Step 3:**

```
POST-SIM ANALYTICAL RECALCULATION — Iteration <N>
===================================================
                      | LUT-based   | SPICE-OP-based | SPICE meas. | Model err
Metric                | analytical  | analytical     | (simulator) | (OP vs meas)
DC gain (dB)          | <>          | <>             | <>          | <> dB
GBW (MHz)             | <>          | <>             | <>          | <> %
PM (°)                | <>          | <>             | <>          | <> °

Where:
  LUT-based analytical  = original prediction from design-flow (Step 4/6)
  SPICE-OP-based analyt = recomputed from SPICE OP gm/gds/caps (this step)
  SPICE measured         = value from the AC/transient simulation
  Model err              = (SPICE measured) − (SPICE-OP-based analytical)
                           This isolates the structural model error only.
```

The "Model err" column reveals how much error comes from the analytical
*model structure* (3-pole approximation, missing distributed effects,
NQS) versus how much came from *parameter inaccuracy* (LUT vs actual
gm/gds/caps). A small Model err confirms the equations are sound even
when the LUT-based prediction was far off.

**Implementation template (adapt per topology):**

For the **TSM** topology:
```python
# Extract SPICE OP (abs for caps)
op = sim["raw_response"]["op_region"]
gm3_sp  = op["m3"]["gm"];   gds3_sp = op["m3"]["gds"]
gm1_sp  = op["m1"]["gm"];   gds1_sp = op["m1"]["gds"]
gm7_sp  = op["m7"]["gm"];   gds7_sp = op["m7"]["gds"]
gds8_sp = op["m8"]["gds"]

Cgs7_sp = abs(op["m7"]["cgs"])
Cgs1_sp = abs(op["m1"]["cgs"]); Cgs2_sp = Cgs1_sp  # matched
Cdb1_sp = abs(op["m1"]["cdb"]); Cdb2_sp = Cdb1_sp
Cdb3_sp = abs(op["m3"]["cdb"]); Cdb4_sp = Cdb3_sp
Cgd1_sp = abs(op["m1"]["cgd"]); Cgd2_sp = Cgd1_sp
Cgd3_sp = abs(op["m3"]["cgd"]); Cgd4_sp = Cgd3_sp
Cgd7_sp = abs(op["m7"]["cgd"]); Cdb7_sp = abs(op["m7"]["cdb"])
Cgd8_sp = abs(op["m8"]["cgd"]); Cdb8_sp = abs(op["m8"]["cdb"])

# Node caps from SPICE OP
C1_sp  = Cgs7_sp + Cdb2_sp + Cdb4_sp + Cgd2_sp + Cgd4_sp + Cgd7_sp
CTL_sp = CL + Cdb7_sp + Cdb8_sp + Cgd7_sp + Cgd8_sp
C2_sp  = Cgs1_sp + Cgs2_sp + Cdb1_sp + Cdb3_sp + Cgd2_sp + Cgd3_sp

# Recompute specs from SPICE OP
A_v1_op = gm3_sp / (gds3_sp + gds1_sp)
A_v2_op = gm7_sp / (gds7_sp + gds8_sp)
A0_op   = A_v1_op * A_v2_op

GBW_op  = gm3_sp / (2π × Cc)
ω_c_op  = 2π × GBW_op
G_net1  = gm1_sp + gds1_sp + gds3_sp
p3_op   = G_net1 / C2_sp
p4_op   = gm7_sp / C1_sp
fz_mir  = 2 * p3_op / (2π)
fz_rhp  = gm3_sp / (2π × Cgd3_sp)
PM_op   = 90 - atan(ω_c_op/p3_op) - atan(ω_c_op/p4_op)
        + atan(ω_c_op/(fz_mir*2π)) - atan(ω_c_op/(fz_rhp*2π))
```

For the **5T OTA** topology:
```python
gm1_sp  = op["m1"]["gm"];  gds1_sp = op["m1"]["gds"]
gm5_sp  = op["m5"]["gm"];  gds5_sp = op["m5"]["gds"]
gm6_sp  = op["m6"]["gm"];  gds6_sp = op["m6"]["gds"]

Cdb1_sp = abs(op["m1"]["cdb"]); Cdb2_sp = Cdb1_sp
Cdb5_sp = abs(op["m5"]["cdb"]); Cdb6_sp = Cdb5_sp
Cgd1_sp = abs(op["m1"]["cgd"]); Cgd2_sp = Cgd1_sp
Cgd5_sp = abs(op["m5"]["cgd"])
Cgs5_sp = abs(op["m5"]["cgs"]); Cgs6_sp = Cgs5_sp

C1_sp = CL + Cdb1_sp + Cdb5_sp + Cgd1_sp + Cgd5_sp
C2_sp = Cdb2_sp + Cdb6_sp + Cgs5_sp + Cgs6_sp + Cgd2_sp + Cgd5_sp
C_mir = C2_sp - Cgd5_sp

A0_op  = gm1_sp / (gds1_sp + gds5_sp)
GBW_op = gm1_sp / (2π × C1_sp)
G2     = gds1_sp + gm6_sp + gds6_sp   # note: gds2 = gds1 for matched pair
fp2    = G2 / (2π × C2_sp)
fz_mir = (gm5_sp + gm6_sp) / (2π × C_mir)
fz_rhp = gm1_sp / (2π × Cgd1_sp)
PM_op  = 90 - atan(GBW_op/fp2) + atan(GBW_op/fz_mir) - atan(GBW_op/fz_rhp)
```

**After printing Steps 1–3b, PAUSE and ask the user for confirmation
before continuing.** Print:

```
→ Waiting for confirmation. Type "continue" to proceed to decision logic,
  or provide instructions to adjust.
```

This pause allows the user to inspect results and debug if needed.

## Step 4 — Decision Logic

Track `iteration_count` across simulation loops (initialize to 0 before
the first simulation, increment by 1 each time this step is reached).

```
MAX_ITERATIONS = 10

IF all active specs PASS and all devices in saturation:
  → PASSED — proceed to design-review.md

ELIF iteration_count >= MAX_ITERATIONS:
  → TIMEOUT — proceed to design-review.md (report best achieved)

ELIF any device NOT in saturation:
  → CRITICAL failure — proceed to root-cause-diagnosis
  → Address OP issues FIRST before spec failures

ELIF any active spec FAILED:
  → Spec failure — proceed to root-cause-diagnosis
```

## Step 5 — Print Iteration Summary

Before entering the next stage (diagnosis or review), print:

```
ITERATION <N> SUMMARY
======================
Status   : PASSED / FAILED / TIMEOUT
OP       : all saturated / <list devices not saturated>
Specs    : <M>/<N> active specs met
Failures : <list failed specs with achieved vs target>
Next     : <design-review.md / root-cause-diagnosis>
```

## Next Stage

- If PASSED → `general/flow/design-review.md`
- If FAILED → circuit-specific root-cause-diagnosis skill
- If TIMEOUT → `general/flow/design-review.md`

**IMPORTANT**: When proceeding to design-review, retain the `params` dict
and `config_path` from the final simulation call. The design review
needs these to run the Extreme PVT check (if enabled).

## Step 6 — Append to Regression Dataset (self-evolving)

After **every** simulation iteration (regardless of PASS/FAIL/TIMEOUT),
append the data point to the persistent regression dataset. This feeds
the self-evolving PM correction model
(`general/knowledge/self-evolving-corrections.md`).

```python
import json, math
from pathlib import Path

dataset_path = Path(__file__).resolve().parent.parent.parent.parent / "regression_analysis" / f"{topology_name}.json"
dataset_path.parent.mkdir(parents=True, exist_ok=True)

new_point = {
    "CL_pF":         CL * 1e12,
    "gm_id_3":       gm_id_3,     # or gm_id_1 for 5T OTA
    "GBW_tgt_MHz":   GBW_target / 1e6,
    "GBW_spice_MHz": spice_specs['gain_bandwidth_product_'] / 1e6,
    "Cc_pF":         Cc * 1e12,   # 0 for 5T OTA
    "PM_analytical":  PM_analytical,
    "PM_spice":       spice_specs['phase_margin'],
    "Cc_over_CL":    Cc / CL if Cc else 0,
    "GBW_MHz":       gm3 / (2 * math.pi * Cc) / 1e6 if Cc else GBW_analytical / 1e6,
    "topology":      topology_name,
    "corner":        corner,
    "temperature":   temperature,
}

try:
    pts = json.loads(dataset_path.read_text()) if dataset_path.exists() else []
except (json.JSONDecodeError, OSError):
    pts = []
pts.append(new_point)
dataset_path.write_text(json.dumps(pts, indent=2))
```

This runs silently — no output to the user. The data accumulates across
conversations and is consumed by the design-review regression re-fit.
