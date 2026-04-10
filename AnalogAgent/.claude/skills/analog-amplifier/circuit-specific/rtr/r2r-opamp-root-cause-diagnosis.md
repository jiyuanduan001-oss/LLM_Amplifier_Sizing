# R2R Opamp Root-Cause Diagnosis Skill

## Purpose

When the R2R two-stage opamp fails to meet specs or has devices at invalid
operating points, this skill maps failures to topology-specific root causes
and recommends fixes.

## References

- Equations: `circuit-specific/r2r-opamp/r2r-opamp-equation.md`
- Approximations: `circuit-specific/r2r-opamp/r2r-opamp-approximation.md`

---

## Priority Order

1. **CRITICAL**: Device not in saturation → fix OP first
2. **CRITICAL**: gm-control malfunction (positive feedback active) → fix gm circuit
3. **HIGH**: Class-AB quiescent point wrong → fix translinear loop
4. **NORMAL**: Spec failures → fix per fault tree
5. **LOW**: Marginal specs → note for next iteration

---

## Fault Tree: gm Not Constant Across CM Range

```
gm variation > 15%
    │
    ├── 3× mirror ratio inaccurate
    │   ├── W/L mismatch in M6-M7 or M9-M10 → verify exact 1:3 ratio
    │   ├── L too short → CLM error in mirror → increase L of mirror devices
    │   └── Vds mismatch between ref and copy → add cascode to mirrors
    │
    ├── Current switches not fully ON/OFF in their respective regions
    │   ├── M5 (N-switch) not fully conducting → increase W_M5 or check gate bias
    │   ├── M8 (P-switch) not fully conducting → increase W_M8
    │   └── Transition too abrupt or too gradual → adjust switch W/L
    │
    ├── µN/µP ratio deviates from nominal
    │   ├── Process corner: check SS/FF/SF/FS → gm varies extra ±7.5% per ±15% µ variation
    │   └── FIX: increase (W/L) of the pair with lower µ to compensate
    │       (requires process-aware sizing or trimming)
    │
    ├── Positive feedback loop active at low VDD (M5-M10 loop)
    │   ├── VDD < 2.9V and protection circuit M29-M31 not working
    │   │   → Verify M29-M30 differential pair detects supply correctly
    │   │   → Verify M31 properly disables M8 at low VDD
    │   └── FIX: ensure M8 is OFF at supply voltages where both switches would conduct
    │
    └── Dead zone in CM range (neither pair active)
        → VDD < V_sup,min = Vgsp + Vgsn + 2·Vdsat
        → FIX: reduce Vov of input pairs (moderate/weak inversion)
                or accept reduced CM range
```

---

## Fault Tree: Class-AB Quiescent Current Wrong

```
Iq of output transistors incorrect
    │
    ├── Translinear loop not balanced
    │   ├── M19-M20 sizing inconsistent with M21-M24 and M25-M26
    │   │   → Verify: Vgs_M20 + Vgs_M21 + Vgs_M22 = Vgs_M25 (loop 1)
    │   │   → Verify: Vgs_M19 + Vgs_M23 + Vgs_M24 = Vgs_M26 (loop 2)
    │   └── W/L ratios of class-AB devices do not produce target Iq
    │       → Iq ∝ (W/L)_out / (W/L)_AB — adjust ratio
    │
    ├── Iq depends on VDD (supply voltage variation)
    │   ├── Floating CS (M27-M28) structure does NOT match class-AB (M19-M20)
    │   │   → FIX: make M27-M28 structurally identical to M19-M20
    │   └── Finite output impedance of floating devices → VDD directly across them
    │       → FIX: increase L of M19-M20 and M27-M28 for higher ro
    │
    ├── Iq depends on V_cm (common-mode input voltage)
    │   ├── Cascode current through summing circuit changes with CM → class-AB bias shifts
    │   │   → FIX: use dual-mirror summing (M11-M14 + M15-M18 with separate floating CS)
    │   │          as in the compact topology (Fig.11 of paper)
    │   └── Floating CS current varies > 5% across CM
    │       → Check Vgs_M11 + Vgs_M17 sum constancy
    │       → If not constant: mirrors are not equally loaded by CM currents
    │
    └── Output transistors entering triode (at extreme output swing)
        → Iq measurement only valid at mid-rail output
        → Under large signal, class-AB allows one output device to approach cutoff
           while the other handles full current — this is normal operation
```

---

## Fault Tree: Gain Too Low

