# TSM Equations

## Circuit Structure

```
       VDD ──────────┬──────────────── VDD
         |           |                   |
        M1          M2                  M7
      (LOAD)      (LOAD)           (OUTPUT_CS)
       pfet        pfet              pfet
      diode         |                   |
         |     1st_out ──── Rc ── Cc ──Vout── CL ── GND
  mirror └────┬─────┘                   |
              |                        M8
        M3         M4            (OUTPUT_BIAS)
      (DIFF)     (DIFF)            nfet
       nfet       nfet               |
       vinn       vinp              GND
         └────┬────┘
              |
             M6 (TAIL, nfet)
              |
             GND

  I_bias ── M5 (BIAS_GEN, diode nfet) ── GND
            gate → M6 gate, M8 gate

Nodes (from netlist):
  1st_out (net5) : drain M2, drain M4, gate M7, Cc
  mirror  (net1) : drain/gate M1, drain M3, gate M2
  tail    (net2) : source M3, source M4, drain M6
  Vout           : drain M7, drain M8, CL, Cc
  bias    (net3) : gate/drain M5, gate M6, gate M8
```

| Role | Device | Type | Circuit function |
|------|--------|------|-----------------|
| DIFF_PAIR | M3, M4 | nfet | Input differential pair |
| LOAD | M1, M2 | pfet | Active current mirror load (1st stage) |
| BIAS_GEN | M5 | nfet | Diode-connected bias reference |
| TAIL | M6 | nfet | Tail current source (mirrors M5) |
| OUTPUT_CS | M7 | pfet | Common-source 2nd-stage amplifier |
| OUTPUT_BIAS | M8 | nfet | 2nd-stage current source load (mirrors M5) |
| COMPENSATION | Cc, Rc | — | Miller capacitor + nulling resistor |

Matching: M3 ≡ M4 (same W, L, M), M1 ≡ M2 (same W, L, M).
M5/M6/M8 share L; mirror ratios set by multiplier M.

---

## Symbol Definitions — LUT Derivation

Once **(gm, L, gm/ID)** are determined for a device (see design-flow),
all remaining parameters are derived from the LUT.

**LUT units:** id_w is stored in A/m, cgs_w/cgd_w/cdb_w in F/m, ft in Hz, vgs/vth/vdsat in V.
All LUT per-width metrics use SI base unit meters. Derived W is in meters.

**LUT API:** `lut_query(device, metric, L, corner=corner, temp=temp_str, gm_id_val=gm_id)`
where `temp` is a string like `'27C'`, `'40C'`, `'70C'` — NOT a bare integer.
`list_available_L(device, corner=corner, temp=temp_str)` uses the same `temp` format.

```
LUT query format: lut_query(device_type, metric, L, corner=corner, temp=temp_str, gm_id_val=gm_id)

ID      = gm / (gm/ID)                         derived
id_w    = lut_query(dev, 'id_w',  L, gm_id)    from LUT (A/m)
W       = ID / id_w                             derived (m)  ← meters, not µm
gm_gds  = lut_query(dev, 'gm_gds', L, gm_id)  from LUT
gds     = gm / gm_gds                          derived (S)
ft      = lut_query(dev, 'ft',    L, gm_id)    from LUT (Hz)
cgs_w   = lut_query(dev, 'cgs_w', L, gm_id)    from LUT (F/m)
cgd_w   = lut_query(dev, 'cgd_w', L, gm_id)    from LUT (F/m)
cdb_w   = lut_query(dev, 'cdb_w', L, gm_id)    from LUT (F/m)
Cgs     = cgs_w × W                            derived (F)  ← no 1e-6 (W is already in m)
Cgd     = cgd_w × W                            derived (F)  ← no 1e-6 (W is already in m)
Cdb     = cdb_w × W                            derived (F)  ← drain-bulk junction cap
vdsat   = lut_query(dev, 'vdsat', L, gm_id)    from LUT (V) — BSIM4 |VDS|_sat, positive magnitude
```

⚠️ **Common pitfall**: W = ID / id_w yields **meters** (not µm) because
id_w is A/m. When displaying W, multiply by 1e6 to show µm. When computing
Cgs = cgs_w × W, use W in meters directly — do NOT multiply by 1e-6.

