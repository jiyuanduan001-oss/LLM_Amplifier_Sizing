# TCO Equation Skill

## Purpose

Complete equation set for the Fully Differential Telescopic Cascode OTA (TCO),
organized by analysis branch. These are the specific equations needed
for the sizing flow — not abstract frameworks.

## Quick Reference — Which Branch for Which Spec

| Spec to analyze  | Branch | Key equation                      | Primary Role affected |
|-----------------|--------|-----------------------------------|-----------------------|
| DC gain (A0)     | §A     | A_v = Gm1 × Rout                 | DIFF_PAIR, NCAS, PCAS |
| GBW              | §C     | GBW = gm1/(2π·CL)                | DIFF_PAIR, CL         |
| Phase margin     | §C     | PM ≈ 90° - arctan(ω_c/p2)        | NCAS, PCAS (parasitic poles) |
| Poles/zeros      | §B     | p1, p2, p3 expressions           | All Roles via caps    |
| Slew rate        | §D     | SR = I_tail / CL                  | TAIL, CL              |
| Noise            | §E     | S_in² = f(gm1, gm3, gm5, gm7)   | DIFF_PAIR, PCAS, NCAS |
| CMRR             | §F     | CMRR = gm1·Rout / (1/gm_tail·gds_tail) | TAIL         |
| PSRR             | §F     | PSRR from supply-to-output paths  | PCAS, TAIL            |
| Output swing     | §G     | Vov constraints per stacked device| All (4 stacked)       |
| CM input range   | §G     | ICMR from saturation constraints  | DIFF_PAIR, TAIL, PCAS |
| Bias currents    | (top)  | Mirror ratios from I_bias         | TAIL, BIAS_REF        |
| Power            | (top)  | P = VDD × I_tail                  | TAIL                  |
| Parasitic caps   | §H     | Cgs, Cgd, Cdb formulas           | All (for pole calc)   |

## Circuit Structure (Fully Differential)

```
                        VDD
                         |
         ┌───────────────┼───────────────┐
         |               |               |
        M7a             M9              M7b
      (PCAS_a)        (TAIL)          (PCAS_b)
     Vbp_cas─┤|         |          |├─Vbp_cas
         |               |               |
        M5a              |              M5b
      (PLOAD_a)          |           (PLOAD_b)
     Vbp─┤|              |          |├─Vbp
         |               |               |
  Voutp──┤         ┌─────┴─────┐         ├──Voutn
         |         |           |         |
        M3a       M1a         M1b       M3b
      (NCAS_a)  (DIFF_a)   (DIFF_b)  (NCAS_b)
     Vbn_cas─┤|  Vinp─┤|   |├─Vinn  |├─Vbn_cas
         |         |           |         |
        M11a       └─────┬─────┘        M11b
      (NLOAD_a)          |           (NLOAD_b)
     Vbn─┤|             M9b          |├─Vbn
         |            (TAIL_B)        |
         └───────────────┼───────────────┘
                         |
                        VSS

Roles:
  DIFF_PAIR    : M1a, M1b  (NMOS input differential pair)
  NCAS         : M3a, M3b  (NMOS cascode devices)
  PLOAD        : M5a, M5b  (PMOS current source load)
  PCAS         : M7a, M7b  (PMOS cascode devices)
  TAIL         : M9        (NMOS tail current source)
  NLOAD        : M11a, M11b (NMOS current source, for alternative topology)
  BIAS_REF     : Bias generation circuit (provides Vbp, Vbp_cas, Vbn, Vbn_cas)
  CMFB         : Common-mode feedback circuit (sets output CM level)
```

**Note on topology variants**: The canonical fully differential telescopic cascode
has NMOS input pair (M1), NMOS cascode (M3), PMOS cascode (M7), and PMOS load (M5).
All current flows through a single branch from VDD to VSS — this is the defining
feature that gives the telescopic topology its power efficiency advantage.

An alternative uses PMOS input pair — the analysis is dual (swap N↔P).

## Matching and Symmetry

```
M1a ≡ M1b : W1=W1, L1=L1            (input pair)
M3a ≡ M3b : W3=W3, L3=L3            (NMOS cascode)
M5a ≡ M5b : W5=W5, L5=L5            (PMOS load)
M7a ≡ M7b : W7=W7, L7=L7            (PMOS cascode)
```

## Bias Current Expressions

```
I_tail = I9                           [total tail current]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
ID1 = I_tail / 2                      [each input device]
ID3 = ID5 = ID7 = ID1                 [all devices in same branch carry same current]
```

