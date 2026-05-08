# Design Review Skill

## Purpose

Summarize the final design state after either (a) all specs are met, or
(b) the iteration limit is reached.

## Trigger

This skill is invoked in exactly two cases:
1. **SUCCESS**: All active specs met, all devices in saturation.
2. **TIMEOUT**: 10 iterations reached without full convergence.

## Rules

1. The report format below is **strict**. Do NOT rename sections, do NOT
   add your own sections (e.g. "Specification Targets", "Operating Point"),
   do NOT merge sections, do NOT reorder columns.
2. Sections 1–4 are **always required**. Sections 5/6/7 are conditional
   (gates specified in Steps 3–4).
3. Every field marked `<...>` MUST be filled in — no placeholders in
   the final output. If a value is unavailable, write `—`.
4. All analytical values MUST be re-computed from the FINAL device sizes
   using Python before printing the report (Step 1 is a gate).
5. Track the iteration history as you run the flow (Step 0 below) so
   Section 4 can be filled. Do NOT reconstruct it from memory at the end.
6. OP-based values (gain, GBW, PM recomputed from SPICE OP data) MUST
   be computed in Step 1c before printing the report. Do NOT rely on
   values computed during intermediate simulation-verification steps —
   they may be from a different iteration.

## Procedure

### Step 0 — Maintain iteration log (during the flow, before this skill)

Every time design-flow Step 5 returns SPICE results, append one row to
an `iteration_log` list:

```python
iteration_log.append({
    "iter":    <N>,                                    # 1, 2, 3, ...
    "change":  "<one-line description of what changed>",  # e.g. "Initial sizing" or "raised (gm/ID)_1 to 13"
    "A0_dB":   <sp['dcgain_']>,
    "GBW_MHz": <sp['gain_bandwidth_product_']/1e6>,
    "PM_deg":  <sp['phase_margin']>,
    "Power_uW":<sp['power']>,
    "decision":"pass" or "fail: <which specs>",
})
```

This log feeds Section 4 directly — do NOT try to remember it.

### Step 1 — Compute analytical predictions for FINAL sizes (GATE)

Before printing anything, re-derive every spec analytically using the
circuit-specific `*-equation.md` with the **final** (converged) device
sizes. Compute in Python; store in a dict `analytical`:

```python
analytical = {"A0_dB": ..., "GBW_MHz": ..., "PM_deg": ...,
              "SR_Vus": ..., "CMRR_dB": ..., "Power_uW": ...,
              "Swing_V": ..., ...}
```

**GATE**: Print this dict before proceeding — this verifies Step 1 ran.
If any required spec is missing from `analytical`, go back and compute it.

### Step 1b — Re-fit regression and compute PM_regression (MANDATORY)

