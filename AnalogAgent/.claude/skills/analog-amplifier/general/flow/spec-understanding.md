# Spec Understanding Skill

## Purpose

Read and validate the user's design spec form. This is the first stage in
the pipeline — it converts a filled-in spec form into a verified design
objective.

The spec form template is at `general/spec-form-template.md`. The user
fills in the fields and provides the completed form as input (either as
a file or inline in the prompt).

## Procedure

### Step 1 — Read the Spec Form

Parse every field in the form. For each field, extract:
- The value (number with unit)
- The constraint direction (>, <, =) if present

### Step 2 — Validate Required Fields

The following five fields are **required**. If ANY is missing or blank,
print the error and **terminate immediately** — do NOT proceed.

```
REQUIRED FIELDS CHECK
======================
VDD  : <value or MISSING>
CL   : <value or MISSING>
Gain : <value or MISSING>
GBW  : <value or MISSING>
PM   : <value or MISSING>

Status: ALL PRESENT → proceed / MISSING: <list> → STOP
```

If any required field is missing:
→ Print: "Required spec <name> is missing. Please fill in the spec form."
→ **STOP. Do NOT proceed to Circuit Understanding.**

### Step 3 — Check Environment and Apply Defaults

| Field       | Default  | Action if blank                          |
|-------------|----------|------------------------------------------|
| Temperature | 27°C     | Apply default, print reminder to user    |
| Corner      | tt       | Apply default, print reminder to user    |
| VSS         | 0 V      | Apply default silently                   |

If Temperature or Corner is blank, print:
→ "Temperature/Corner not specified — defaulting to 27°C / tt.
   Reminder: set these if your design requires specific conditions."

**LUT temperature availability check (MANDATORY):**

After resolving the temperature, verify that LUT data exists. Run:
```python
from scripts.lut_lookup import list_available_L, _resolve_device, _discover_temps
temps = _discover_temps(_resolve_device('nfet'), corner)
```

- If the exact temperature has pre-generated LUT files → proceed normally.
- If the exact temperature is **between** two available reference
  temperatures → `lut_query` will automatically apply first-order linear
  interpolation at query time. Print:
  → "LUT data at <T>°C not pre-generated. Using first-order linear
     interpolation between <T_lo>°C and <T_hi>°C reference data.
     Note: this is an approximation; accuracy degrades far from
     reference points."
- If the temperature is **outside** the available range → **STOP**.
  Print: "Temperature <T>°C is outside the LUT range [<min>°C, <max>°C].
  Cannot proceed — extrapolation is not supported."

### Step 4 — Parse Optional Specs

For each optional field in the form:
- If **blank**: this spec is not a design target. It will not be
  considered during optimization. The achieved value will still be
  reported in the final design review.
- If **filled**: this spec becomes a design target with the given
  constraint.

Optional fields:
```
Power, SR+, SR-, CMRR, PSRR+, PSRR-,
IRN, ORN, Output_swing, I_bias
```

### Step 4b — Parse Post-Sizing Options

**Extreme_PVT** (default: `no`):
- If `yes`: after the sizing flow converges (SUCCESS or TIMEOUT),
  run two additional simulations with the **final** device sizes:
    1. **Slow extreme**: SS corner, 70°C
    2. **Fast extreme**: FF corner, 0°C
  Results are appended to the design review report (Section 5).
- If `no` or blank: skip. No extra simulations are run.

**Optimize** (default: `no`):
- If `yes`: after the design review completes, invoke the numerical
  optimization skill (`general/knowledge/numerical-optimization.md`).
  This uses a derivative-free optimizer to further improve Power
  (minimize), Gain (maximize), and GBW (maximize) while keeping all
  other specs at or above their user targets.
- If `no` or blank: skip. The LLM-derived sizing is the final result.

### Step 5 — Output Validated Spec Summary

**MANDATORY OUTPUT** — print this before proceeding:

```
VALIDATED SPECIFICATIONS
========================
Required:
  VDD  = <value> V
  CL   = <value> F
  Gain > <value> dB  (<linear> V/V)
  GBW  > <value> Hz
  PM   > <value>°

Environment:
  Temperature = <value>°C
  Corner      = <corner>
  VSS         = <value> V

Active Targets (will be optimized):
  <spec> : <constraint>
  <spec> : <constraint>
  ...

Inactive (blank — will report achieved value only):
  <spec>, <spec>, ...

Post-Sizing:
  Extreme PVT check       : enabled / disabled
  Numerical optimization  : enabled / disabled
```

**GATE**: This output MUST be printed before proceeding.

## Next Stage

→ Proceed to `general/flow/circuit-understanding.md`