**Key insight**: In a telescopic cascode, ALL devices in each half-circuit carry
the same drain current ID = I_tail/2. There is only one current path per branch.
This is the fundamental difference from a folded cascode, which has separate
bias currents for input and cascode branches.

## Quiescent Power

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
P = VDD × I_tail
```

Single-stage → only one bias current. This is the most power-efficient OTA topology.

---

## Branch A: Small-Signal Gain

### Transconductance (Gm)

```
Gm = gm1
```
The overall OTA transconductance equals the input pair transconductance.
Cascode devices do not contribute to Gm; they only boost output impedance.

### Output Resistance (Rout) — Fully Differential Half-Circuit

Each output node sees the parallel combination of the NMOS cascode output
impedance looking down and the PMOS cascode output impedance looking up:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout = Rout_ncas ∥ Rout_pcas
```

**NMOS cascode output impedance** (looking into drain of M3):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout_ncas = gm3·ro3·ro1
```
More precisely (including gds):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout_ncas = ro3·(1 + gm3·ro1) ≈ gm3·ro3·ro1
```
This is the impedance of the cascode M3 sitting on top of the input device M1.

**PMOS cascode output impedance** (looking into drain of M7):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout_pcas = gm7·ro7·ro5
```
More precisely:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout_pcas = ro7·(1 + gm7·ro5) ≈ gm7·ro7·ro5
```

**Total output resistance**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Rout = (gm3·ro3·ro1) ∥ (gm7·ro7·ro5)
```

### DC Gain

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v = Gm × Rout = gm1 × [(gm3·ro3·ro1) ∥ (gm7·ro7·ro5)]
```

**Design equation** (using intrinsic gain A_i = gm·ro from LUT):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v = gm1 × [(A_i3 · ro1) ∥ (A_i7 · ro5)]
```

**Simplified** (when NMOS and PMOS cascode impedances are comparable):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_v ≈ gm1 × (gm3·ro3·ro1) / 2
    = (gm1/gds1) × (gm3/gds3) / 2
    = A_i1 × A_i3 / 2
```

**Key insight**: DC gain of a telescopic cascode is proportional to (gm·ro)²,
compared to (gm·ro) for a simple differential pair, or (gm·ro)² for a
two-stage Miller. The single-stage telescopic achieves comparable gain to
a two-stage design without requiring compensation.

---

## Branch B: Poles, Zeros, and Transfer Function

### Single-Stage Transfer Function

The telescopic cascode is a single-stage amplifier with one dominant pole
at the output node:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
H(s) = A_v / (1 + s/p1) × 1/[(1 + s/p2)(1 + s/p3)]
```

### Dominant Pole (p1) — Output Node

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p1 = 1 / (Rout × CL_total)

where:
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  CL_total = CL + Cdb7a + Cdb3a + Cgd7a + Cgd3a + C_cmfb
           [load + parasitic drain caps at output + CMFB cap]
```

### Non-Dominant Pole (p2) — NMOS Cascode Source Node

This pole is at the source of the NMOS cascode device M3, which is also
the drain of the input pair M1:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p2 = gm3 / Cp2

where:
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  Cp2 = Cdb1 + Cgd1 + Csb3 + Cgs3
      [drain caps of M1 + source caps of M3]
```

**Key insight**: p2 is set by an NMOS transconductance (gm3) — this is why
the telescopic cascode has higher bandwidth than the folded cascode, where
the equivalent pole involves a PMOS transconductance (lower fT).

### Non-Dominant Pole (p3) — PMOS Cascode Source Node

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p3 = gm7 / Cp3

where:
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
  Cp3 = Cdb5 + Cgd5 + Csb7 + Cgs7
      [drain caps of M5 + source caps of M7]
```

Since PMOS devices have lower gm/C (lower fT), p3 < p2 typically.
p3 is usually the first non-dominant pole that limits phase margin.

### Additional Poles

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p4 = gm5 / Cgs5     [at gate of M5 if not bypassed by mirror]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p5 = gm_tail / C_tail [at source of input pair / drain of tail]
```

p5 is a common-mode pole (does not affect differential-mode response).
It matters for CMFB loop stability.

---

## Branch C: Bandwidth and Phase Margin

### Unity-Gain Bandwidth (GBW)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm1 / (2π · CL_total)
```

**No compensation capacitor is needed.** This is a major advantage of the
single-stage telescopic cascode — bandwidth is set directly by gm1/CL,
not gm1/Cc. For the same gm1, the telescopic achieves higher GBW than
a two-stage Miller (where GBW = gm1/(2π·Cc) and Cc ≈ 0.2–0.5 × CL).