Since M3 ≡ M4: `gm3 = gm4`, `gds3 = gds4`, `Cgs3 = Cgs4`, `Cgd3 = Cgd4`, `Cdb3 = Cdb4`.
Since M1 ≡ M2: `gm1 = gm2`, `gds1 = gds2`, `Cgs1 = Cgs2`, `Cgd1 = Cgd2`, `Cdb1 = Cdb2`.

---

## Bias Current Expressions

```
I_bias → M5 (BIAS_GEN, unit cell)
I_tail = (M6_M / M5_M) × I_bias        [TAIL mirrors BIAS_GEN]
ID_M8  = (M8_M / M5_M) × I_bias        [OUTPUT_BIAS mirrors BIAS_GEN]
ID3 = ID4 = I_tail / 2                  [each diff pair device]
ID1 = ID2 = ID3                         [load carries same current]
ID7 = ID8 = ID_M8                       [second stage]
```

Systematic offset condition (equal current densities at 1st-stage output):
```
(W1/L1)/(W7/L7) = (1/2) × (W6/L6)/(W8/L8)
```

## Quiescent Power

```
P = VDD × (I_bias + I_tail + ID7)
```

---

## Equations

All values are computable from the LUT except noise parameters (Kf, Cox, µ)
which are process-dependent and evaluated by the simulator.

### Sub-Block Abstraction

Three roles in the TSM are current-source / load sub-blocks:
**LOAD** (M1/M2) in the first stage, **OUTPUT_BIAS** (M8) in the
second stage, and **TAIL** (M6) for the input pair. Each can be a
single transistor, a regular cascode, or an lv_cascode. The sub-block
exposes `gds_eq`, `C_eq`, `p_int`, `V_headroom` — see
`general/knowledge/mirror-load-structures.md`.

Substitution map for the TSM equations below:

| In formulas | single | cascode / lv_cascode |
|-------------|--------|----------------------|
| `gds_eq_LOAD`  | `gds1` | `(gds1 × gds_loadcas) / gm_loadcas` |
| `C_eq_LOAD`    | `Cgd1 + Cdb1` | `Cgd_loadcas + Cdb_loadcas` |
| `p_int_LOAD`   | none   | `gm_loadcas / C_int_LOAD` |
| `gds_eq_OBIAS` | `gds8` | `(gds8 × gds_obcas) / gm_obcas` |
| `C_eq_OBIAS`   | `Cgd8 + Cdb8` | `Cgd_obcas + Cdb_obcas` |
| `p_int_OBIAS`  | none   | `gm_obcas / C_int_OBIAS` |
| `gds_eq_TAIL`  | `gds6` | `(gds6 × gds_tcas) / gm_tcas` |
| `V_headroom_TAIL` | `vdsat6` | `vdsat6 + vdsat_tcas` |

Where:
- `C_int_LOAD  = Cgs_loadcas + Cdb1 + Cgd1`
- `C_int_OBIAS = Cgs_obcas   + Cdb8 + Cgd8`

For the lv_cascode TAIL variant, the cascode gate is an external
subcircuit port `Vbias_cas_n`:
`Vbias_cas_n = vdsat6 + vdsat_tcas + vth_tcas`  (NMOS, rail = VSS)

### DC Gain

First-stage gain:
`A_v1 = gm3 / (gds3 + gds_eq_LOAD)`

Second-stage gain:
`A_v2 = gm7 / (gds7 + gds_eq_OBIAS)`

Total open-loop DC gain:
`A0 = A_v1 × A_v2`

To select L during initial sizing (single load): sweep L, query
`gm_gds` for nfet, pick L where `gm_gds_M3 / 1.5 ≥ sqrt(A0_target_linear)`.
For cascode/lv_cascode loads, much shorter L can meet the gain because
the cascode provides an extra (gm_cas·ro_cas) factor.

### Poles, Zeros, and Transfer Function

**RHP zero and nulling resistor Rc:**

Feedforward through Cc creates a zero whose location depends on Rc:
```
z = 1 / [Cc · (1/gm7 - Rc)]
```

| Rc value | Zero location | Effect |
|----------|--------------|--------|
| Rc = 0 (no resistor) | z = +gm7/Cc (RHP) | Degrades PM |
| Rc = 1/gm7 | z → ∞ (cancelled) | Zero removed |
| Rc > 1/gm7 | z = -1/[Cc·(Rc - 1/gm7)] (LHP) | Can cancel p2 |

