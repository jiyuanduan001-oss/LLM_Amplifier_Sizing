# 5T OTA Root-Cause Diagnosis

## Purpose

When a 5T OTA design fails to meet specs (analytically or in simulation),
this skill maps each failure to its root cause and recommends a fix.

## Rules

1. Follow the priority order: fix saturation issues before spec failures.


---

## Priority Order

1. **CRITICAL**: Any device not in saturation → fix OP first
2. **NORMAL**: Spec failures → fix per fault tree below

---

## Fault Tree: Device Not Saturated

### M3 (TAIL) in linear region

Most common failure. VDS_M3 = V_cm - VGS_M1 - VSS must exceed Vov_M3.
Two aspects to fix: reduce VGS_M1 or reduce Vov_M3.

```
Root cause: VDS_M3 < Vov_M3

Fix from VGS_M1 side (increase VDS_M3):
  1. Increase W/L of DIFF_PAIR → lowers VGS_M1 at same ID
     ⚠️ Side effect: larger input pair, more parasitic cap
  2. Reduce I_tail → lower VGS_M1
     ⚠️ Side effect: reduces gm1 → GBW drops

Fix from Vov_M3 side (relax saturation requirement):
  1. Increase W of M3 (keep L3 reasonable, not small) → reduces Vov_M3
     This means increasing gm/ID of TAIL toward weaker inversion.
     ⚠️ Side effect: larger device area
```

### M1 (DIFF_PAIR) or M5 (LOAD) leaving saturation

At the DC operating point, M1 or M5 leaving saturation is almost always
caused by M3 not working properly — fix M3 first (see above). When M3
is correctly saturated, Vout settles near VCM and both M1/M5 have
adequate VDS margin.

Note: M6 is diode-connected → always saturated.

---

## Fault Tree: Gain Too Low

```
A0 = gm1 / (gds1 + gds5) < A0_target
    │
    ├── gds1 too large → increase L1
    │   ⚠️ Side effect: larger Cgs1, Cgd1 → may affect GBW and mirror cap
    │
    ├── gds5 too large → increase L5
    │   ⚠️ Side effect: larger Cgs5 → lower fp2 → PM may degrade
    │
    └── Both gds1 and gds5 need reduction → increase both L1 and L5
```

---

## Fault Tree: GBW Too Low

```
GBW = gm1 / (2π × C_out) < GBW_target
    │
    ├── gm1 too low
    │   → Increase I_tail (raises gm1 = gm/ID × I_tail/2)
    │   ⚠️ Side effect: more power
    │
    ├── fT too low (device not fast enough)
    │   → Decrease gm/ID (stronger inversion → higher fT)
    │   ⚠️ Side effect: less gm per current → need more power
    │
    └── C_out too large (parasitic caps significant)
        → This is a post-simulation diagnosis (Cdb not known pre-sim)
        → Reduce device size if possible (shorter L smaller W)
        ⚠️ Side effect: lower gain 
        → Accept that analytical GBW overestimates when devices are wide
```

---

## Fault Tree: Phase Margin Too Low

The 5T OTA rarely has PM problems. It starts at 90° (no RHP zero, no Miller
cap), and the mirror pole-zero doublet (fz2 = 2×fp2) means the zero always
partially recovers phase lost to the pole. PM below 60° is unlikely under
normal sizing conditions.

---

## Fault Tree: Slew Rate Too Low

```
SR = I_tail / CL < SR_target
    │
    └── Increase I_tail
        → I_tail = 2 × ID1, so ID1 must increase
        → At fixed gm/ID: gm1 also increases → GBW increases
        ⚠️ Side effect: more power, larger devices
```

---

## Fault Tree: Output Swing Too Low

```
V_swing = VDD - Vov_M1 - |Vov_M5| < Swing_target
    │
    ├── Vov_M1 too large → increase gm/ID of DIFF_PAIR (weaker inversion)
    │   ⚠️ Side effect: lower ft, larger W
    │
    └── |Vov_M5| too large → increase gm/ID of LOAD (weaker inversion)
        ⚠️ Side effect: lower ft, larger W
```

---

## Fault Tree: CMRR Too Low

```
CMRR = 2·gm1·gm5·Rout·ro3 < CMRR_target
    │
    ├── ro3 too low (gds3 too high) → increase L3
    │   This is the primary fix. TAIL is not speed-critical.
    │
    └── A0 too low → fix gain first (see gain fault tree)
```

---

## Fault Tree: PSRR Too Low

```
PSRR⁺ ≈ A0 < PSRR⁺_target
    → PSRR⁺ is limited by DC gain. Fix gain (see gain fault tree).

PSRR⁻ ≈ CMRR < PSRR⁻_target
    → Same as CMRR. Increase L3 for higher ro3.
```

---

## Fault Tree: Power Too High

```
P = (I_tail + I_bias) × VDD > P_target
    │
    └── Reduce I_tail
        → To maintain gm1: increase gm/ID (weaker inversion, less current)
        ⚠️ Side effect: higher gm/ID → lower ft, larger W, lower SR
```

---

## Fault Tree: Noise Too High

Noise parameters (Kf, Cox) are not in the LUT. Noise is best evaluated
by the simulator. For pre-simulation guidance:

```
Integrated noise too high
    │
    ├── Thermal noise dominated
    │   → Increase gm1 (more current or lower gm/ID)
    │   → gm5/gm1 ratio also matters — minimize gm5 relative to gm1
    │
    └── 1/f noise dominated
        → Increase W1 × L1 (more input pair area)
```

---

## Output

After consulting the fault trees, apply the fix and output the **new adjusted
sizes** for the affected role(s). Re-derive all LUT parameters for the changed
role(s), then return to design-flow Step 4 for re-evaluation.
