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

## ⚠️ Power Utilization — Read Before Any Fault Tree

Before diving into individual fault trees, check whether the design is
using its power budget. If power is well below target while specs are
failing, consider increasing I_tail first — it improves GBW, noise,
and CMRR simultaneously (gm scales with current at fixed gm/ID).

---

## Fault Tree: Device Not Saturated

### M3 (TAIL) in linear region

Most common failure. VDS_M3 = V_cm - VGS_M1 - VSS must exceed Vdsat_M3.
Two aspects to fix: reduce VGS_M1 or reduce Vdsat_M3.

```
Root cause: VDS_M3 < Vdsat_M3

Fix from VGS_M1 side (increase VDS_M3):
  1. Increase W/L of DIFF_PAIR → lowers VGS_M1 at same ID
     ⚠️ Side effect: larger input pair, more parasitic cap
  2. Reduce I_tail → lower VGS_M1
     ⚠️ Side effect: reduces gm1 → GBW drops

Fix from Vdsat_M3 side (relax saturation requirement):
  1. Increase W of M3 (keep L3 reasonable, not small) → reduces Vdsat_M3
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

## Fault Tree: Tail Current Source Headroom

The TAIL (M3) saturation margin is a cross-cutting concern: when M3
operates near the saturation boundary, its effective gds rises steeply,
degrading **multiple specs simultaneously** — CMRR, PSRR⁻, GBW (via
mirror current loss), and indirectly noise and SR. If more than one of
these specs fails at the same time, check M3 headroom first.

```
M3 saturation margin too low  (margin < 100 mV, or multiple specs degraded)
    │
    ├── Reduce Vdsat of BIAS_GEN / TAIL
    │   Push gm/ID of BIAS_GEN (M4) toward weaker inversion.
    │   Since M4 and M3 share the same per-instance W/L, lowering
    │   Vdsat on M4 lowers Vdsat on M3 simultaneously.
    │   This is the most direct fix — it does not change VGS_M1 or
    │   the voltage stack above M3.
    │
    ├── Reduce VGS of DIFF_PAIR
    │   Push gm/ID of DIFF_PAIR toward weaker inversion.
    │   VDS_M3 = V_cm − VGS_M1, so any reduction in VGS_M1 adds
    │   directly to M3 headroom.
    │   ⚠️ Side effect: wider input pair, more parasitic cap, lower ft.
    │
    ├── Increase L4 (= L3) for higher intrinsic ro per device
    │   Higher ro improves small-signal tail impedance even at the
    │   same saturation margin.
    │   ⚠️ Side effect: W4 shrinks, may force M4_M > 1
    │   (discretization can double the effective mirror ratio).
    │
    └── Increase I_bias to reduce mirror ratio
        Lower M3_M means less VDS compression from finite ro.
        Only if the spec form allows it (I_bias is often constrained).

Cross-references:
  CMRR depends on ro_eq_TAIL — see "CMRR Too Low"
  PSRR⁻ scales with ro_eq_TAIL — see "PSRR Too Low"
  GBW shortfall from mirror current loss — see "GBW Too Low"
```

⚠️ **Analytical overestimate warning:** The small-signal CMRR and
PSRR⁻ formulas use gds3 as a constant, but near the saturation
boundary gds changes steeply with VDS. The analytical prediction can
overestimate CMRR by 15–20 dB when M3 margin is below 100 mV. Always
verify with SPICE, and if the analytical model predicts comfortable
CMRR margin but SPICE fails, check M3 headroom.

---

## Fault Tree: Gain Too Low

```
A0 = gm1 / (gds1 + gds_eq_LOAD) < A0_target
    │
    ├── gds1 too large → increase L1
    │   ⚠️ Side effect: larger Cgs1, Cgd1 → may affect GBW and mirror cap
    │
    ├── gds_eq_LOAD too large → increase L5 (or L_cas for cascode)
    │   ⚠️ Side effect: larger Cgs5 → lower fp2 → PM may degrade
    │
    └── Both gds1 and gds_eq_LOAD need reduction → increase both L1 and L5
```

---

## Fault Tree: GBW Too Low

```
GBW = gm1 / (2π × C1) < GBW_target
    │
    ├── gm1 too low
    │   → Increase I_tail (raises gm1 = gm/ID × I_tail/2)
    │   ⚠️ Side effect: more power
    │
    └── C1 too large (parasitic caps significant)
        → This is a post-simulation diagnosis (Cdb not known pre-sim)
        → Reduce device size if possible (shorter L, smaller W)
        ⚠️ Side effect: lower gain
        → Accept that analytical GBW overestimates when devices are wide
```

---

## Fault Tree: Phase Margin Too Low

The 5T OTA rarely has PM problems. It starts at 90° with no Miller cap,
and the mirror pole-zero doublet (fz ≈ 2×fp2) means the zero always
partially recovers phase lost to the pole. There is an RHP zero at
`fz_rhp = gm1/(2π·Cgd1)` from diff-pair Cgd feedforward, but it is
near ft and typically negligible. PM below 60° is unlikely under normal
sizing conditions.

---

## Fault Tree: Slew Rate Too Low

```
SR = I_tail / (CL + Cdb1 + Cdb5 + Cgd5) < SR_target
    │
    └── Increase I_tail
        → I_tail = 2 × ID1, so ID1 must increase
        → At fixed gm/ID: gm1 also increases → GBW increases
        ⚠️ Side effect: more power, larger devices
