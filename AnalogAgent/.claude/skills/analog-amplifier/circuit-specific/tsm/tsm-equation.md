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
M5/M6/M8 share L; mirror ratios set by finger count.

---

## Symbol Definitions — LUT Derivation

Once **(gm, L, gm/ID)** are determined for a device (see design-flow),
all remaining parameters are derived from the LUT.

**LUT units:** id_w is stored in A/m (= µA/µm), cgs_w/cgd_w in F/m, ft in Hz, vov in V.
Ensure unit consistency when mixing SI-derived values (gm in S, ID in A) with LUT values.

```
LUT query format: lut_query(device_type, metric, L, gm_id_val=gm_id)

ID      = gm / (gm/ID)                         derived
id_w    = lut_query(dev, 'id_w',  L, gm_id)    from LUT (µA/µm)
W       = ID / id_w                             derived (µm)
gm_gds  = lut_query(dev, 'gm_gds', L, gm_id)  from LUT
gds     = gm / gm_gds                          derived (S)
ft      = lut_query(dev, 'ft',    L, gm_id)    from LUT (Hz)
cgs_w   = lut_query(dev, 'cgs_w', L, gm_id)    from LUT (F/m)
cgd_w   = lut_query(dev, 'cgd_w', L, gm_id)    from LUT (F/m)
Cgs     = cgs_w × W × 1e-6                     derived (F)
Cgd     = cgd_w × W × 1e-6                     derived (F)
vov     = lut_query(dev, 'vov',   L, gm_id)    from LUT (V)
```

Since M3 ≡ M4: `gm3 = gm4`, `gds3 = gds4`, `Cgs3 = Cgs4`, `Cgd3 = Cgd4`.
Since M1 ≡ M2: `gm1 = gm2`, `gds1 = gds2`, `Cgs1 = Cgs2`, `Cgd1 = Cgd2`.

⚠️ LUT `vov` for PFET may return Vgs instead of Vov. Use `vov ≈ 2/(gm/ID)`
as an analytical estimate if the LUT value seems unreasonable (|vov| > 0.5V).

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

### DC Gain

First-stage gain:
`A_v1 = gm3 / (gds3 + gds1)`

Second-stage gain:
`A_v2 = gm7 / (gds7 + gds8)`

Total open-loop DC gain:
`A0 = A_v1 × A_v2 = [gm3/(gds3+gds1)] × [gm7/(gds7+gds8)]`

To select L during initial sizing: sweep L, query `gm_gds` for nfet,
pick L where `gm_gds_M3 / 2 ≥ sqrt(A0_target_linear)`.
Then compute the exact A0 once all devices are sized.

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

Setting z_LHP = p2 = gm7·Cc/(C1·Cc + C1·CTL + Cc·CTL) and solving:
```
Rc = (1/gm7) · (Cc + C1)·(Cc + CTL) / Cc²

where:
  C1  = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4    [cap at net5]
  CTL = CL + Cdb7 + Cdb8 + Cgd7 + Cgd8       [total output cap]
```

Simplified (when C1 << Cc and parasitic drain caps << CL):
```
Rc ≈ (1/gm7) · (1 + CL/Cc)
```

This removes both the zero and p2 from the loop gain, leaving only p3
(and p4) as non-dominant poles — significantly improving PM.

With p2 cancelled, the transfer function simplifies to three effective poles:
```
H(s) ≈ A0 / [(1 + s/p1)(1 + s/p3)(1 + s/p4)]
```
p4 = gm7/C1 arises from the Rc–C1 interaction at net5.

**Dominant pole (p1):**
```
p1 = gm3 / (A0 · Cc)   [rad/s]
f_p1 = p1 / (2π)
```

**Output pole (p2):**
```
p2 = gm7·Cc / (C1·Cc + C1·CTL + Cc·CTL)   [rad/s]

where:
  C1  = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4    [cap at 1st-stage output, net5]
  CTL = CL + Cdb7 + Cdb8 + Cgd7 + Cgd8       [total output cap]
```

Simplified (when CL >> parasitic caps):
```
p2 ≈ gm7 / CL
```

**Mirror pole (p3):**
```
p3 = gm1 / C2   [rad/s]

where:
  C2 = Cgs1 + Cgs2 + Cdb1 + Cdb3 + Cgd3    [cap at mirror node, net1]
```

Simplified (when Cgs1 + Cgs2 dominate):
```
p3 ≈ gm1 / (2·Cgs1)
```

**Compensation pole (p4):**
```
p4 = gm7 / C1   [rad/s]
```

### GBW and Phase Margin

**Unity-gain bandwidth (GBW):**
```
ω_c ≈ gm3 / Cc
GBW = gm3 / (2π·Cc)
```
Valid when non-dominant poles p2, p3, p4 > 2 × ω_c.

