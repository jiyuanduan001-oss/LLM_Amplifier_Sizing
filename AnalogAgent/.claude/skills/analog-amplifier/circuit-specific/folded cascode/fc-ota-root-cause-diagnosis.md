# FC-OTA Root-Cause Diagnosis Skill

## Purpose

When an FC-OTA design fails to meet specs or has devices at invalid OPs,
this skill maps failures to FC-specific root causes and recommends fixes.

## References

- Equations: `circuit-specific/fc-ota/fc-ota-equation.md`
- Approximations: `circuit-specific/fc-ota/fc-ota-approximation.md`

---

## Priority Order

1. **CRITICAL**: Device not in saturation → fix OP first
2. **HIGH**: CMFB not converged / output CM wrong → fix CMFB
3. **NORMAL**: Spec failures → fix per fault tree
4. **LOW**: Marginal specs → note for next iteration

---

## Fault Tree: Device Not Saturated

### Cascode device (M3 or M7) in linear region

```
Root cause: insufficient VDS across cascode device
  Mechanism: output voltage at extreme of swing
    → V_out too low: M3 loses VDS (V_out < Vov_M5 + Vov_M3)
    → V_out too high: M7 loses VDS (V_out > VDD - |Vov_M9| - |Vov_M7|)

Fix:
  1. Check output CM (Voc1) — is CMFB working correctly?
  2. Reduce Vov of cascode + CS devices (higher gm/ID → less headroom consumed)
  3. Use wide-swing cascode biasing to reduce minimum VDS
  4. Relax output swing spec if possible
```

### Current source (M5 or M9) in linear region

```
Root cause: cascode gate bias squeezing VDS of CS device
  Mechanism: Vb_casc set too aggressively, not leaving enough VDS for CS

Fix:
  1. Verify bias voltage generation — Vb_n_cs, Vb_n_casc consistency
  2. Increase VDS margin by adjusting Vov_casc (higher Vov → less VGS → more VDS for CS)
  3. Use wide-swing cascode bias circuit
```

### Input pair (M1) in linear region

```
Root cause: V_cm too low or fold node voltage wrong
  Mechanism: tail node voltage = V_cm - Vgs_M1, fold node needs to accommodate M3
    → If V_cm is near VSS and Vov_M3 > Vth_M1: no room for M1 drain

Fix:
  1. Check V_cm range constraint [EQ §G]
  2. Reduce Vov_M3 (but check fold pole speed)
  3. Increase V_cm operating point if application allows
```

### TAIL (M_tail) in linear region

```
Root cause: same as 5T OTA — VDS compressed
  Mechanism: V_cm too low → tail node voltage too low

Fix:
  1. Increase L_TAIL (raises Vth, lowers VGS, gives more VDS room)
  2. Reduce I_tail (but check GBW impact)
  3. Raise V_cm,min spec
```

---

## Fault Tree: CMFB Not Working

```
Output CM wrong (Voc1 ≠ Vref) or unstable
    │
    ├── CMFB loop gain too low
    │   → Increase gm of CMFB error amplifier
    │   → Increase R_out of error amp
    │
    ├── CMFB loop unstable (oscillation visible in transient)
    │   → CMFB loop has too many poles near its UGB
    │   → Add compensation cap at CMFB output
    │   → Reduce CMFB UGB (but check CM settling time)
    │
    ├── CMFB detection loading the output
    │   → For resistive CMFB: R_detect too small → reduce DM gain
    │     → Increase R_detect (but check CM detection speed)
    │   → For SC-CMFB: charge injection from switches
    │     → Use bottom-plate sampling, larger C2
    │
    ├── CMFB reference voltage wrong
    │   → Vref should be (V_out,min + V_out,max)/2
    │   → If Vref is outside the output swing range, CMFB can't lock
    │
    └── CMFB control point wrong
        → Verify that CMFB output is connected to the correct current source
        → Check polarity: does increasing Vcm_ctrl INCREASE or DECREASE output CM?
        → Negative feedback required — inversion count must be odd
```

---

## Fault Tree: Gain Too Low