```

---

## Fault Tree: Output Swing Too Low

```
V_swing = VDD - V_headroom_LOAD - V_headroom_TAIL - Vdsat_M1 < Swing_target
    │
    ├── Vdsat_M1 too large → increase gm/ID of DIFF_PAIR (weaker inversion)
    │   ⚠️ Side effect: lower ft, larger W
    │
    ├── V_headroom_LOAD too large → increase gm/ID of LOAD (weaker inversion)
    │   ⚠️ Side effect: lower ft, larger W
    │   For cascode load: headroom = Vgs + vdsat; consider lv_cascode
    │
    └── V_headroom_TAIL too large → increase gm/ID of TAIL (weaker inversion)
        ⚠️ Side effect: larger device area
```

---

## Fault Tree: CMRR Too Low

```
CMRR ≈ 2·gm1·gm5·Rout·ro_eq_TAIL < CMRR_target
    │
    ├── ro_eq_TAIL too low (most common root cause)
    │   → First check M3 saturation margin.
    │     If margin < 100 mV or multiple specs (CMRR + PSRR⁻ + GBW)
    │     fail together → see "Tail Current Source Headroom" fault tree.
    │   → If M3 is well saturated: increase L3 (= L4) or add cascode to TAIL.
    │     TAIL is not speed-critical.
    │
    └── A0 too low → fix gain first (see gain fault tree)
```

---

## Fault Tree: PSRR Too Low

```
PSRR⁺ ≈ A0 < PSRR⁺_target
    → PSRR⁺ is limited by DC gain. Fix gain (see gain fault tree).

PSRR⁻ ≈ CMRR < PSRR⁻_target
    → Same root cause as CMRR — dominated by tail impedance.
    → If M3 margin < 100 mV or CMRR also fails
      → see "Tail Current Source Headroom" fault tree.
    → If M3 well saturated: increase L3 (= L4) for higher ro_eq_TAIL.
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

## Fault Tree: Power Under-Utilized

When power is well below the budget but other specs (GBW, noise, SR)
are failing, the design is not spending enough of the available power.
Unused power margin should be redirected to fix failing specs:

```
P << P_target AND other specs failing
    │
    ├── GBW or noise limited
    │   → Increase I_tail (raises gm1 for GBW; lowers thermal noise)
    │
    └── SR limited
        → Increase I_tail (SR = I_tail / C1 for the 5T OTA)
        → This directly uses power headroom for a concrete spec benefit
```

---

## Fault Tree: Noise Too High

Noise parameters (Kf, Cox) are not in the LUT. Noise is best evaluated
by the simulator. For pre-simulation guidance:

```
Integrated noise too high
    │
    ├── Thermal noise dominated
    │   → Increase gm1 (more current or larger gm/ID)
    │   → gm5/gm1 ratio also matters — minimize gm5 relative to gm1
    │
    └── 1/f noise dominated
        → Increase W1 × L1 (more input pair area)
```

---

## Fault Tree: Cascode / LV Cascode Sub-Block Issues

Applies only when LOAD or TAIL uses `sub_block_type = "cascode"` or
`"lv_cascode"` (see `general/knowledge/mirror-load-structures.md`).

### Internal pole too low → degrades PM

```
p_int = gm_cas / C_int  <  3 × ω_c
    │
    ├── Reduce L_cas (already at L_min? skip)
    │     → smaller C_int → higher p_int
    │     ⚠️ Side effect: slightly lower gm/gds of cascode → tiny gain loss
    │
    └── Increase gm_cas
        → Lower (gm/ID)_cas to 8 S/A (stronger inversion)
        ⚠️ Side effect: bigger Vdsat_cas → more headroom consumed
```

### Gain too low despite cascode

```
A0 = gm1 / (gds1 + gds_eq_LOAD) below target
    │
    ├── gds_eq_LOAD dominated by cascode (shouldn't happen; verify numbers)
    │     → Increase L_cas (longer cascode → higher gm_gds_cas)
    │     ⚠️ Verify p_int still > 3·ω_c after change
    │
    ├── gds_eq_LOAD dominated by main (gds5 × gds_cas / gm_cas ≈ gds5/gm_gds_cas)
    │     → Increase L5 (longer main → smaller gds5)
    │
    └── gds1 dominant → raise DIFF_PAIR L1 (standard gain fix)
```

### Headroom violation with regular cascode → consider lv_cascode

```
V_out hits V_headroom limit (output saturates)
  Regular cascode headroom = vdsat_main + Vgs_cas (≈ Vth + 2·vdsat)
  LV cascode headroom      ≈ 2·vdsat (much better)

Fix: rewire the netlist to the LV cascode pattern
  (M_main.gate = M_cas.drain, M_cas.gate = external bias port)
  AND add the external bias to the testbench.
This is a NETLIST change — may require user intervention.
```

---

## Fault Tree: Mismatch Too High

Only applies when Mismatch is an active target (user provided a number).

Mismatch is dominated by Pelgrom threshold mismatch: `σ(ΔVth) = A_VT / √(W × L)`.
Both the input pair (M1/M2) and load pair (M5/M6) contribute.

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
role(s), then return to design-flow Step 4 for re-evaluation.