Re-fit the self-evolving PM correction from the full accumulated
dataset, then apply it to get `PM_regression`. This ensures the
regression uses all data points collected so far (including the
current design's iterations appended in simulation-verification Step 6).

```python
import json, numpy as np
from pathlib import Path

dataset_path = Path("regression_analysis") / f"{topology_name}.json"

# Load dataset
try:
    pts = json.loads(dataset_path.read_text()) if dataset_path.exists() else []
except (json.JSONDecodeError, OSError):
    pts = []

# Per-topology file — no filtering needed
topo_pts = pts

Cc_over_CL = Cc / CL if Cc else 0

if len(topo_pts) >= 6:
    # Re-fit: err = b_GBW × GBW_MHz + b_CcCL × Cc_over_CL + intercept
    X = np.column_stack([
        [p['GBW_MHz'] for p in topo_pts],
        [p.get('Cc_over_CL', 0.4) for p in topo_pts],
        np.ones(len(topo_pts)),
    ])
    y = np.array([p['PM_analytical'] - p['PM_spice'] for p in topo_pts])
    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    b_GBW, b_CcCL, intercept = coeffs
    y_pred = X @ coeffs
    R2 = 1 - np.sum((y - y_pred)**2) / np.sum((y - np.mean(y))**2)
    PM_regression = analytical["PM_deg"] - (b_GBW * analytical["GBW_MHz"] + b_CcCL * Cc_over_CL + intercept)
    print(f"Regression re-fit: err = {b_GBW:.3f}×GBW {b_CcCL:+.1f}×Cc/CL {intercept:+.1f}° "
          f"(R²={R2:.3f}, N={len(topo_pts)} points)")
else:
    # Fallback to hardcoded defaults from self-evolving-corrections.md
    if 'tsm' in topology_name:
        PM_regression = analytical["PM_deg"] - (0.31 * analytical["GBW_MHz"] + (-134.0) * Cc_over_CL + 48.6)
    else:
        # 5T OTA fallback — needs ft_min
        PM_regression = analytical["PM_deg"] - 26 * (analytical["GBW_MHz"] * 1e6 / ft_min)
    print(f"Regression: using default coefficients (dataset has < 6 points)")

analytical["PM_regression"] = PM_regression
```

Print the regression result alongside the analytical PM before proceeding.

### Step 1c — Compute OP-based analytical values (GATE)

Using the **final** simulation result `sim`, extract SPICE OP data and
recompute gain, GBW, and PM with the same equations used in
simulation-verification.md Step 3b. Store in an `op_based` dict:

```python
op_based = {"A0_dB": ..., "GBW_MHz": ..., "PM_deg": ...}
```

Follow the topology-specific code templates in
simulation-verification.md Step 3b (TSM or 5T OTA). Use `Cc` and `Rc`
from the final sizing, `CL` from the spec form.

**GATE**: Print `op_based` before proceeding.

### Step 2 — Print the report (REQUIRED SECTIONS 1–4)

Copy the template below **verbatim** into your response, replacing every
`<...>` with the computed value. Do not add, remove, rename, or reorder
sections. Keep the exact headers and separator lines.

```text
==========================================================
DESIGN REVIEW
==========================================================

1. OUTCOME
----------
STATUS: <SUCCESS — all specs met in N iterations>
     or <TIMEOUT — M/K active specs met after 10 iterations>

2. SPECIFICATION COMPLIANCE
----------------------------
Spec          | Target       | Analytical  | Regression  | OP-based    | SPICE       | LUT err  | Model err | Margin   | Status
<spec>        | <constraint> | <value>     | <value>     | <value>     | <value>     | <+/-%>   | <+/-%>    | <+/-%>   | pass/fail
...

Reported (no target):
  <spec> = <SPICE value>   (analytical: <value>, OP-based: <value>)
  ...

Where:
  Analytical = value computed from LUT-derived small-signal parameters
               for the final device sizes (circuit-specific *-equation.md)
  Regression = value corrected by the self-evolving regression model
               (from general/knowledge/self-evolving-corrections.md).
               For TSM PM: PM_regression = PM_analytical − (b_GBW × GBW_MHz + b_CcCL × Cc/CL + intercept).
               For 5T OTA PM: PM_regression = PM_analytical − 26 × (GBW/ft_min).
               For non-PM specs: put "—".
  OP-based   = value recomputed using SPICE-extracted OP data (gm, gds, caps)
               plugged back into the same analytical equations
               (from simulation-verification.md Step 3b)
  SPICE      = value from the final converged simulation
  LUT err    = (SPICE - Analytical) / Analytical × 100%
               Shows total prediction error (LUT param error + model error)
  Model err  = (SPICE - OP-based) / OP-based × 100%
               Shows structural model error only (LUT error removed)
  Margin     = distance from SPICE value to target (+ = pass margin)
  For simulation-only specs (noise, Vos), put "—" in Analytical, Regression,
  and OP-based.

  For gain, GBW, and PM, Analytical, Regression, and OP-based are all mandatory.
  For other specs, Regression and OP-based are optional.

3. SIZING SUMMARY
------------------
Topology : <name>
Process  : SKY130 / <corner> / <temp>°C
VDD      : <value> V
CL       : <value> F
I_bias   : <value> A

Role          | Device | W(µm) | L(µm) | M  | ID(µA) | gm/ID | Vdsat(mV)
<role>        | <dev>  | <W>   | <L>   | <M>| <ID>   | <>    | <>
...

CircuitCollector params:
  <param> = <value>
  ...

4. ITERATION HISTORY
---------------------
Iter | Change Made                     | A0(dB) | GBW(MHz) | PM(°) | Power(µW) | Decision
1    | Initial sizing                  | <>     | <>       | <>    | <>        | pass/fail: <which>
2    | <fix from diagnosis>            | <>     | <>       | <>    | <>        | pass/fail: <which>
...
```

**Validation checklist (run mentally before finishing Step 2):**
- [ ] Section 1 starts with `STATUS:` line
- [ ] Section 2 table has all 10 columns: Spec, Target, Analytical, Regression, OP-based, SPICE, LUT err, Model err, Margin, Status
- [ ] Section 3 table has all 8 columns: Role, Device, W, L, M, ID, gm/ID, Vdsat
- [ ] Section 3 lists CircuitCollector params (the exact dict sent to `simulate_circuit`)
- [ ] Section 4 lists one row per iteration that was actually run
- [ ] No extra sections ("Spec Targets", "Operating Point", etc.) inserted

## Common mistakes (do NOT repeat)

- ❌ Adding a "Specification Targets" section before Section 1 — the targets
  belong in Section 2's "Target" column, nothing else.
- ❌ Replacing Section 2 with a simple "SPICE vs Target" 4-column table —
  the Analytical column is mandatory; it is the whole point of this report.
- ❌ Adding a standalone "Operating Point" section — OP info lives in
  Section 3's Vdsat column and in any text notes under the table.
- ❌ Skipping Section 4 because "it's obvious from conversation" — the
  iteration history is part of the deliverable.
- ❌ Printing the report before running Step 1 — analytical values
  computed from memory or guessed are not acceptable.
- ❌ Skipping the OP-based column — gain, GBW, and PM must be
  recomputed from SPICE OP data in Step 1c, not recalled from memory.

### Step 2b — Save simulation waveforms and plots for final sizing (MANDATORY)

After printing the report, re-run the final simulation with
`save_waveforms=True` to dump AC/transient waveform data, then
**generate plots** (Bode, transient, swing PNGs) in the AnalogAgent
`simulation_waveform/nominal/` subfolder.

**Always use `generate_all_plots`** — it copies the raw waveform text
files AND regenerates the PNG plots from the current data.  Never use
`collect_waveforms` alone, as it only copies text files and leaves
stale PNGs from previous runs.

`topology_name`, `params`, `config_path`, `corner`, `temperature`, `VDD`,
and `CL` are all carried forward from Stage [2] (circuit-understanding)
and Stage [3] (design flow). They must still be in scope.

```python
from tools.bridge_generic import simulate_circuit
from tools.waveform_utils import generate_all_plots

# Re-run final simulation with waveform saving enabled
sim = simulate_circuit(
    params,
    config_path=config_path,
    corner=corner,
    temperature=temperature,
    supply_voltage=VDD,
    CL=CL,
    save_waveforms=True,
)
# Copy waveforms AND regenerate PNG plots
generate_all_plots(topology_name, category='nominal', specs=sim['specs'])
```

### Step 3 — Section 5: Extreme PVT Check (conditional)

**GATE**: Check the `Extreme_PVT` flag from the validated spec summary
(Stage [1], Step 4b). If `Extreme_PVT` is `no` or was left blank →
**SKIP this step entirely**. If `yes` → execute the procedure below.

**Procedure:**

Using the **exact same `params` dict and `config_path`** that produced
the final PASSED / TIMEOUT result, run two additional simulations.
Do NOT re-size or modify any device parameter — only override
`corner` and `temperature`.

```python
from tools.bridge_generic import simulate_circuit

# params and config_path are from the final converged iteration

# Slow extreme: SS corner, 85°C
sim_ss85 = simulate_circuit(
    params,
    config_path=config_path,
    corner='ss',
    temperature=85,
    supply_voltage=VDD,
    CL=CL,
)

# Fast extreme: FF corner, −40°C
sim_ff_m40 = simulate_circuit(
    params,
    config_path=config_path,
    corner='ff',
    temperature=-40,
    supply_voltage=VDD,
    CL=CL,
)

# Save PVT waveforms AND regenerate plots
from tools.waveform_utils import generate_all_plots

simulate_circuit(params, config_path=config_path, corner='ss',
    temperature=85, supply_voltage=VDD, CL=CL, save_waveforms=True)
generate_all_plots(topology_name, category='pvt_ss_85C', specs=sim_ss85['specs'])

simulate_circuit(params, config_path=config_path, corner='ff',
    temperature=-40, supply_voltage=VDD, CL=CL, save_waveforms=True)
generate_all_plots(topology_name, category='pvt_ff_m40C', specs=sim_ff_m40['specs'])
```

**IMPORTANT:** `supply_voltage` (VDD) and `CL` MUST come from the validated
spec form (Stage [1]). These are the same values used for LUT queries and
analytical sizing. Omitting them causes the simulator to fall back to TOML
defaults (typically 1.8V/5pF), creating a mismatch between the LUT-based
sizing and the SPICE verification. The `CL` parameter accepts **Farads**
(SI); the bridge converts to picoFarads internally for CircuitCollector.

For each simulation result, extract `specs` and `transistors`.
For each transistor, compute `margin = |vds| - vdsat` and flag
any device with `margin < 0` (not saturated).

**Print Section 5:**

```
5. EXTREME PVT CHECK
---------------------
Extreme PVT Results
====================
Spec          | Target      | Design corner | SS/85°C     | FF/−40°C
<spec>        | <constraint>| <achieved>    | <value>     | <value>
...

OP Flags (devices leaving saturation):
  SS/85°C: <list devices with margin < 0, or "all saturated">
  FF/−40°C:  <list devices with margin < 0, or "all saturated">

Summary:
  SS/85°C: <N>/<M> specs met | <notes on critical failures>
  FF/−40°C:  <N>/<M> specs met | <notes on critical failures>
```

### Step 4 — Section 6/7: Numerical Optimization (conditional)

**GATE**: Check the `Optimize` flag from the validated spec summary
(Stage [1], Step 4b). If `Optimize` is `no` or was left blank →
**SKIP this step. The design review is the final output.**
If `yes` → execute the procedure below.

**Procedure:**

**Step 4a — Ask the user for optimization priority.**

Before invoking the optimizer, print the following prompt and
**PAUSE** for user input:

```
Optimization is enabled. Which metric should be prioritized?

  1. Power   — minimize power consumption (default)
  2. Gain    — maximize DC gain
  3. GBW     — maximize gain-bandwidth product

Enter 1, 2, or 3 (or press Enter for default):
```

Map the user's choice to optimizer weights:

| Choice | w_pwr | w_gain | w_gbw | Description |
|--------|-------|--------|-------|-------------|
| 1 (Power) | 1.0 | 0.15 | 0.15 | Aggressive power reduction |
| 2 (Gain)  | 0.15 | 1.0 | 0.15 | Maximize gain headroom |
| 3 (GBW)   | 0.15 | 0.15 | 1.0 | Maximize bandwidth |

If the user does not respond or presses Enter, use choice 1 (Power).

**Step 4b — Run the optimizer.**

Invoke `general/knowledge/numerical-optimization.md` with the
`params` dict, `config_path`, user targets, `corner`,
`temperature`, and the **selected weights** from Step 4a.
The optimization skill returns an optimized `params` dict and its
simulation results.

After the optimization completes, append **Section 6** to the
report. If the optimized design is worse than the LLM sizing
(cost did not improve), skip Section 6 and print:
→ "Optimization did not improve the design. Keeping LLM sizing."

**Print Section 6:**

```
6. NUMERICAL OPTIMIZATION
--------------------------
Priority   : <Power / Gain / GBW>
Weights    : w_pwr=<>, w_gain=<>, w_gbw=<>
Method     : <method name> (λ=<N>, <N> generations)
Sim calls  : <N>
Runtime    : <N> min

6a. Parameter Changes
~~~~~~~~~~~~~~~~~~~~~~
Parameter   | LLM sizing | Optimized  | Change
<param>     | <value>    | <value>    | <+/-%>
...
(only show parameters that changed by more than 0.1%)

6b. Specification Comparison
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Spec          | Target      | LLM sizing | Optimized  | Change  | Status
<spec>        | <constraint>| <value>    | <value>    | <+/-%>  | pass/fail
...

All constraints satisfied: yes/no

6c. Optimized Sizing Summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
(same format as Section 3, but with the optimized params)

Role          | Device | W(µm) | L(µm) | M  | ID(µA) | gm/ID | Vdsat(mV)
<role>        | <dev>  | <W>   | <L>   | <M>| <ID>   | <>    | <>
...

CircuitCollector params:
  <param> = <value>
  ...
```

**Save optimized waveforms and plots:**
```python
sim_opt = simulate_circuit(optimized_params, config_path=config_path, corner=corner,
    temperature=temperature, supply_voltage=VDD, CL=CL, save_waveforms=True)
generate_all_plots(topology_name, category='optimized', specs=sim_opt['specs'])
```

**If `Extreme_PVT = yes`:** After printing Section 6, re-run the
Extreme PVT check (Step 3 procedure) using the **optimized** params.
Append the results as **Section 7**:

```
7. EXTREME PVT CHECK (optimized design)
-----------------------------------------
(same format as Section 5, but using the optimized params)

Spec          | Target      | Design corner | SS/85°C     | FF/−40°C
<spec>        | <constraint>| <achieved>    | <value>     | <value>
...

OP Flags (devices leaving saturation):
  SS/85°C: <list devices with margin < 0, or "all saturated">
  FF/−40°C:  <list devices with margin < 0, or "all saturated">
```

**Save optimized PVT waveforms and plots:**
```python
sim_opt_ss = simulate_circuit(optimized_params, config_path=config_path, corner='ss',
    temperature=85, supply_voltage=VDD, CL=CL, save_waveforms=True)
generate_all_plots(topology_name, category='optimized_pvt_ss', specs=sim_opt_ss['specs'])

sim_opt_ff = simulate_circuit(optimized_params, config_path=config_path, corner='ff',
    temperature=-40, supply_voltage=VDD, CL=CL, save_waveforms=True)
generate_all_plots(topology_name, category='optimized_pvt_ff', specs=sim_opt_ff['specs'])
```
