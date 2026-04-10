---
name: analog-amplifier
description: >
  Hierarchical skill stack for analog IC design within AnalogAgent. Covers
  OTA/op-amp sizing from netlist + specs, with expert-level equation analysis,
  gm/ID-based sizing, simulation-driven iteration, and root-cause diagnosis.
---

# Analog Amplifier Design Skill Stack

## Rules

1. Execute the design flow in the exact order specified below. Do NOT skip stages.
2. All calculations MUST be done in Python. Never perform mental arithmetic.
3. Follow instructions in each skill file as a procedure to execute, not as
   reference material to absorb.
4. During the optimization loop, use the circuit-specific root-cause-diagnosis
   skill to diagnose failures. Do NOT improvise fixes.

## Architecture

```
general/
  spec-form-template.md              Reusable spec input form
  flow/
    spec-understanding.md            Validate spec form
    circuit-understanding.md         Identify topology, route to design flow
    simulation-verification.md       Verify SPICE results, decide next action
    design-review.md                 Final report
  knowledge/
    numerical-optimization.md        Post-sizing numerical optimizer

circuit-specific/<topology>/
    *-equation.md                    Circuit equations + LUT derivation
    *-design-flow.md                 Step-by-step sizing procedure
    *-root-cause-diagnosis.md        Fault trees for diagnosis
```

### Supported Topologies

| Topology | Directory | Files |
|---|---|---|
| 5-Transistor OTA | `circuit-specific/5TOTA/` | `5t-ota-equation.md`, `5t-ota-design-flow.md`, `5t-ota-root-cause-diagnosis.md` |
| Two-Stage Miller (TSM) | `circuit-specific/tsm/` | `tsm-equation.md`, `tsm-design-flow.md`, `tsm-root-cause-diagnosis.md` |
| Folded-Cascode OTA | `circuit-specific/folded cascode/` | `fc-ota-equation.md`, `fc-ota-design-flow.md`, `fc-ota-root-cause-diagnosis.md` |
| Telescopic OTA | `circuit-specific/telescopic/` | `tco-equation.md`, `tco-design-flow.md`, `tco-root-cause-diagnosis.md` |
| Rail-to-Rail Opamp | `circuit-specific/rtr/` | `r2r-opamp-equation.md`, `r2r-opamp-design-flow.md`, `r2r-opamp-root-cause-diagnosis.md` |

## Design Flow

```
User provides netlist + filled spec form
        │
        ▼
┌─[1] SPEC UNDERSTANDING ───────────────────────────────────────┐
│  Read: general/flow/spec-understanding.md                      │
│  Action: Validate spec form (required/environment/optional)    │
│  Gate: 5 required fields present, or STOP                      │
│  Output: Validated spec summary                                │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─[2] CIRCUIT UNDERSTANDING ────────────────────────────────────┐
│  Read: general/flow/circuit-understanding.md                   │
│  Action: Parse netlist → match to supported topology           │
│  Gate: topology matched, or STOP                               │
│  Output: Topology name + activated design flow                 │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─[3] CIRCUIT-SPECIFIC DESIGN FLOW ────────────────────────────┐
│  Read: circuit-specific/<topology>/*-design-flow.md            │
│  Action: Initial sizing (Steps 1–3) → analytical eval (Step 4)│
│          → analytical fix loop (max 5) → simulation (Step 5)  │
│  Output: Sized devices + simulation results                    │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─[4] SIMULATION & VERIFICATION ───────────────────────────────┐
│  Read: general/flow/simulation-verification.md                 │
│  Action: Check OP → check specs → compare analytical vs SPICE │
│  Gate: PAUSE for user confirmation                             │
│  Decision:                                                     │
│    ALL specs met + ALL devices saturated → go to [6]           │
│    ANY failure → go to [5]                                     │
│    iteration_count >= 10 → go to [6] (TIMEOUT)                │
└────────────────────────────────────────────────────────────────┘
        │ (failure)
        ▼
┌─[5] ROOT-CAUSE DIAGNOSIS ────────────────────────────────────┐
│  Read: circuit-specific/<topology>/*-root-cause-diagnosis.md   │
│  Action: Identify fault tree → apply fix → output new sizes    │
│  → Return to [3] to re-derive and re-simulate                 │
└────────────────────────────────────────────────────────────────┘
        │ (success or timeout)
        ▼
┌─[6] DESIGN REVIEW ───────────────────────────────────────────┐
│  Read: general/flow/design-review.md                           │
│  Output: Sections 1–4 (always)                                 │
│  IF Extreme_PVT = yes:                                         │
│    Run sim at SS/70°C and FF/0°C with LLM params               │
│    Output: Section 5 — Extreme PVT results                     │
│  IF Optimize = yes:                                            │
│    Read: general/knowledge/numerical-optimization.md           │
│    Run optimizer → minimizes power, maximizes gain/GBW         │
│    Output: Section 6 — Optimized sizing + comparison           │
│    IF Extreme_PVT = yes:                                       │
│      Re-run PVT with optimized params                          │
│      Output: Section 7 — Extreme PVT (optimized)              │
└────────────────────────────────────────────────────────────────┘
```

## Simulation Loop

```
iteration_count = 0
MAX_ITERATIONS = 10

LOOP:
  iteration_count += 1

  [3] Execute design flow (initial sizing or apply fix from diagnosis)
  [4] Simulate and verify
      IF all specs ✅ AND all devices in saturation:
        → BREAK → go to [6] Design Review (SUCCESS)
      ELIF iteration_count >= MAX_ITERATIONS:
        → BREAK → go to [6] Design Review (TIMEOUT)
      ELSE:
        → [5] Root-cause diagnosis → apply fix → GOTO LOOP
```