```
A0 < A0_target
    │
    ├── First-stage gain A_v1 too low
    │   ├── Summing circuit cascode impedance insufficient
    │   │   → Increase L of cascode devices (M13-M14, M15-M16) and mirror devices
    │   ├── Class-AB bias sources loading the summing node (wrong topology!)
    │   │   → ⚠️ Are Ib6/Ib7 non-floating and in parallel with cascodes?
    │   │   → This is the naive topology (Fig.6) problem
    │   │   → FIX: use compact topology with floating class-AB embedded in summing
    │   └── gm_in too low → increase Iref or reduce gm/ID
    │
    ├── Second-stage gain A_v2 too low
    │   ├── Output transistor gm_out too low → increase Iq or W_out
    │   └── Output ro too low → increase L_out (but check speed/swing)
    │
    └── Can be improved by gain boosting
        → Apply gain-boosting amplifiers to cascodes M14 and M16
        → Paper explicitly mentions this option
```

---

## Fault Tree: GBW Too Low or Varies with V_cm

```
GBW < target
    │
    ├── gm_in too low [GBW = gm_in/(2π·Cc)]
    │   → Increase Iref or reduce gm/ID of input pairs
    │
    ├── Cc too large
    │   → Reduce Cc (but check PM carefully)
    │   → Consider cascoded-Miller for 2.5× BW improvement at same Cc
    │
    └── Parasitic poles at summing node too close to GBW
        → Increase gm of cascode devices (lower gm/ID)
        → Reduce parasitic capacitance (smaller input pair W)

GBW varies > 20% across CM range
    │
    ├── gm not constant → see "gm Not Constant" fault tree above
    │
    └── Summing node impedance varies with CM
        → Check: are mirror currents balanced at all CM?
        → Use dual-mirror summing with floating CS
```

---

## Fault Tree: Phase Margin Too Low

```
PM < PM_target
    │
    ├── Standard Miller compensation
    │   ├── Output pole p2 = gm_out/CL too close to GBW
    │   │   → Increase gm_out (more output stage current or lower gm/ID)
    │   │   → Reduce CL if possible
    │   ├── RHP zero z = gm_out/Cc too close to GBW
    │   │   → Increase gm_out or increase Cc
    │   └── Summing node pole too close to GBW
    │       → Same fixes as FC-OTA: increase cascode gm, reduce parasitic C
    │
    ├── Cascoded-Miller compensation
    │   ├── Output pole is higher (Cc/Cgs_out × gm_out/CL) → PM should be better
    │   │   BUT: RHP zero handling is different
    │   ├── Peaking at high output currents
    │   │   → Paper: negligible up to 3 mA output current
    │   │   → If driving > 3 mA: switch to standard Miller
    │   └── Cc/Cgs_out ratio wrong
    │       → Verify Cgs_out estimation (dominated by output transistor gate area)
    │
    └── PM varies with V_cm
        → gm_in varies → GBW varies → PM varies
        → Worst PM is typically at the CM value where GBW is highest
        → FIX: target PM at worst-case CM (where gm peaks in takeover)
```

---

## Fault Tree: SR Too Low or Asymmetric

```
SR < target
    │
    ├── SR_worst (middle CM) too low
    │   ├── Iref too low [SR = Iref/Cc]
    │   │   → Increase Iref (but check power budget)
    │   └── Cc too large → reduce Cc (check PM)
    │
    ├── SR changes by > 2× across CM range
    │   → This is inherent to 3× mirror gm-control
    │   → In middle CM: SR = Iref/Cc
    │   → In outer CM: SR = 2×Iref/Cc (tail current = 4×Iref)
    │   → Cannot be eliminated without changing gm-control method
    │
    └── Asymmetric rise/fall SR at same CM
        → Class-AB output stage imbalance
        → Check: is Iq of M25 ≈ Iq of M26?
        → Check: gm_M25 ≈ gm_M26?
```

---

## Fault Tree: Noise Too High

```
Noise > target
    │
    ├── Wrong topology (class-AB bias contributes)
    │   ⚠️ THIS IS THE #1 R2R NOISE ISSUE
    │   ├── Using naive topology (Fig.6) where Ib6/Ib7 are not floating
    │   │   → Current gain from Ib6/Ib7 to input is 1 → full noise contribution
    │   │   → FIX: use compact topology (Fig.11) with floating class-AB
    │   └── Floating CS (M27-M28) not truly floating
    │       → Check: is M27-M28 connected to a supply-referred bias?
    │       → Must be floating for noise cancellation
    │
    ├── Input pair noise too high (correct topology)
    │   ├── gm_in too low → thermal noise
    │   │   → Increase gm_in (more current or lower gm/ID)
    │   └── W·L too small → 1/f noise
    │       → Increase area of M1-M4
    │
    ├── Summing circuit mirror noise
    │   ├── Mirror devices (M11-M12, M17-M18) contribute at unity current gain
    │   │   → Increase L of mirror devices for 1/f
    │   │   → Increase Vov (lower gm/ID) of mirror devices to reduce gm_mirror/gm_in ratio
    │   └── Cascode devices: negligible noise (always true)
    │
    └── Noise varies with CM range
        → When only one pair active: fewer noise sources but also lower effective gm
        → When both pairs active: more sources but higher gm
        → Check noise at multiple CM operating points
```

---

## Fault Tree: CMRR Too Low

