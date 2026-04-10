# TCO Root-Cause Diagnosis Skill

## Purpose

When a TCO design fails to meet specs or has devices at invalid operating
points, this skill maps each failure to TCO-specific root causes and
recommends targeted fixes with Role-level reasoning.

## References

- Equations: `circuit-specific/tco/tco-equation.md`
- Approximations: `circuit-specific/tco/tco-approximation.md`

---

## Priority Order

Handle failures in this order:
1. **CRITICAL**: Any device not in saturation → fix OP first
2. **CRITICAL**: CMFB not locking → output CM level undefined
3. **NORMAL**: Spec failures → fix per fault tree below
4. **LOW**: Marginal specs (⚠️) → note for next iteration

---

## Fault Tree: Device Not Saturated

### M9 (TAIL) in linear region
```
Root cause: VDS_M9 < Vov_M9
  Mechanism: Input CM voltage too low → source of M1 pulled low →
             drain of M9 has insufficient VDS

Fix priority:
  1. Increase V_cm (if adjustable)
  2. Reduce Vov_M9 by increasing W9 (lower VGS at same current)
  3. Reduce I_tail (but check GBW and SR impact)
  4. Use wider-swing tail bias (cascode tail current source for better headroom)
  5. If VDD is too low → topology not feasible, switch to folded cascode
```

### M1 (DIFF_PAIR) in linear region
```
Root cause: VDS_M1 < Vov_M1
  Mechanism: Vbn_cas too low → source of M3 (= drain of M1) is too close to
             source of M1 → M1 enters triode

Fix:
  1. Increase Vbn_cas (raise gate voltage of NMOS cascode)
  2. Reduce Vov_M1 by increasing W1 (but check area and Cp2)
  3. Check: is Vbn_cas correctly set to Vov1 + VTN3 (wide-swing) or
     Vov1 + Vov3 + VTN3 (standard)?
```

### M3 (NCAS) in linear region
```
Root cause: VDS_M3 < Vov_M3
  Mechanism: Output voltage too low → drain of M3 pulled below
             safe operating point

Fix:
  1. This defines V_out,min. Check if V_out,min spec is too aggressive.
  2. Reduce Vov_M3 by increasing W3 (but check Cp2 impact on p2)
  3. Reduce Vov_M1 (same — both contribute to V_out,min)
  4. Relax output swing spec
```

### M7 (PCAS) in linear region
```
Root cause: VSD_M7 < |Vov_M7|
  Mechanism: Output voltage too high → drain of M7 pushed too close to VDD

Fix:
  1. This defines V_out,max. Check if V_out,max spec is too aggressive.
  2. Reduce |Vov_M7| by increasing W7 (but check Cp3)
  3. Reduce |Vov_M5| by increasing W5
  4. Relax output swing spec
```

### M5 (PLOAD) in linear region
```
Root cause: VSD_M5 < |Vov_M5|
  Mechanism: Vbp_cas set incorrectly → source of M7 (= drain of M5)
             too close to VDD

Fix:
  1. Adjust Vbp_cas to ensure M5 has sufficient VSD
  2. Reduce |Vov_M5| by increasing W5
  3. Check CMFB: if CMFB drives Vbp (M5 gate), it may be pushing
     the operating point incorrectly
```

---

## Fault Tree: CMFB Not Locking

```
CMFB fails to set output CM level
    │
    ├── CMFB gain too low
    │   → Increase CMFB amplifier gain (more current or larger devices)
    │
    ├── CMFB bandwidth too low
    │   → CMFB loop must be faster than signal path
    │   → Increase CMFB amplifier bandwidth
    │
    ├── V_cm_ref outside achievable range
    │   → Check: V_cm_ref must be within [V_out,min, V_out,max]
    │   → If not → adjust V_cm_ref or relax swing spec
    │
    ├── CMFB polarity wrong
    │   → Verify: increasing Voutp+Voutn should DECREASE the controlled
    │     current or voltage (negative feedback)
    │   → Common mistake: CMFB connected to wrong polarity → positive
    │     feedback → latch-up
    │
    └── DC latch-up
        → Multiple stable operating points exist
        → Add start-up circuit to force initial conditions
        → Ensure CMFB has authority over the full swing range
```

---

## Fault Tree: Gain Too Low