**Preferred: LHP zero cancels output pole p2.**

To compute Rc, first obtain the exact p2 from the KCL-derived cubic
(see "Poles" section below), then set z_Rc = p2:
```
Rc = 1/gm7 + 1/(p2_kcl · Cc)
```

**Approximate Rc formula** (for initial estimation only):
```
Rc_approx = (1/gm7) · (Cc + C1)·(Cc + CTL) / Cc²
```
This approximation overestimates Rc because it uses the simplified p2
formula. Always recompute Rc from the KCL-derived p2 before simulation.

#### Node Capacitances

The pole locations depend on total capacitance at each node. These
change with the LOAD and OUTPUT_BIAS sub-block types.

**IMPORTANT — Use corrected Cgd and Cdb (see `lut-parameter-derivation.md`):**
All Cgd and Cdb terms below MUST include extrinsic components from
`extrinsic_caps()`. The LUT intrinsic Cgd is ≈ 0 in saturation; the
physical gate-drain overlap dominates. LUT Cdb misses junction sidewall
terms that are significant for multi-instance (high-M) devices.

**Single load / single output-bias:**
```
C1  = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4 + Cgd7    [cap at net5 — includes Cgd7 coupling to vout]
CTL = CL + Cdb7 + Cdb8 + Cgd7 + Cgd8               [total output cap]
C2  = Cgs1 + Cgs2 + Cdb1 + Cdb3 + Cgd2 + Cgd3     [cap at net1 — includes Cgd2/Cgd3 coupling]
```

**Cascode / LV-cascode LOAD:** `Cdb1` moves from net1 to internal node;
`Cgd_loadcas + Cdb_loadcas` replace it at net1:
```
C2  = Cgs1 + Cgs2 + Cgd_loadcas + Cdb_loadcas + Cdb3 + Cgd3
C_int_LOAD = Cgs_loadcas + Cdb1 + Cgd1
```

**Cascode / LV-cascode OUTPUT_BIAS:** `Cdb8 + Cgd8` in CTL replaced by
cascode device caps:
```
CTL = CL + Cdb7 + Cdb_obcas + Cgd7 + Cgd_obcas
C_int_OBIAS = Cgs_obcas + Cdb8 + Cgd8
```

#### Poles

**Mirror pole (p3) — at net1 (separate node, independent of Rc-Cc):**
```
G_net1 = gm1 + gds1 + gds3              [M1 diode + M3 gds]
p3 = G_net1 / C2                         [rad/s]
```
LHP zero at `≈ 2×p3` (mirror zero, same doublet as 5T OTA).

**p1, p2, p4 — from KCL cubic (exact, coupled net5-vout system):**

The net5 and vout nodes are coupled through the Rc-Cc branch and Cgd7.
The standard simplified formulas `p2 = gm7·Cc/(C1·Cc+C1·CTL+Cc·CTL)`
and `p4 = gm7/C1` ignore this coupling and produce large errors:
p2 is underestimated by ~40% and p4 is overestimated by ~4×.

Instead, solve the exact KCL-derived cubic polynomial for the three
poles of the coupled 2-node system. Define:

```python
tau    = Rc * Cc                         # Rc-Cc time constant
Go     = gds7 + gds_eq_OBIAS            # output conductance
G1     = gds_eq_LOAD + gds3             # net5 conductance (gds2=gds_LOAD, gds4=gds3)
Ccomp  = Cc + Cgd7                       # total compensation cap
Gt     = gm7 + Go + G1                  # ≈ gm7 (dominant)
Ct     = CTL + C1                        # total node cap

# Cubic: d3·s³ + d2·s² + d1·s + d0 = 0
d0 = Go * G1
d1 = Go*C1 + G1*CTL + Go*G1*tau + Ccomp*Gt
d2 = C1*CTL + (Go*C1 + G1*CTL)*tau + Ccomp*Ct + tau*Cgd7*Gt
d3 = C1*CTL*tau + tau*Cgd7*Ct

poles = numpy.roots([d3, d2, d1, d0])    # 3 real negative roots
# Sort by magnitude: poles[0]=p1 (dominant), poles[1]=p2, poles[2]=p4
```

All three poles are real and in the LHP for physically valid parameters.
The dominant pole p1 is at ~kHz (sets the -3dB point), p2 is the output
pole (~50-100 MHz), and p4 is the compensation pole (~100-300 MHz).

