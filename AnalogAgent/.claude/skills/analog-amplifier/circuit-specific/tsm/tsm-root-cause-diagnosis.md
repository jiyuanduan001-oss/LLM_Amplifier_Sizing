# TSM Root-Cause Diagnosis

## Purpose

When a TSM design fails to meet specs (analytically or in simulation),
this skill maps each failure to its root cause and recommends a fix.

## Rules

1. Follow the priority order: fix saturation issues before spec failures.

---

## Priority Order

1. **CRITICAL**: Any device not in saturation → fix OP first
2. **NORMAL**: Spec failures → fix per fault tree below

---

## Fault Tree: Device Not Saturated

### M6 (TAIL) in linear region

Most common failure. VDS_M6 = V_cm - VGS_M3 - VSS must exceed Vdsat_M6.

```
Root cause: VDS_M6 < Vdsat_M6
  Mechanism: I_tail/I_bias mirror ratio too high → VGS_M6 large → VDS compressed
  OR: V_cm too low for the stack height

Fix priority:
  1. Reduce VGS(DIFF_PAIR) by increasing gm/ID of DIFF_PAIR (M3, M4)
     ⚠️ Side effect: larger input pair, more parasitic cap
  2. Increase gm/ID of TAIL → reduces Vdsat_M6
     ⚠️ Side effect: larger device area
  3. Increase I_bias to reduce mirror ratio (target ratio ≤ 8:1)
  4. If all fail: topology may not support these specs at this VDD
```

### M7 (OUTPUT_CS) in linear region

```
Root cause: VDD - V_out < Vdsat_M7
  Mechanism: V_out,max spec too close to VDD for M7's Vdsat

Fix:
  1. Increase W7 (reduces Vdsat at same ID7)
     ⚠️ Side effect: larger Cgs7, slower p4
  2. Increase gm/ID of OUTPUT_CS (weaker inversion, lower Vdsat)
  3. Reduce ID7 (but check PM — lower gm7 → lower p2)
```

### M8 (OUTPUT_BIAS) in linear region

```
Root cause: V_out < Vdsat_M8
  Mechanism: V_out,min spec too aggressive for M8's Vdsat

Fix:
  1. Increase W8 (reduces Vdsat at same ID8)
     This means increasing W5 (shared unit-cell W/L)
  2. Reduce ID7 (= ID8)
  3. Relax V_out,min spec
```

### M3/M4 (DIFF_PAIR) in linear region

```
Root cause: V_cm too low, or first-stage output node voltage wrong
  Mechanism: systematic offset condition not met → drain voltages of M3/M4 unequal

Fix:
  1. Check V_cm range vs bias constraints
  2. Verify systematic offset condition:
     (W1/L1)/(W7/L7) = (1/2)·(W6/L6)/(W8/L8)
     Adjust mirror ratios to satisfy offset condition
```

---

## Fault Tree: Gain Too Low

```
A0 < A0_target
    │
    ├── First-stage gain too low (A_v1 = gm3/(gds3+gds1))
    │   ├── gds3 too large → increase L3
    │   │   ⚠️ Side effect: larger Cgs3, Cgd3 → may affect GBW
    │   ├── gds1 too large → increase L1
    │   │   ⚠️ Side effect: larger Cgs1 → lower mirror pole p3 → PM may degrade
    │   └── Check from OP: intrinsic gain of M3 vs M1
    │       → If one device has much lower gm_gds → that's the bottleneck
    │
    └── Second-stage gain too low (A_v2 = gm7/(gds7+gds8))
        ├── gm7 too low → increase W7 or ID7
        ├── gds7 + gds8 too high → increase L7 and/or L8 (L8 = L5)
        │   ⚠️ Side effect: longer L7 → slower p2, p4
        └── OP check: verify gm7, gds7, gds8 from simulation

Side effects of fixing gain:
  Increasing L → larger parasitics → GBW may decrease
  Increasing ID → more power (almost no gain benefit, since gds also rises)
  These tradeoffs must be reported to the user.
```

---

## Fault Tree: GBW Too Low

```
GBW < GBW_target   (GBW = gm3/(2π·Cc))
    │
    ├── gm3 too low
    │   → Increase I_tail to get larger gm3 (Especially when there is power margin available. )
    │
    ├── Cc too large
    │   → Reduce Cc (but verify PM still meets target)
    │
    └── Non-dominant pole pulling effective BW down
        ├── p2 too low → increase gm7
        ├── p3 too low → reduce C2 (smaller W1/W2 or shorter L1)
        └── Check: is SPICE GBW much lower than gm3/(2π·Cc)?
            → If yes: parasitic pole separation assumption is violated
```

---

## Fault Tree: Phase Margin Too Low