**Phase margin (general, all four poles):**
```
PM = 90° - arctan(ω_c/p2) - arctan(ω_c/p3) - arctan(ω_c/p4)
```
Since p1 << ω_c, `arctan(ω_c/p1) ≈ 90°`, reducing the 180° baseline to 90°.

**Phase margin (with Rc cancelling p2):**

When `Rc = (1/gm7)·(1 + CL/Cc)`, the LHP zero cancels p2:
```
PM = 90° - arctan(ω_c/p3) - arctan(ω_c/p4)
```
This is the preferred operating mode. PM is now set by the mirror pole
p3 and compensation pole p4 only.

### Slew Rate

Positive and negative slew rates are separate specs:
```
SR+ = I_tail / Cc
SR- = min(I_tail / Cc,  ID7 / (Cc + CTL))
```

SR+ is limited by the 1st stage driving net5 through Cc (M7 can source
well beyond its quiescent current during positive slew, so it is not
the bottleneck).

SR- is limited by whichever is slower: the 1st stage driving net5
(I_tail/Cc) or M8 discharging the output (ID7/(Cc + CTL)).

Design constraint for symmetric SR:
```
ID7 ≥ I_tail × (Cc + CTL) / Cc
```

### Output Swing

```
V_out,min = Vov_M8            (M8 saturation)
V_out,max = VDD - |Vov_M7|    (M7 saturation)
V_swing = VDD - |Vov_M7| - Vov_M8
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
CMRR = 2·gm3·gm1 / [(gds3 + gds1)·gds6]
```
Dominated by tail current source impedance (ro6 = 1/gds6).
Increase L6 (equivalently L5, since they share L) to improve CMRR.

⚠️ **Accuracy note:** When M6 operates near the saturation boundary
(Vds ≈ Vov, margin < 50 mV), the OP-extracted gds6 is the tangent
slope at one bias point and may overestimate the effective small-signal
conductance seen by the AC CMRR measurement. The BSIM4 model uses a
continuous gds(Vds) transition, so the actual CMRR can be 5–7 dB higher
than this formula predicts in marginal-saturation conditions. Ensure
adequate M6 Vds margin (> 50 mV) for the formula to be reliable.

**PSRR⁻ (VSS coupling, low frequency):**

VSS noise couples to the output through **two paths**:

*Path 1 — M8 direct coupling (output node):*
M8 source/body at VSS. When VSS shifts, M8 Vds changes:
```
A_VSS_M8 = gds8 / (gds7 + gds8)
```

*Path 2 — M6 tail coupling (dominant when M6 is near triode):*
M6 source at VSS. When VSS shifts, M6 Vds changes → ΔI_tail = gds6·ΔVSS.
This common-mode perturbation leaks through the mirror mismatch
(gds1 vs gm1) to net5, then is amplified by the second stage:
```
A_VSS_M6 = [gds6 · gds1 · gm7] / [2·(gm1 + gds1)·(gds3 + gds1)·(gds7 + gds8)]
```
Simplified (gm1 >> gds1):
```
A_VSS_M6 ≈ [gds6 · gds1 · gm7] / [2·gm1·(gds3 + gds1)·(gds7 + gds8)]
```

The M6 path dominates when gds6 is large (M6 near triode). For the
design in this repo, the M6 path is typically 3–5× larger than M8.

**Full PSRR⁻:**
```
PSRR⁻ = A0 / (A_VSS_M8 + A_VSS_M6)
```

The legacy single-path formula `PSRR⁻ = gm3·gm7 / [(gds3+gds1)·gds8]`
assumes the M6 path is negligible (valid only when gds6 << gds8, i.e.
M6 is deep in saturation with Vds >> Vov). **Do not use the single-path
formula when M6 Vds margin < 100 mV** — it overestimates PSRR⁻ by
10–20 dB.

Improving PSRR⁻: increase L5 (= L6) to raise ro6, or increase VDS_M6
headroom by raising gm/ID of the diff pair (reduces VGS_M3).

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
V_cm,min = Vov_M6 + VGS_M3 + VSS     (M6 saturation limit)
V_cm,max = VDD - |VSG_M1| + VTN       (M1 headroom limit)
```

### Node Capacitances

| Node | Devices at node | Capacitance |
|------|----------------|-------------|
| 1st_out (net5, gate M7) | M2 drain, M4 drain, M7 gate | `C1 = Cgs7 + Cdb2 + Cdb4 + Cgd2 + Cgd4` |
| Mirror (net1) | M1 drain/gate, M3 drain, M2 gate | `C2 = Cgs1 + Cgs2 + Cdb1 + Cdb3 + Cgd3` |
| Output (Vout) | M7 drain, M8 drain, CL | `CTL = CL + Cdb7 + Cdb8 + Cgd7 + Cgd8` |