```
A0 < A0_target
    │
    ├── gm1 too low
    │   → Increase W1 or ID1
    │   → Or reduce gm/ID toward stronger inversion
    │   Note: gm1 affects GBW more than gain. Gain is dominated by Rout.
    │
    ├── Rout_ncas too low (gm3·ro3·ro1 limited)
    │   ├── gm3 too low → increase W3 or push M3 to stronger inversion
    │   ├── ro3 too low → increase L3
    │   ├── ro1 too low → increase L1 (most impactful for Rout_ncas)
    │   └── OP check: verify intrinsic gains A_i1, A_i3 from simulation
    │
    ├── Rout_pcas too low (gm7·ro7·ro5 limited)
    │   ├── gm7 too low → increase W7
    │   ├── ro7 too low → increase L7
    │   ├── ro5 too low → increase L5 (most impactful for Rout_pcas)
    │   └── OP check: verify A_i5, A_i7 from simulation
    │
    └── One cascode side dominates (parallel combination)
        → If Rout_ncas << Rout_pcas → NMOS side is bottleneck → fix L1, L3
        → If Rout_pcas << Rout_ncas → PMOS side is bottleneck → fix L5, L7
        → Check ratio from OP: if > 3× asymmetric → balance by adjusting L

Side effects of fixing gain:
  Increasing L → larger parasitics → GBW may decrease, p2/p3 may drop
  Increasing W → larger parasitics → p2/p3 may drop
  These tradeoffs must be reported to the user.
```

---

## Fault Tree: GBW Too Low

```
GBW < GBW_target
    │
    ├── gm1 too low [EQ §C]
    │   → Increase W1 (more gm at same ID)
    │   → Or increase ID1 (more current)
    │   → Or reduce gm/ID (stronger inversion → higher gm per µA)
    │
    ├── CL_total larger than expected
    │   → Check: is parasitic output capacitance significant?
    │   → Cdb3+Cgd3+Cdb7+Cgd7+C_cmfb may add 10–30% to CL
    │   → Include in CL_total and re-derive gm1
    │
    └── Non-dominant pole pulling effective BW down
        ├── p3 too low (PMOS cascode — most likely culprit)
        │   → Increase gm7: increase W7 or use shorter L7
        │   → Reduce Cp3: use shorter L5 (reduces Cdb5) — but hurts gain
        ├── p2 too low (NMOS cascode)
        │   → Increase gm3: increase W3 or use shorter L3
        │   → Reduce Cp2: use shorter L1 (reduces Cdb1) — but hurts gain
        └── Check: is SPICE GBW much lower than gm1/(2π·CL)?
            → If yes: parasitic pole separation assumption [APPROX S02] is violated
```

---

## Fault Tree: Phase Margin Too Low

```
PM < PM_target
    │
    ├── PMOS cascode pole p3 too close to ω_c [MOST COMMON for TCO]
    │   → Increase gm7 (increase W7 or push to stronger inversion)
    │   → Reduce Cp3: shorter L5 or L7 (but check gain impact)
    │   → Last resort: reduce GBW (lower gm1) to move ω_c away from p3
    │
    ├── NMOS cascode pole p2 too close to ω_c
    │   → Increase gm3 (increase W3)
    │   → Reduce Cp2: shorter L1 or L3 (but check gain impact)
    │
    ├── Both p2 and p3 contributing significantly
    │   → With two non-dominant poles each at ~20°, total excess phase = 40°
    │     → PM = 90° - 40° = 50° which may be insufficient
    │   → Need both poles at > 3× ω_c for comfortable 60° PM
    │
    ├── PM estimation was optimistic [APPROX S03]
    │   → Check: was arctan(x) ≈ x used with x > 0.47?
    │   → With two non-dominant poles, cumulative error is worse
    │   → Switch to exact arctan computation
    │
    └── Parasitic poles from CMFB or bias circuit
        → CMFB capacitors add to output capacitance → lower ω_c
        → CMFB loop may introduce additional poles near ω_c
        → Check CMFB loop separately for stability
```

---

## Fault Tree: Noise Too High

```
Noise > target
    │
    ├── 1/f noise dominated (noise at low frequency)
    │   → Increase W1·L1 (reduces Kf/(Cox·W·L) term)
    │   → Consider PMOS input pair if process allows (lower Kf for PMOS)
    │   → Check PMOS load contribution: if gm5/gm1 > 0.5,
    │     load noise is significant → increase L5 (reduces gm5 at same ID)
    │     or reduce W5 to decrease gm5 (ensure M5 still in saturation)
    │
    ├── Thermal noise dominated (noise at high frequency)
    │   → Increase gm1 (increase W1 or ID1)
    │   → Reduce load noise: minimize gm5/gm1 ratio
    │     (make PMOS load weaker relative to input pair)
    │   → TCO advantage: no folding branch noise. If noise is still too
    │     high, the topology is not the problem — need more gm1.
    │
    └── CMFB contributing noise
        → Resistive CMFB: resistors inject thermal noise directly at output
        → SC CMFB: kT/C noise sampled onto output
        → Solution: increase CMFB capacitor size (for SC) or resistance (for resistive)
```

---

## Fault Tree: Slew Rate Too Low

