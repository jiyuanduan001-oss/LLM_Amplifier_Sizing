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
Device  | gm/id | gm/gds | id(µA) | vds(V)  | vov(V)  | margin(V) | region
M1      | <>    | <>     | <>     | <>      | <>      | <>        | sat ✅ / linear ❌
...
```

Where:
- `vov = vgs - vth`
- `margin = |vds| - |vov|` (positive = saturated)
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

**After printing Steps 1–3, PAUSE and ask the user for confirmation
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