```
CMRR < target
    │
    ├── CMRR in takeover regions is ~43 dB (fundamental limit)
    │   → N and P pairs have different offsets
    │   → Offset changes ~2 mV over each 300mV takeover region
    │   → CMRR_takeover ≈ ΔV_offset / ΔV_cm ≈ 2mV/300mV ≈ 43 dB
    │   → Cannot exceed ~50 dB without trimming or alternative gm-control
    │
    ├── CMRR outside takeover regions is < 70 dB
    │   ├── Tail current source ro too low → increase L_tail
    │   ├── Mirror mismatch in summing circuit → improve matching (centroid layout)
    │   └── gm-control mirrors injecting CM-dependent current → check 3× mirror accuracy
    │
    └── CMRR improvement strategies
        → Better N/P pair matching (common-centroid layout)
        → Wider takeover regions (spread offset change over more voltage)
        → Trimming (laser, e-fuse, or digital calibration)
        → Alternative: maximum-current-selector gm control (no takeover region)
```

---

## Fault Tree: Output Not Rail-to-Rail

```
Output swing not reaching rails
    │
    ├── Vout_max < VDD - 0.3V
    │   → M25 (PMOS output) Vdsat too large → increase W_M25 or reduce I_M25
    │
    ├── Vout_min > VSS + 0.3V
    │   → M26 (NMOS output) Vdsat too large → increase W_M26 or reduce I_M26
    │
    └── Output devices entering triode too early
        → Class-AB minimum current too high → one device drawing too much current
          even when the other should be handling the load
        → FIX: adjust translinear loop W/L ratios to reduce I_min
```

---

## Interdependence Map (R2R-Specific)

| Fix                        | Helps              | May hurt             | R2R-specific note |
|---------------------------|--------------------|-----------------------|-------------------|
| Increase Iref              | GBW, SR, gm_in    | Power, noise (if gm/ID unchanged) | SR_worst improves proportionally |
| Decrease Cc                | GBW, SR            | PM                    | Cascoded-Miller gives 2.5× free BW |
| Cascoded-Miller comp       | GBW (2.5×), settling | PM margin, peaking at high Iout | Use standard Miller if Iout > 3mA |
| Increase W·L of input      | Noise (1/f)        | Speed (parasitic C), area | Need for both N and P pairs → 2× area |
| Use floating class-AB      | Noise, offset, gain | None                  | Always use compact topology (Fig.11) |
| Use floating CS             | Noise, offset       | None                  | Must match class-AB structure for Iq stability |
| Increase L of mirrors       | Gain, 1/f noise    | Speed (summing poles) | Tradeoff similar to FC-OTA |
| Widen takeover region       | CMRR               | gm variation, area    | Requires modified gm-control circuit |
| Gain boosting on cascodes   | Gain (+20-30 dB)   | Stability (extra poles) | Paper explicitly suggests this for M14/M16 |

---

## Output Format

```
DIAGNOSIS: gm varies 28% across CM [target ≤ 15%] ❌
  Root cause  : 3× mirror M6-M7 ratio inaccurate
                SPICE shows M7 current = 2.6× M6 (should be 3×)
                L = 1µm → CLM error at Vds mismatch
  Affected Role: GM_CTRL (M6-M7)
  Fix         : Increase L of M6, M7 from 1µm to 3µm
                → improves mirror accuracy to 2.95× (within 2%)
                → expected gm variation drops to 12%
  Side effects : gm-control mirrors slower (but not speed-critical)
  Priority    : 1

DIAGNOSIS: Noise @10kHz = 35 nV/√Hz [target ≤ 25 nV/√Hz] ❌
  Root cause  : Using naive cascaded topology (Fig.6)
                Class-AB bias sources Ib6, Ib7 contribute at unity current gain
  Affected Role: CLASS_AB bias
  Fix         : Migrate to compact topology (Fig.11):
                embed floating class-AB (M19-M20) in summing circuit
                bias with floating CS (M27-M28)
  Side effects : Eliminates ~40% of total noise contribution
                 Expected noise: ~22 nV/√Hz (comparable to 3-stage)
  Priority    : 1 (architectural change)

DIAGNOSIS: PM = 48° with cascoded-Miller [target ≥ 55°] ❌
  Root cause  : gm_out insufficient → p2 not high enough
                gm_out = 0.8 mS, CL = 10pF, Cc = 2pF, Cgs_out = 0.8pF
                p2_cascode = (2/0.8) × (0.8m/10p) = 200 MHz
                GBW = 30µ/(2π×2p) = 2.4 MHz
                RHP zero and parasitic poles limiting PM
  Affected Role: OUTPUT (M25, M26)
  Fix         : Increase gm_out by increasing Iq_out from 90µA to 150µA
                → gm_out ≈ 1.5 mS → p2 shifts higher
  Side effects : Power increases ~120 µW; output swing slightly reduced
  Priority    : 2
```