**Why the simplified formulas fail:** At frequencies above
`1/(2π·Rc·Cc)`, the Rc-Cc branch impedance transitions from capacitive
to resistive (Rc). The conductance `1/Rc` then loads the net5 node,
pulling p4 down by ~4× from the unloaded `gm7/C1`. Simultaneously,
the Rc delay weakens the Miller feedback, pushing p2 up by ~40%.
The cubic captures this coupling exactly.

**Cascode internal poles** (only when sub-block is cascode/lv_cascode):
```
p_int_LOAD  = gm_loadcas / C_int_LOAD
p_int_OBIAS = gm_obcas / C_int_OBIAS
```

#### Zeros

**LHP zero from Rc nulling:**
```
z_Rc = -1 / [Cc · (Rc - 1/gm7)]   [rad/s, LHP when Rc > 1/gm7]
```
This formula is accurate (< 1% error vs SPICE). Rc is chosen so that
`z_Rc = p2_kcl` (the KCL-derived p2 from the cubic above).

**Mirror zero (LHP):**
```
fz_mirror ≈ 2 × |p3| / (2π)
```

**Cgd3/Cgd4 feedforward zeros (RHP):**
```
fz_rhp_dp = gm3 / (2π·Cgd3)             [from diff pair Cgd to net5/net1]
```

#### GBW

```
ω_c = gm3 / Cc
GBW = gm3 / (2π·Cc)
```

**⚠️ GBW / ft validity:** This formula and the PM formula below are
valid only when GBW < ft for all signal-path devices. Check ft of M3,
M1, and M7 after sizing — if GBW/ft > 0.3 for any device, the
analytical PM will be optimistic (see `lut-parameter-derivation.md`
GBW/ft table).

#### Phase Margin

Use the KCL-derived p2 and p4 from the cubic polynomial (NOT the
simplified formulas). The PM formula structure is the same — only
the pole values change.

**General (all poles, using KCL-derived p2_kcl and p4_kcl):**
```
PM = 90° − arctan(ω_c/p2_kcl) − arctan(ω_c/p3) − arctan(ω_c/p4_kcl)
     + arctan(ω_c/z_Rc) + arctan(ω_c/fz_mirror·2π) − arctan(ω_c/fz_rhp_dp·2π)
```

When Rc is designed so that z_Rc = p2_kcl, the p2 and z_Rc terms
nearly cancel (residual ~1-2°), leaving:
```
PM ≈ 90° − arctan(ω_c/p3) − arctan(ω_c/p4_kcl) + arctan(ω_c/fz_mirror·2π)
```

Note: p4_kcl is typically 100-300 MHz (vs the simplified `gm7/C1` which
gives 500-800 MHz). This is the dominant non-mirror phase contribution.

**Additional cascode internal pole penalties:**
```
if p_int_LOAD  is not None: PM -= arctan(ω_c / p_int_LOAD)
if p_int_OBIAS is not None: PM -= arctan(ω_c / p_int_OBIAS)
```

Design constraint: each cascode `p_int > 3 × ω_c`.

### Slew Rate

**Sustained slew rate (standard formula):**
```
SR+_sustained = I_tail / Cc
SR-            = min(I_tail / Cc,  ID7 / CTL)
```

where `CTL = CL + Cdb7 + Cdb8 + Cgd7 + Cgd8` is the total output
capacitance including parasitics (use corrected Cgd/Cdb with extrinsic
terms from `extrinsic_caps()`).

**Effect of nulling resistor Rc on SR+ (important):**
When Rc > 0, the Miller feedback through Cc is delayed by τ = Rc × Cc.
During this delay (Phase 1), net5 slews at the much faster rate
`I_tail / C1` instead of `I_tail / Cc`, because Rc blocks the Cc
current path and net5 sees only its local parasitic cap C1.
M7 amplifies this fast net5 transient → the output slews faster than
`I_tail / Cc` during Phase 1. After ~2τ, the Cc feedback establishes
and the output settles to the sustained rate `I_tail / Cc` (Phase 2).

The SPICE-measured SR+ captures the peak slope across the 20–80%
transition, which includes Phase 1. This yields a measured SR+
*between* the two limits:
```
I_tail / Cc ≤ SR+_measured ≤ I_tail / C1
```