### Phase Margin

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PM = 180° - arctan(ω_c/p1) - arctan(ω_c/p2) - arctan(ω_c/p3)
```

Since p1 << ω_c (dominant pole is well below GBW):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
arctan(ω_c/p1) ≈ 90°
```

**Simplified**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PM ≈ 90° - arctan(ω_c/p2) - arctan(ω_c/p3)
```

**PM design rule**: for 60° PM with two non-dominant poles:
- If p2 ≈ p3: each must be > 2.7 × ω_c
- If p2 >> p3: p3 alone must be > 2.2 × ω_c (same as single non-dominant pole)
- General: p2 > 3 × ω_c and p3 > 3 × ω_c gives comfortable margin

### 3-dB Bandwidth

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
f_3dB = 1 / (2π · Rout · CL_total) = p1 / (2π)
```

### Closed-Loop Bandwidth (unity-gain feedback, β = 1)

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
f_CL = GBW = gm1 / (2π · CL_total)
```

---

## Branch D: Slew Rate

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR = I_tail / CL_total
```

**Key insight**: In a telescopic cascode, the slew rate is symmetric:
- Positive slewing: M1a turns off, all of I_tail flows through M1b → charges CL
- Negative slewing: M1b turns off, all of I_tail flows through M1a → discharges CL

Both limited by the same current I_tail and load CL_total.

**SR vs GBW relationship**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
SR = I_tail / CL = 2 × ID1 / CL = 2 × (gm1 / gm_id_1) / CL

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
GBW = gm1 / (2π · CL)

→ SR = 2 × GBW × 2π / gm_id_1 = 4π × GBW / gm_id_1
```

For moderate inversion (gm/ID ≈ 12): SR ≈ GBW (in consistent units).
This means the telescopic cascode is naturally balanced between
small-signal and large-signal performance — no separate SR/GBW tradeoff.

---

## Branch E: Noise

### Input-Referred Noise PSD (Fully Differential)

For a fully differential telescopic cascode, the input-referred noise
power spectral density is:

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_in(f)² = S_thermal + S_flicker

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_thermal = (8kT/3) × (1/gm1) × [1 + gm5/gm1]

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
S_flicker  = (2Kf_n)/(Cox·W1·L1·f) × [1 + (Kf_p·µp·L1²)/(Kf_n·µn·L5²)]
```

**Noise contributors** (input-referred):
1. **Input pair M1a, M1b**: Direct noise contributor. Dominates.
2. **PMOS load M5a, M5b**: Contributes noise scaled by (gm5/gm1)².
3. **Cascode devices M3, M7**: Negligible noise contribution at low/mid
   frequencies. Cascode devices appear as common-gate stages — their noise
   current flows into low-impedance nodes and is divided by cascode gm.
4. **Tail current source M9**: Contributes only to common-mode noise.
   Rejected by differential operation and CMFB.

**Key insight**: The telescopic cascode has LOWER noise than the folded cascode
because:
- No additional bias current branch (no extra noise from folding devices)
- Same noise as a simple differential pair with active load
- Cascode devices contribute negligible noise

### Spot Noise Constraint at frequency f0

```
S_in(f0)² ≤ S²_max
```

### Total RMS Noise over band [f0, f1]

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V²_noise = S_flicker_coeff × ln(f1/f0) + S_thermal × (f1 - f0) ≤ V²_max
```

---

## Branch F: CMRR and PSRR

### CMRR

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
CMRR = A_dm / A_cm

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_dm = gm1 × Rout

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
A_cm ≈ gm1 / (2 × gm9 × ro9 × gm3 × ro3)
     [common-mode gain through tail source, attenuated by cascode]

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
CMRR ≈ 2 × gm9 × ro9 × gm3 × ro3 × Rout / Rout
     = 2 × (gm9·ro9) × (gm3·ro3)
```

**Simplified**: CMRR ≈ 2 × A_i,tail × A_i,ncas

The cascode structure provides an additional gm·ro factor of CMRR
improvement compared to a simple differential pair.

### PSRR (VDD)

At low frequencies, supply noise couples through the PMOS cascode stack:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PSRR_VDD ≈ A_v × gds5 / gm5
         = gm1 × Rout × (gds5/gm5)
```
The PMOS cascode greatly attenuates supply noise coupling.

### PSRR (VSS)

Supply noise on VSS couples through the tail current source:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
PSRR_VSS ≈ gm1 × Rout × (gds9/gm9) × (gds3/gm3)
```