```
A0 < A0_target
    │
    ├── R_out_n too low (NMOS cascode stack impedance insufficient)
    │   ├── gm_gds of M3 (NMOS_CASC) too low → increase L3
    │   ├── gm_gds of M5 (NMOS_CS) too low → increase L5
    │   └── Check: is M3 or M5 the bottleneck? (compare gm_gds from OP)
    │
    ├── R_out_p too low (PMOS cascode stack impedance insufficient)
    │   ├── gm_gds of M7 (PMOS_CASC) too low → increase L7
    │   ├── gm_gds of M9 (PMOS_CS) too low → increase L9
    │   └── Check: is M7 or M9 the bottleneck?
    │
    ├── gm1 too low (unlikely to cause gain issue in FC, but check)
    │   → gm enters only linearly in A0 = gm1 × R_out
    │
    └── R_out_n and R_out_p severely unbalanced
        → The weaker stack dominates (parallel combination)
        → Fix the weaker stack first — balancing them doubles the effective R_out
```

---

## Fault Tree: GBW Too Low

```
GBW < GBW_target
    │
    ├── gm1 too low [EQ §C: GBW = gm1/(2π·CL)]
    │   → Increase W1 or I1 (increase gm)
    │   → Reduce gm/ID toward stronger inversion
    │
    ├── Effective CL larger than assumed [APPROX S05]
    │   → Parasitic output caps (Cdb3+Cdb7+Cgd3+Cgd7) significant
    │   → CMFB loading adds capacitance at output
    │   → Recompute GBW with true C_out
    │
    └── Folding pole pulling effective BW down [APPROX S04]
        → fp_fold too close to GBW
        → Check: is SPICE GBW << gm1/(2π·CL)?
        → If yes: fp_fold is limiting → see PM fault tree
```

---

## Fault Tree: Phase Margin Too Low

```
PM < PM_target
    │
    ├── Folding pole fp_fold too close to GBW [EQ §B]
    │   ├── gm3 too low → increase Vov_M3 (lower gm/ID for M3)
    │   │   ⚠️ But Vov_M3 < Vth_M1 required for CM range!
    │   ├── C_fold too large → dominated by Cgs3 + Cdb1
    │   │   → Reduce W1 (less Cdb1, but check GBW)
    │   │   → Reduce L3 (less Cgs3, but check gain)
    │   └── fp_fold = gm3/C_fold — BOTH knobs matter
    │
    ├── PMOS cascode pole too close to GBW
    │   → Increase gm7 (lower gm/ID for M7)
    │   → Reduce L7 (less Cgs7, but check gain)
    │
    ├── CMFB loop introducing extra poles near DM GBW
    │   → CMFB bandwidth too high → poles interact with DM loop
    │   → Reduce CMFB UGB to (1/3)× DM UGB
    │
    └── Parasitic poles from bias circuit or routing
        → Extract parasitics and re-simulate

⚠️ The FC-OTA starts at PM = 90° (no RHP zero). If PM < 60°,
the parasitic poles are much too close to GBW — either GBW is too
aggressive or cascode devices are too slow.
```

---

## Fault Tree: Noise Too High

```
Noise > target
    │
    ├── Current source noise dominates [EQ §E]
    │   ⚠️ THIS IS THE #1 FC-OTA NOISE ISSUE
    │   ├── gm5 too large → Vov_M5 too low
    │   │   → INCREASE Vov_M5 (lower gm/ID → stronger inversion)
    │   │   → Tradeoff: more Vov → less output swing
    │   ├── gm9 too large → Vov_M9 too low
    │   │   → Same: increase Vov_M9
    │   └── Check ratio: gm5/gm1 and gm9/gm1
    │       → Both should be < 0.5 for current sources to contribute < 50% of noise
    │       → If gm5/gm1 > 1: current source noise exceeds input pair noise!
    │
    ├── Input pair thermal noise too high
    │   → gm1 too low → increase gm1 (more current or lower gm/ID)
    │
    ├── Input pair 1/f noise too high
    │   → W1·L1 too small → increase input pair area
    │   → Use PMOS input pair if process has lower Kf_p
    │
    └── Current source 1/f noise
        → Increase L5, L9 (reduces Kf/(Cox·W·L))
        → Long L for current sources is cheap (not speed-critical)
```

---

## Fault Tree: Output Swing Insufficient