For sizing, use `SR+_sustained = I_tail / Cc` as the conservative
design target. The actual SR+ will be higher when Rc > 0.

**Effect of M7 Cgd Miller multiplication on SR-:**
During negative slew, M7 is an active CS amplifier. Its Cgd (including
the physical gate-drain overlap) appears at the output node multiplied
by `(1 + A_v2)` where `A_v2 = gm7 / (gds7 + gds8)`. This increases
the effective CTL for SR- beyond the small-signal estimate:
```
CTL_eff = CTL + Cgd7 × A_v2       [Cgd7 includes extrinsic overlap]
SR-_corrected = min(I_tail / Cc,  ID7 / CTL_eff)
```

Design constraint for symmetric SR:
```
ID7 ≥ I_tail × CTL_eff / Cc
```

### Output Swing

```
V_out,min = Vdsat_M8            (M8 saturation)
V_out,max = VDD - Vdsat_M7      (M7 saturation)
V_swing = VDD - Vdsat_M7 - Vdsat_M8
```

### Noise (input-referred)

**Thermal noise:**
```
S_thermal² = (16kT)/(3·gm3) × [1 + gm1/gm3]
```

**1/f noise:**
```
S_1f² = (2·Kf_n)/(Cox·W3·L3·f) × [1 + (Kf_p·µn·W3·L3)/(Kf_n·µp·W1·L1) × (gm1/gm3)²]
```
Input pair is NFET (Kf_n, µn); load is PFET (Kf_p, µp).
Derived from S_vg² = KF/(2µCox²WLf) where µ appears in the denominator.

Key insight: noise is dominated by the first-stage input pair and load.
Second-stage noise is divided by A_v1² and is negligible when A_v1 > 20 dB.

**Integrated noise:**
```
V²_noise = S_1f² × ln(fH/fL) + S_thermal² × (fH - fL)
```

### CMRR and PSRR

**CMRR:**
```
CMRR = 2·gm3·gm1 / [(gds3 + gds1)·gds_eq_TAIL]
```
Dominated by tail current source impedance (`ro_eq_TAIL = 1/gds_eq_TAIL`).

⚠️ **Accuracy note:** When the TAIL operates near the saturation
boundary (|Vds| ≈ vdsat, margin < 50 mV), the OP-extracted `gds_eq_TAIL`
is the tangent slope at one bias point and may overestimate the
effective small-signal conductance seen by the AC CMRR measurement.
The BSIM4 model uses a continuous gds(Vds) transition, so the actual
CMRR can be 5–7 dB higher than this formula predicts in marginal-
saturation conditions. Ensure adequate TAIL Vds margin (> 50 mV) for
the formula to be reliable.

**PSRR⁻ (VSS coupling, low frequency):**

VSS noise couples to the output through **two paths**:

*Path 1 — M8 direct coupling (output node):*
M8 source/body at VSS. When VSS shifts, M8 Vds changes:
```
A_VSS_M8 = gds8 / (gds7 + gds8)
```

*Path 2 — TAIL coupling (dominant when TAIL is near triode):*
TAIL source at VSS. When VSS shifts, TAIL Vds changes →
`ΔI_tail = gds_eq_TAIL · ΔVSS`. This common-mode perturbation leaks
through the mirror mismatch (gds1 vs gm1) to net5, then is amplified
by the second stage:
```
A_VSS_TAIL = [gds_eq_TAIL · gds1 · gm7] / [2·(gm1 + gds1)·(gds3 + gds1)·(gds7 + gds8)]
```
Simplified (gm1 >> gds1):
```
A_VSS_TAIL ≈ [gds_eq_TAIL · gds1 · gm7] / [2·gm1·(gds3 + gds1)·(gds7 + gds8)]
```

The TAIL path dominates when `gds_eq_TAIL` is large (TAIL near triode
or un-cascoded).

**Full PSRR⁻:**
```
PSRR⁻ = A0 / (A_VSS_M8 + A_VSS_TAIL)
```

The legacy single-path formula `PSRR⁻ = gm3·gm7 / [(gds3+gds1)·gds8]`
assumes the TAIL path is negligible (valid only when
`gds_eq_TAIL << gds8`, i.e. TAIL is deep in saturation or cascoded).
**Do not use the single-path formula when TAIL Vds margin < 100 mV** —
it overestimates PSRR⁻ by 10–20 dB.