---

## Branch G: Bias and Saturation Constraints (Output Swing & ICMR)

### Output Voltage Swing

This is the CRITICAL limitation of the telescopic cascode. Four devices
are stacked between VDD and VSS on each output branch:

```
V_out,max = VDD - |Vov5| - |Vov7|
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = Vov11 + Vov3
```

If using the standard topology (no separate NLOAD):
```
V_out,max = VDD - |Vov_PLOAD| - |Vov_PCAS|
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_out,min = Vov_NCAS + Vov_input_pair_drain_node
```

More precisely, the constraint is that each device stays in saturation:

**M7 (PCAS)**: VSD7 ≥ |Vov7|
```
VDD - V_bias_pcas_source ≥ |Vov7|
→ V_out,max ≤ VDD - |Vov5| - |Vov7|
```

**M3 (NCAS)**: VDS3 ≥ Vov3
```
V_out - V_source_M3 ≥ Vov3
→ V_out,min ≥ Vov1 + Vov3  (where Vov1 = VDS of M1 at minimum)
```

**Output swing** (peak-to-peak differential):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_swing = (V_out,max - V_out,min) × 2   [fully differential]
        = 2 × [VDD - |Vov5| - |Vov7| - Vov3 - Vov1]
```

### Input Common-Mode Range (ICMR)

**Maximum V_cm**:
```
V_cm,max = VDD - |Vov9_tail_equivalent| - |VGS5| - |Vov7| + VGS1
```
More practically (NMOS input pair):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm,max = V_out,max + VTN + Vov1
         [input pair gate must not push M1 drain above where M3 can cascode]
```

**Minimum V_cm**:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
V_cm,min = VSS + Vov_tail + VGS1
         = VSS + Vov9 + VTN + Vov1
```

**ICMR** is NARROWER than the folded cascode because the input pair drain
is directly connected to the cascode — no decoupling between input CM and
output CM levels.

**Key insight**: The telescopic cascode CANNOT operate in unity-gain feedback
configuration in most processes because V_out,CM ≠ V_in,CM. The output CM
is typically higher than the input CM (for NMOS input pair), making unity-gain
connection impossible. This is why telescopic cascodes are used primarily in
switched-capacitor circuits where the feedback factor β < 1.

---

## Branch H: Parasitic Capacitance Expressions

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Cgs = (2/3)·W·L·Cox + W·LD·Cox           [gate-source]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Cgd = Cox·W·LD                             [gate-drain overlap]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Cdb = Cj·Ls·W + Cjsw·(2·Ls+W)            [drain-bulk, at estimated bias]
     divided by (1 + VDB/ψ0)^0.5
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Csb = Cj·Ls·W + Cjsw·(2·Ls+W)            [source-bulk]
     divided by (1 + VSB/ψ0)^0.5
```

### Key Capacitance Nodes

**Output node** (determines p1):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
C_out = CL + Cdb3 + Cgd3 + Cdb7 + Cgd7 + C_cmfb
```

**NMOS cascode source node** (determines p2):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Cp2 = Cdb1 + Cgd1 + Csb3 + Cgs3
```

**PMOS cascode source node** (determines p3):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
Cp3 = Cdb5 + Cgd5 + Csb7 + Cgs7
```

---

## CMFB Considerations

The fully differential telescopic cascode REQUIRES a common-mode feedback
circuit to set the output CM level. Without CMFB, the output CM is undefined
(high-impedance node with no DC path to set the level).

### CMFB Requirements
1. Sense output CM: V_cm,out = (Voutp + Voutn) / 2
2. Compare to reference: V_cm,ref (typically set to mid-swing)
3. Feed back to bias: adjust tail current or PMOS load gate voltage

### CMFB Implementation Options
- **Resistive sensing**: Two large resistors from Voutp/Voutn to sense node.
  Simple but loads output (reduces Rout and swing).
- **Switched-capacitor CMFB**: Standard for SC applications. Does not load
  output in the signal phase. Adds clock feedthrough.
- **Continuous-time CMFB**: Uses auxiliary differential pair. Consumes extra
  power and may limit output swing.

### CMFB Loop Stability
The CMFB loop has its own gain and poles. The common-mode output pole is:
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
p_cm = 1 / (R_out,cm × C_out)

```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
R_out,cm ≈ 1 / (gm5 × gm7 × ro7)  [much lower than differential Rout]
```

The CMFB loop is typically much faster than the differential signal path
because the common-mode output resistance is much lower.