```
PM < PM_target
    │
    ├── Output pole p2 too close to ω_c
    │   → Increase gm7 (increase W7 or ID7)
    │   → Or increase Cc (moves ω_c down, but reduces GBW)
    │
    ├── Mirror pole p3 too close to ω_c
    │   → Reduce capacitance at mirror node:
    │     - Reduce W1, W2 (reduces Cgs1, Cgs2)
    │     - Reduce W4 (reduces Cdb4, Cgd4)
    │   → Or increase gm1 (move p3 up — but W1 must also increase → tradeoff)
    │
    ├── Compensation pole p4 too close to ω_c
    │   → Increase gm7 (raises p4 — recompute via KCL cubic)
    │   → Or reduce C1 parasitic (shorter L7 or smaller W1/W2)
    │
    ├── RHP zero not cancelled / p2 not fully cancelled
    │   → Recompute Rc = 1/gm7 + 1/(p2_kcl × Cc) after any parameter change
    │
    └── PM estimation was optimistic
        → Check: was arctan(x)≈x used with x > 0.47?
        → Switch to exact arctan computation
        → Or just trust SPICE PM and adjust accordingly
```

---

## Fault Tree: Slew Rate Too Low

SR+ and SR- are separate specs:
```
SR+ = I_tail / Cc
SR- = min(I_tail / Cc, ID7 / CTL)
```

```
SR+ < SR+_target
    │
    └── I_tail/Cc too low
        → Increase I_tail
        → Or reduce Cc (but check PM)
        ⚠️ Side effect: more power

SR- < SR-_target   (identify which term limits min())
    │
    ├── Limited by I_tail/Cc (1st stage too slow)
    │   → Increase I_tail
    │   → Or reduce Cc (but check PM)
    │   ⚠️ Side effect: more power
    │
    └── Limited by ID7/CTL (2nd stage too slow)
        → Increase ID7
        → Or reduce CL (usually fixed)
        ⚠️ Side effect: more power
```

---

## Fault Tree: Output Swing Too Low

```
V_swing = VDD - Vdsat_M7 - Vdsat_M8 < Swing_target
    │
    ├── Vdsat_M7 too large → increase gm/ID of OUTPUT_CS (weaker inversion)
    │   ⚠️ Side effect: lower ft, larger W7
    │
    └── Vdsat_M8 too large → increase gm/ID of bias mirrors (weaker inversion)
        This means increasing W5 (shared unit-cell), which increases W8
        ⚠️ Side effect: larger device area
```

---

## Fault Tree: CMRR Too Low

```
CMRR = 2·gm3·gm1/[(gds3+gds1)·gds6] < CMRR_target
    │
    ├── gds6 too high (ro6 too low) → increase L5 (= L6)
    │   This is the primary fix. TAIL is not speed-critical.
    │   ⚠️ When M6 margin < 50 mV, OP-extracted gds6 overestimates
    │   the effective gds. The formula may under-predict CMRR by 5–7 dB.
    │   If SPICE CMRR passes but formula says fail: check M6 margin.
    │
    └── A0 too low → fix gain first (see gain fault tree)
```

---

## Fault Tree: PSRR Too Low

```
PSRR⁻ — use the two-path formula (see tsm-equation.md):
  A_VSS_M8 = gds8 / (gds7 + gds8)                  [M8 direct]
  A_VSS_M6 = gds6·gds1·gm7 / [2·gm1·(gds3+gds1)·(gds7+gds8)]  [M6 tail]
  PSRR⁻    = A0 / (A_VSS_M8 + A_VSS_M6)

  PSRR⁻ too low:
    │
    ├── A_VSS_M6 dominates (check: A_VSS_M6 > A_VSS_M8)
    │   Root cause: gds6 too high (M6 near triode)
    │   → Increase L5 (= L6) for higher ro6
    │   → Or increase M6 Vds headroom (raise gm/ID of DIFF_PAIR to reduce VGS_M3)
    │
    ├── A_VSS_M8 dominates (check: A_VSS_M8 > A_VSS_M6)
    │   Root cause: gds8 too high
    │   → Increase L5 (= L8) for higher ro8
    │
    └── Both paths comparable
        → Increase L5 (benefits both ro6 and ro8)
        → Or improve first-stage gain (increase L3 or L1)

  ⚠️ The legacy formula PSRR⁻ = gm3·gm7/[(gds3+gds1)·gds8] ignores the
  M6 tail coupling path. Do NOT use it when M6 Vds margin < 100 mV —
  it overestimates PSRR⁻ by 10–20 dB.

PSRR⁺ — use the corrected formula (see tsm-equation.md):
  PSRR⁺ = A0 · (gds7 - gds8) / |gds7 - gm7·gds3/gm1|

  Net5 tracks VDD through M1/M2 (sources at VDD). The VDD coupling
  at the output depends on the cancellation between gds7 (pushes Vout
  toward VDD) and gm7·gds3/gm1 (net5 overshoot opposes the push).

  PSRR⁺ too low:
    │
    ├── Cancellation in denominator is poor (gm7·gds3/gm1 << gds7)
    │   → Increase gm7·gds3/gm1 to approach gds7:
    │     - Increase gds3 (shorter L3) — but hurts gain, usually undesirable
    │     - Increase gm7/gm1 ratio — increase gm7 or reduce gm1
    │
    ├── A0 too low → fix gain first (see gain fault tree)
    │
    └── gds7 ≈ gds8 (denominator gds7-gds8 is small)
        → This actually HELPS PSRR⁺ (numerator shrinks proportionally)
        → If gds7 < gds8: sign flips, different cancellation regime

  ⚠️ The legacy formula PSRR⁺ ≈ gm3/gds3 underestimates PSRR⁺ by
  20–25 dB because it ignores that net5 naturally tracks VDD through
  the PMOS load (M1/M2 sources at VDD).
```