```
V_swing < target
    │
    ├── Cascode stack headroom too large
    │   ├── Vov_M3 + Vov_M5 too large (bottom) → reduce Vov (higher gm/ID)
    │   ├── |Vov_M7| + |Vov_M9| too large (top) → reduce |Vov| (higher gm/ID)
    │   └── BUT: reducing Vov increases noise (gm of CS devices increases)
    │
    ├── Wide-swing cascode biasing not used
    │   → Implement Sooch cascode bias to reduce min VDS per stack from
    │     Vov_casc + Vov_cs to max(Vov_casc, Vov_cs) + margin
    │
    └── VDD too low for FC-OTA topology
        → For VDD < 1V: FC-OTA becomes very difficult (4×Vov ≈ 0.4–0.6V)
        → Consider: gain-boosted telescopic, inverter-based, or two-stage
```

---

## Fault Tree: Slew Rate Too Low

```
SR < SR_target
    │
    ├── I1 too low [EQ §D: SR = I1/CL]
    │   → Increase I_tail (= 2×I1)
    │   → But: increases power and changes gm1 (affects GBW)
    │   → Alternative: reduce gm/ID of input pair (more current per gm)
    │
    └── Asymmetric slewing
        → Check both SR+ and SR-
        → If SR- >> SR+: I_fold > I1, positive slew is limiting
        → Fix: increase I_tail or rebalance I_fold/I1 ratio
```

---

## Fault Tree: CMRR/PSRR Too Low

```
CMRR < target [EQ §F]
    → Increase L_TAIL (primary knob for CMRR)
    → Verify CMFB loop gain is adequate
    → Check for mismatch in M5a/M5b or M9a/M9b

PSRR⁺ < target
    → Increase L9 and/or L7 (PMOS stack)
    → Verify bias circuit is not coupling supply noise

PSRR⁻ < target
    → Increase L5 and/or L3 (NMOS stack)
```

---

## Interdependence Map (FC-Specific)

| Fix                    | Helps           | May hurt              | FC-specific note |
|-----------------------|-----------------|----------------------|------------------|
| Increase L (CASC)      | A0, PSRR        | p_fold↓ → PM↓, speed | Gain-speed tradeoff at fold node |
| Increase L (CS)        | A0, noise (1/f), PSRR | Area, Vov changes | Always beneficial for CS |
| Increase L (INPUT)     | Noise (1/f)     | GBW (parasitic↑)     | Trade noise for speed |
| Increase L (TAIL)      | CMRR            | Area                 | Always beneficial |
| Increase Vov (CASC)    | Speed (p_fold↑) | Swing, CM range      | Speed vs swing tradeoff |
| Increase Vov (CS)      | Noise↓          | Swing                | Noise vs swing tradeoff |
| Decrease Vov (INPUT)   | Noise↓, gm/ID↑  | Speed (fT↓)          | Noise vs speed |
| Increase I_fold        | Margin, CMRR    | Power, noise         | More current = more CS noise |
| Increase I_tail        | gm1, GBW, SR    | Power                | Direct power-performance |

---

## Output Format

```
DIAGNOSIS: PM = 52° [target ≥ 60°] ❌
  Root cause  : Folding pole fp_fold too close to GBW
                fp_fold ≈ 75 MHz, GBW = 30 MHz → ratio = 2.5 (need > 3)
  Affected Role : NMOS_CASC (M3a, M3b)
  Fix         : Reduce gm/ID of M3 from 10 to 7 S/A
                → Increases Vov_M3 from 170mV to 240mV
                → gm3/Cgs3 improves → fp_fold ≈ 120 MHz → ratio = 4.0
  Side effects : Vov_M3 still < Vth_M1 (≈0.4V) ✅
                 Output swing reduced by 70mV (check V_swing spec)
  Priority    : 1

DIAGNOSIS: Noise @1kHz = 45 nV/√Hz [target ≤ 30 nV/√Hz] ❌
  Root cause  : gm5/gm1 = 1.1 → NMOS_CS noise exceeds input pair noise
                M5 at gm/ID=12 while M1 at gm/ID=14
  Affected Role : NMOS_CS (M5a, M5b) + PMOS_CS (M9a, M9b)
  Fix         : Reduce gm/ID of M5 to 6 S/A and M9 to 6 S/A
                → gm5/gm1 drops to 0.45 → CS noise contribution halved
  Side effects : Vov_M5 increases → output swing reduced by ~100mV
                 Check V_swing spec
  Priority    : 2
```