Improving PSRR⁻: cascode the TAIL (boosts `ro_eq_TAIL` by
`gm_tcas/gds_tcas`), increase L5 (= L6) to raise ro6, or increase the
TAIL Vds headroom by raising gm/ID of the diff pair (reduces VGS_M3).

**PSRR⁺ (VDD coupling, low frequency):**

VDD couples to the output through M7, whose source is directly at VDD.
The analysis requires careful small-signal KCL at net1, net5, and Vout.
At DC, Cc is an open circuit so it does not provide feedback.

**Step 1 — net1 (mirror node) tracking:**

KCL at net1: M1 current (diode, source=VDD) = M3 current (drain to net1).
```
(gm1 + gds1)·(δVnet1 − δVDD) = gds3·δVnet1
→ δVnet1/δVDD = (gm1 + gds1) / (gm1 + gds1 − gds3)
              ≈ 1 + gds3/gm1    (since gm1 >> gds1, gds3)
```
Net1 slightly **overshoots** VDD because the M3 gds load is smaller
than the M1 diode conductance.

**Step 2 — net5 (1st-stage output) tracking:**

KCL at net5: M2 current (gate=net1, source=VDD) = M4 current (gds only).
```
gm1·(δVnet1 − δVDD) + gds1·(δVnet5 − δVDD) = gds3·δVnet5
```
Substituting δVnet1 = (1 + gds3/gm1)·δVDD:
```
δVnet5/δVDD = (gm1 + gds1) / (gm1 + gds1 − gds3)
            ≈ 1 + gds3/gm1
```
Net5 tracks VDD with the same overshoot as net1.

**Step 3 — output coupling:**

M7 (PFET, source=VDD, gate=net5, drain=Vout), M8 (NFET at output):
```
ids_M7 = gm7·(δVnet5 − δVDD) + gds7·(δVout − δVDD)
ids_M8 = gds8·δVout
```
Setting ids_M7 = ids_M8 and letting x = δVnet5/δVDD:
```
δVout/δVDD = [gds7 − gm7·(x − 1)] / (gds7 − gds8)
           ≈ [gds7 − gm7·gds3/gm1] / (gds7 − gds8)
```

The numerator contains **two competing terms**:
- `gds7`: M7's channel-length modulation pushes Vout toward VDD
- `gm7·gds3/gm1`: net5 overshoot reduces M7 Vsg, opposing the push

When `gm7·gds3/gm1 ≈ gds7`, the terms nearly cancel → very high PSRR⁺.

**Full PSRR⁺:**
```
PSRR⁺ = A0 · (gds7 − gds8) / |gds7 − gm7·gds3/gm1|
```

⚠️ **Accuracy note:** This formula gives ~6 dB overestimate compared to
SPICE because it neglects finite M6 impedance effects on the tail node
(which slightly degrades the net5 tracking). The remaining error also
depends on the gds7/gds8 ratio — the formula is most accurate when
gds7 and gds8 are well separated.

⚠️ **The legacy formula `PSRR⁺ ≈ gm3/gds3` is incorrect.** It models
the VDD-to-net5 path as a simple `gds3/(gds3+gds1)` resistive divider,
ignoring that M1/M2 (sources at VDD) actively track VDD at their
outputs. The legacy formula underestimates PSRR⁺ by 20–25 dB.

### CM Input Range

```
V_cm,min = V_headroom_TAIL + VGS_M3 + VSS     (TAIL saturation limit)
V_cm,max = VDD - |VSG_M1| + VTN       (M1 headroom limit)
```

### Node Capacitances

| Node | Devices at node | Capacitance |
|------|----------------|-------------|
| 1st_out (net5, gate M7) | M2 drain, M4 drain, M7 gate | `C1 = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4` |
| Mirror (net1) | M1 drain/gate, M3 drain, M2 gate | `C2 = Cgs1 + Cgs2 + Cdb1 + Cdb3 + Cgd3` |
| Output (Vout) | M7 drain, M8 drain, CL | `CTL = CL + Cdb7 + Cdb8 + Cgd7 + Cgd8` |

All Cgd and Cdb values MUST include extrinsic components (see
`general/knowledge/lut-parameter-derivation.md` — Extrinsic Capacitance
Correction section). The LUT intrinsic Cgd ≈ 0 in saturation; the
physical gate-drain overlap from `extrinsic_caps()` dominates.
