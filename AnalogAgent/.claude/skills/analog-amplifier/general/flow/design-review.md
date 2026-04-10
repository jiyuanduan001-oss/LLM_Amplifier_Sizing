# Design Review Skill

## Purpose

Summarize the final design state after either (a) all specs are met, or
(b) the iteration limit is reached.

## Trigger

This skill is invoked in exactly two cases:
1. **SUCCESS**: All active specs met, all devices in saturation.
2. **TIMEOUT**: 10 iterations reached without full convergence.

## Report Format

Print the following report exactly as structured. Sections 1–4 are
always required. Section 5 is conditional (see Step 2 below).

### Step 1 — Compute Analytical Specs for Final Sizes

Before printing the report, re-derive all spec predictions analytically
using the **final device sizes** (the same sizes that produced the
converged simulation). Use the circuit-specific `*-equation.md` equations
and compute everything in Python. This gives a side-by-side comparison
of the analytical model vs SPICE for the final design point.

### Step 2 — Print Sections 1–4

```
DESIGN REVIEW
==============

1. OUTCOME
----------
STATUS: SUCCESS — all specs met in <N> iterations
   or: TIMEOUT — <M>/<N> active specs met after 10 iterations

2. SPECIFICATION COMPLIANCE
----------------------------
Spec          | Target      | Analytical  | SPICE       | Error   | Margin  | Status
<spec>        | <constraint>| <value>     | <value>     | <+/-%>  | <+/-%>  | pass/fail
...

Where:
  Analytical = value computed from LUT-derived small-signal parameters
               for the final device sizes (using equations from the
               circuit-specific *-equation.md skill)
  SPICE      = value from the final converged simulation
  Error      = (SPICE - Analytical) / Analytical × 100%
  Margin     = distance from SPICE value to target

For specs that are simulation-only (e.g. IRN, noise), put "—" in the
Analytical column.

Reported (no target):
  <spec> = <value> (analytical: <value>)
  ...

3. SIZING SUMMARY
------------------
Topology : <name>
Process  : SKY130 / <corner> / <temp>
VDD      : <value> V
CL       : <value> F
I_bias   : <value> A

Role          | Device | W(µm) | L(µm) | M  | ID(µA) | gm/ID | Vov(mV)
<role>        | <dev>  | <W>   | <L>   | <M>| <ID>   | <>    | <>
...

CircuitCollector params:
  <param> = <value>
  ...

4. ITERATION HISTORY
---------------------
Iter | Change Made              | Key Results            | Decision
1    | Initial sizing           | A0=<>, GBW=<>, PM=<>  | pass/fail: <which>
2    | <fix from diagnosis>     | A0=<>, GBW=<>, PM=<>  | pass/fail: <which>
...
```

### Step 3 — Extreme PVT Check (conditional)

**GATE**: Check the `Extreme_PVT` flag from the validated spec summary
(Stage [1], Step 4b). If `Extreme_PVT` is `no` or was left blank →
**SKIP this step entirely**. If `yes` → execute the procedure below.

**Procedure:**

Using the **exact same `params` dict and `config_path`** that produced
the final PASSED / TIMEOUT result, run two additional simulations.
Do NOT re-size or modify any device parameter — only override
`corner` and `temperature`.

```python
from tools.bridge_twostage import simulate_circuit  # or topology-appropriate bridge

# params and config_path are from the final converged iteration

# Slow extreme: SS corner, 70°C
sim_ss70 = simulate_circuit(
    params,
    config_path=config_path,
    corner='ss',
    temperature=70,
)

# Fast extreme: FF corner, 0°C
sim_ff0 = simulate_circuit(
    params,
    config_path=config_path,
    corner='ff',
    temperature=0,
)
```

For each simulation result, extract `specs` and `transistors`.
For each transistor, compute `margin = |vds| - |vov|` and flag
any device with `margin < 0` (not saturated).

**Print Section 5:**

```
5. EXTREME PVT CHECK
---------------------
Extreme PVT Results
====================
Spec          | Target      | Design corner | SS/70°C     | FF/0°C
<spec>        | <constraint>| <achieved>    | <value>     | <value>
...

OP Flags (devices leaving saturation):
  SS/70°C: <list devices with margin < 0, or "all saturated">
  FF/0°C:  <list devices with margin < 0, or "all saturated">

Summary:
  SS/70°C: <N>/<M> specs met | <notes on critical failures>
  FF/0°C:  <N>/<M> specs met | <notes on critical failures>
```

### Step 4 — Numerical Optimization (conditional)

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

Role          | Device | W(µm) | L(µm) | M  | ID(µA) | gm/ID | Vov(mV)
<role>        | <dev>  | <W>   | <L>   | <M>| <ID>   | <>    | <>
...

CircuitCollector params:
  <param> = <value>
  ...
```

**If `Extreme_PVT = yes`:** After printing Section 6, re-run the
Extreme PVT check (Step 3 procedure) using the **optimized** params.
Append the results as **Section 7**:

```
7. EXTREME PVT CHECK (optimized design)
-----------------------------------------
(same format as Section 5, but using the optimized params)

Spec          | Target      | Design corner | SS/70°C     | FF/0°C
<spec>        | <constraint>| <achieved>    | <value>     | <value>
...

OP Flags (devices leaving saturation):
  SS/70°C: <list devices with margin < 0, or "all saturated">
  FF/0°C:  <list devices with margin < 0, or "all saturated">
```