---

## Fault Tree: Power Too High

```
P = VDD × (I_bias + I_tail + ID7) > P_target
    │
    ├── I_tail too high
    │   → Driven by GBW or SR requirement
    │   → Increase gm/ID of DIFF_PAIR (get same gm with less current)
    │   → Or relax GBW/SR spec
    │
    ├── ID7 (second stage) too high
    │   → Driven by PM constraint (need large gm7 for p2)
    │   → Increase gm/ID of OUTPUT_CS (but check fT constraint)
    │   → Or relax PM spec
    │
    └── Bias overhead
        → Optimize I_bias (reduce if mirror ratios allow)
```

---

## Fault Tree: Noise Too High

Noise parameters (Kf, Cox) are not in the LUT. Noise is best evaluated
by the simulator. For pre-simulation guidance:

```
Integrated noise too high
    │
    ├── Thermal noise dominated
    │   → Increase gm3 (more current or lower gm/ID)
    │   → gm1/gm3 ratio also matters — minimize gm1 relative to gm3
    │
    └── 1/f noise dominated
        → Increase W3 × L3 (more input pair area)
        → Check load contribution: if (Kf_p·µn·W3·L3)/(Kf_n·µp·W1·L1) > 0.5,
          load noise is significant → increase L1
```

---

## Fault Tree: Cascode / LV Cascode Sub-Block Issues

Applies only when LOAD or OUTPUT_BIAS uses `sub_block_type = "cascode"` or
`"lv_cascode"` (see `general/knowledge/mirror-load-structures.md`).

### Internal pole too low → degrades PM

```
p_int_LOAD  = gm_loadcas / C_int_LOAD  < 3·ω_c
p_int_OBIAS = gm_obcas   / C_int_OBIAS < 3·ω_c
    │
    ├── Reduce L_cas (already at L_min? skip)
    │     → smaller C_int → higher p_int
    │
    └── Increase gm_cas
        → Lower (gm/ID)_cas to 8 S/A
        ⚠️ Bigger Vdsat_cas → more headroom consumed
```

### 1st- or 2nd-stage gain low despite cascode

```
A_v1 = gm3 / (gds3 + gds_eq_LOAD)  below target
  OR
A_v2 = gm7 / (gds7 + gds_eq_OBIAS) below target
    │
    ├── gds_eq too high because main gds (gds1 or gds8) dominant
    │     → Increase L1 (or L5 for OUTPUT_BIAS) to reduce main gds
    │
    ├── gds_eq too high because cascode gm_gds low
    │     → Increase L_cas (longer cascode → higher gm_gds_cas)
    │     ⚠️ Verify p_int still > 3·ω_c
    │
    └── gds3 or gds7 (input-side) dominant
        → Standard gain fix: increase L3 or L7
```

### PM degraded by cascode internal pole

```
arctan(ω_c / p_int_*) eats > 15° of PM
    │
    └── Same fixes as "internal pole too low" above.
        If already at gm/ID = 8 and L_min, can't fix further:
          → Increase Cc (moves ω_c down, recovers PM)
          → Or accept the PM loss if still above target
```

### Headroom violation → consider lv_cascode

```
If output stage hits saturation limit at either end:
  Regular cascode headroom = vdsat_main + Vgs_cas (≈ Vth + 2·vdsat)
  LV cascode headroom      ≈ 2·vdsat (better)

Fix: rewire the netlist to the LV cascode pattern and add external bias.
Requires netlist change — may need user intervention.
```

---

## Fault Tree: Mismatch Too High

Only applies when Mismatch is an active target (user provided a number).

Mismatch is dominated by Pelgrom threshold mismatch: `σ(ΔVth) = A_VT / √(W × L)`.
Both the input pair and load pair contribute.

**Two fixes only — do not overcomplicate:**

```
Mismatch_3sigma > Mismatch_target
    │
    ├── Fix 1: Increase W and L (increase transistor area)
    │   Identify the pair with the smaller W×L product (diff pair or load).
    │   Increase both W and L for the bottleneck pair.
    │
    └── Fix 2: Reduce |Vdsat| (push toward weaker inversion)
        Higher gm/ID → lower id_w → wider W at same current → more area.
        Also reduces VGS, improving headroom for stacked devices.
```

---

## Output

After consulting the fault trees, apply the fix and output the **new adjusted
sizes** for the affected role(s). Re-derive all LUT parameters for the changed
role(s), then return to design-flow Step 6 for re-evaluation.