```
SR < SR_target
    │
    ├── I_tail too low
    │   → SR = I_tail / CL_total → increase I_tail
    │   → Side effect: more power
    │   → Alternative: reduce CL if possible (application-dependent)
    │
    └── CMFB cannot track during slewing
        → During large-signal transients, output CM shifts temporarily
        → If CMFB is too slow, it corrects late → effective SR reduced
        → Increase CMFB bandwidth or use faster CMFB topology

Note: Unlike TSM, TCO has symmetric SR by topology. If simulation
shows asymmetric SR, check CMFB behavior during large-signal transients.
```

---

## Fault Tree: Output Swing Insufficient

```
V_swing < V_swing_target
    │
    ├── Vov of stacked devices too large
    │   → For each device in the stack (M1, M3, M5, M7):
    │     compute Vov = 2·ID/gm (or from LUT)
    │   → Identify the device with largest Vov → increase its W
    │     (larger W → lower Vov at same ID)
    │   → Push toward higher gm/ID (weaker inversion) but watch headroom
    │
    ├── Too many devices stacked
    │   → This is the fundamental TCO limitation: 4 Vov's in the stack
    │   → If VDD is low, consider wide-swing cascode bias (saves 1 Vov)
    │   → Or switch to folded cascode (only 2 Vov's in output stack)
    │
    └── Bias voltages sub-optimal
        → Vbn_cas too high → wastes headroom on M1's VDS
        → Vbp_cas too low → wastes headroom on M5's VSD
        → Use wide-swing (Sooch) cascode biasing to minimize wasted headroom
```

---

## Fault Tree: Power Too High

```
P > P_max
    │
    ├── I_tail too high
    │   → Driven by GBW requirement: gm1 = 2π × GBW × CL
    │   → At fixed gm/ID: ID = gm1 / (gm/ID)
    │   → Increase gm/ID (weaker inversion → same gm with less current)
    │   → But check: higher gm/ID → larger Vov... no, LOWER Vov
    │     (weak inversion has highest gm/ID and lowest Vov)
    │   → Or relax GBW spec
    │
    └── TCO is already the most power-efficient topology
        → If power is still too high, the spec set is fundamentally
          demanding more gm than the power budget allows
        → Trade: relax GBW, or relax noise, or accept higher power
        → There is no more efficient single-stage topology
```

---

## TCO-Specific Diagnosis: Gain vs Speed Tradeoff

This is the most common tension in TCO design. Unlike TSM (where gain
and speed use separate stages), TCO must achieve BOTH with the same devices.

```
TRADEOFF: Need more gain but GBW is marginal
    │
    ├── Increase L for gain → parasitics increase → GBW/PM degrade
    │   → Quantify: how much L increase is needed? Check LUT.
    │   → If gain gap is < 6 dB: try L increase + slight gm1 boost
    │   → If gain gap is > 6 dB: add gain boosting or switch to two-stage
    │
    ├── Gain boosting (recommended for > 60 dB gain at high GBW)
    │   → Add auxiliary amplifiers at NMOS and PMOS cascode nodes
    │   → Rout_boosted = A_aux × gm_cas × ro_cas × ro_main
    │   → Gain increases by A_aux factor (typically 20–40 dB additional)
    │   → Requires careful design of auxiliary amplifier for stability
    │   → Auxiliary amplifier introduces additional poles → may affect PM
    │
    └── Switch to two-stage Miller (TSM) if:
        → Gain requirement > 70 dB AND GBW < 50 MHz
        → Output swing requirement is wide (> VDD - 4×Vov)
        → Need unity-gain feedback
```

---

## Output Format

For each failing spec, present a diagnosis block:

```
DIAGNOSIS: PM = 52° [target ≥ 60°] ❌
  Root cause  : PMOS cascode pole p3 too close to ω_c
                p3 ≈ 1.8 GHz, ω_c ≈ 628 MHz → ratio = 2.9 (need > 3.0)
                Combined with p2 = 5.2 GHz → total phase loss = 38°
  Affected Role : PCAS (M7)
  Fix         : Increase W7 from 20µm to 28µm → gm7 increases ~18%
                Expected: p3 increases to ~2.1 GHz (net capacitance also increases
                but gm7 grows faster), PM → ~62°
  Side effects : Cp3 increases slightly → verify net p3 improvement
                 |Vov7| decreases → output swing improves slightly
  Priority    : 1 (fix first)

DIAGNOSIS: A0 = 48 dB [target ≥ 50 dB] ⚠️
  Root cause  : PMOS cascode impedance Rout_pcas is bottleneck
                Rout_pcas = 1.2 MΩ vs Rout_ncas = 3.5 MΩ
                (PMOS side is 3× weaker → dominates the parallel combination)
  Affected Role : PLOAD (M5)
  Fix         : Increase L5 from 0.5µm to 0.8µm → ro5 improves ~60%
                Expected: A0 → ~52 dB
  Side effects : Cp3 increases (larger Cdb5) → recheck p3 and PM
  Priority    : 2 (fix after PM)
```

After presenting all diagnoses, hand back to Circuit Design Flow Skill
for the next sizing iteration.
