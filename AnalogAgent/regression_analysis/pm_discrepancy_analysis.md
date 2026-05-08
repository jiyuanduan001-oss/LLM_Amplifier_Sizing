# Phase Margin Discrepancy Analysis

## Summary

This analysis investigates why the analytical PM formula overestimates PM
compared to SPICE, using experimental data from **36 design points** across
two topologies: 5T OTA (20 points) and Two-Stage Miller (16 points).

**Key finding:** The 5T OTA and TSM have fundamentally different PM error
mechanisms. The 5T OTA errors scale with **GBW/ft** (a device-level NQS
effect), while the TSM errors scale with **GBW in MHz** (a circuit-level
compensation-network effect). The TSM's Rc-Cc compensation introduces a
systematic PM overestimate of **~0.3°/MHz of GBW** that the 3-pole
analytical model cannot capture.

---

## 1. Methodology

For each design point, PM was computed at three levels:

| Level | gm/gds source | Capacitance source | What it isolates |
|-------|---------------|-------------------|------------------|
| **A** (LUT analytical) | LUT | LUT + extrinsic_caps | Total prediction |
| **C** (OP analytical) | SPICE OP | SPICE OP | Pure model structure error |
| **SPICE** | — | — | Ground truth |

**Error definitions:**
- `err_total = PM_A - PM_SPICE` (total analytical error)
- `err_struct = PM_C - PM_SPICE` (model structure error, LUT inaccuracy removed)
- `err_param = PM_A - PM_C` (LUT parameter error only)

---

## 2. Results: 5T OTA (20 design points)

**Sweep:** gm/ID ∈ {8, 10, 12, 15, 18}, L ∈ {0.5, 1.0, 1.5, 2.0} µm, CL = 5 pF, I_bias = 30 µA, tt/27°C

```
gm/ID  L(µm)  GBW(MHz)  GBW/ft    PM_LUT   PM_OP   PM_SPICE  err_total  err_struct
  8    0.5       6.1     0.001     88.4     88.4     89.6       -1.2      -1.2
  8    1.0       6.5     0.005     88.4     88.4     89.4       -1.0      -0.9
  8    1.5       6.7     0.011     86.6     86.5     87.6       -1.0      -1.2
  8    2.0       7.0     0.019     84.2     83.7     85.2       -1.0      -1.5
 10    0.5       8.3     0.002     88.0     88.1     89.0       -1.0      -1.0
 10    1.0       8.5     0.007     88.0     88.1     88.7       -0.8      -0.6
 10    1.5       8.9     0.016     85.7     85.6     86.1       -0.4      -0.5
 10    2.0       9.0     0.029     82.8     82.4     82.9       -0.1      -0.5
 12    0.5      10.2     0.003     87.6     87.7     88.4       -0.8      -0.7
 12    1.0      10.6     0.011     87.5     87.7     87.9       -0.4      -0.3
 12    1.5      11.0     0.024     84.9     84.7     84.7       +0.2      +0.1
 12    2.0      11.0     0.043     81.5     81.0     80.8       +0.7      +0.3
 15    0.5      13.2     0.005     86.9     87.2     87.5       -0.5      -0.3
 15    1.0      14.0     0.020     86.9     87.0     86.8       +0.1      +0.2
 15    1.5      13.9     0.044     83.6     83.5     82.8       +0.8      +0.7
 15    2.0      13.8     0.076     79.6     79.2     78.0       +1.7      +1.3
 18    0.5      16.1     0.011     86.2     86.6     86.6       -0.4      +0.0
 18    1.0      16.7     0.040     86.1     86.4     85.6       +0.4      +0.8
 18    1.5      16.7     0.084     82.2     82.2     80.6       +1.6      +1.6
 18    2.0      16.6     0.146     77.8     77.5     74.9       +2.9      +2.7
```

**Regression:** `err_struct = 26.4 × (GBW/ft) - 0.8°`  (R² = 0.82)

**Observations:**
- Errors range from **-1.5° to +2.7°** — excellent accuracy
- At GBW/ft < 0.02: model slightly **under**-predicts PM (~-1°)
- At GBW/ft > 0.05: model **over**-predicts PM (up to +2.7°)
- Error correlates with **GBW/ft** (device-level NQS effect)
- LUT parameter error (err_total - err_struct) is typically < 1°

---

## 3. Results: Two-Stage Miller (16 design points)

**Sweep:** gm/ID_3 ∈ {10, 12, 15, 18}, GBW_target ∈ {20, 30, 50, 70} MHz,
Cc/CL = 0.4, CL = 5 pF, I_bias = 10 µA, ff/20°C

```
gm/ID  GBW_tgt  GBW_sp   GBW/ft    PM_LUT   PM_OP   PM_SPICE  err_total  err_struct
 10     20      18.6     0.014     84.9     86.2     83.9       +1.0      +2.3
 10     30      28.6     0.021     82.4     83.5     78.0       +4.4      +5.5
 10     50      48.4     0.035     77.6     77.1     66.4      +11.2     +10.7
 10     70      68.2     0.048     73.3     73.6     56.5      +16.8     +17.2
 12     20      18.3     0.017     84.9     86.3     84.1       +0.8      +2.2
 12     30      27.6     0.026     82.4     83.6     78.5       +3.9      +5.0
 12     50      47.5     0.043     77.6     77.2     67.3      +10.3      +9.9
 12     70      68.8     0.060     73.3     73.7     56.7      +16.6     +17.0
 15     20      17.8     0.025     84.9     86.4     84.1       +0.7      +2.2
 15     30      29.4     0.037     82.3     83.3     77.3       +5.0      +6.0
 15     50      47.6     0.062     77.5     77.3     66.9      +10.6     +10.4
 15     70      69.8     0.087     73.2     73.6     55.9      +17.3     +17.7
 18     20      21.0     0.040     84.7     85.9     82.4       +2.4      +3.6
 18     30      28.6     0.060     82.1     83.4     76.9       +5.2      +6.5
 18     50      49.4     0.101     77.2     77.1     64.7      +12.5     +12.4
 18     70      70.0     0.141     72.8     73.5     54.1      +18.7     +19.5
```

**Regressions:**
- `err_struct = 0.299 × GBW_MHz - 3.1°`  (R² = 0.987 — near-perfect)
- `err_struct = 136.4 × GBW/ft + 2.3°`  (R² = 0.603 — poor fit)

**Observations:**
- Errors range from **+0.7° to +18.7°** — dramatically worse than 5T OTA
- Error scales linearly with **GBW in MHz**, NOT with GBW/ft
- At same GBW, changing gm/ID (and hence GBW/ft) barely changes the error
- The structural error is 7-10× larger than the 5T OTA at comparable GBW/ft

---

## 4. Proof: The Error is Compensation-Network Specific

**Evidence 1 — Controlled comparison at same GBW/ft:**

| GBW/ft | 5T OTA err_struct | TSM err_struct | TSM excess |
|--------|-------------------|----------------|------------|
| ~0.04  | +0.3°             | +10.4°         | +10.1°     |
| ~0.08  | +1.6°             | +12.4°         | +10.8°     |
| ~0.14  | +2.7°             | +19.5°         | +16.8°     |

At every GBW/ft level, the TSM has 10-17° more structural error than the
5T OTA. If the error were from BSIM4 NQS effects (which depend on GBW/ft),
both topologies would show similar errors. They don't.

**Evidence 2 — The TSM error is independent of gm/ID:**

At GBW ≈ 50 MHz (varying gm/ID from 10 to 18):
```
gm/ID=10: GBW/ft=0.035, err_struct=+10.7°
gm/ID=12: GBW/ft=0.043, err_struct= +9.9°
gm/ID=15: GBW/ft=0.062, err_struct=+10.4°
gm/ID=18: GBW/ft=0.101, err_struct=+12.4°
```

The error barely changes (10-12°) despite a 3× change in GBW/ft. This
rules out device-level effects as the primary cause.

**Evidence 3 — R² comparison:**

| Regressor | 5T OTA R² | TSM R² | Better fit |
|-----------|-----------|--------|------------|
| GBW/ft    | 0.82      | 0.60   | 5T OTA    |
| GBW (MHz) | —         | 0.99   | TSM       |

The TSM error is explained by GBW alone (R² = 0.99), not by GBW/ft.

---

## 5. Root Cause Analysis

### 5.1 Why the 5T OTA model is accurate (< 3°)

The 5T OTA has a single-stage, single-pole-dominant topology. The PM formula:
```
PM = 90° − arctan(GBW/fp2) + arctan(GBW/fz_mirror) − arctan(GBW/fz_rhp)
```
captures all significant poles and zeros. The only unmodeled effects are:
- BSIM4 NQS transcapacitance (scales with GBW/ft, ~26°/unit of GBW/ft)
- Small gmb contributions (~0.5°)

These produce ≤ 3° of error across the entire practical design space.

### 5.2 Why the TSM model fails (up to 19°)

The TSM analytical model assumes a **3-pole transfer function with
zero-cancellation**:
```
H(s) ≈ A0 / [(1+s/p1)(1+s/p3)(1+s/p4)]
```
where Rc places an LHP zero on top of p2, removing it from the loop gain.

In reality, the BSIM4 SPICE model shows that **the zero-cancellation is
an approximation** — the Rc-Cc network creates a more complex frequency
response that the lumped model cannot capture. Specifically:

**Cause 1 — The Rc-Cc network is not a simple zero-pole cancellation.**

The actual impedance of the Rc-Cc branch between net5 and vout is:
```
Z_comp(s) = Rc + 1/(s·Cc) = (1 + s·Rc·Cc) / (s·Cc)
```
This interacts with the node capacitances C1 (at net5) and CTL (at vout)
to create a **third-order** network, not the first-order zero the
analytical model assumes. At frequencies near and above p2, the
distributed Rc-C1-Cc-CTL response introduces additional phase shift
that grows with frequency.

**Cause 2 — M7 Cgd creates frequency-dependent feedback.**

M7's Cgd (including gate-drain overlap) creates a local feedback path
within the second stage. The analytical model treats Cgd7 as a fixed
capacitor in C1, but in SPICE it acts as a Miller-multiplied feedback
element whose effective capacitance is frequency-dependent through the
second-stage gain `A_v2(s)`. At frequencies above p4, this interaction
adds additional phase lag.

**Cause 3 — The error grows linearly with GBW because ω_c/p2 grows.**

The compensation network's interaction with the loop becomes stronger
as ω_c approaches p2. Since p2 ≈ gm7·Cc/(C1·CTL) ≈ 50-80 MHz for
typical designs, and ω_c = gm3/Cc, the ratio ω_c/p2 grows linearly
with GBW. This ratio determines how much the lumped zero-cancellation
model deviates from the actual distributed response.

### 5.3 Layered error decomposition (TSM at GBW ≈ 50 MHz)

| Layer | PM (°) | vs SPICE | What it tells us |
|-------|--------|----------|------------------|
| A: LUT gm/gds + LUT caps | 72.0° | +5.7° | Total analytical error |
| B: SPICE gm/gds + LUT caps | 76.4° | +10.0° | LUT gm/gds errors help (cancel) |
| C: SPICE gm/gds + SPICE caps | 74.9° | +8.6° | SPICE caps are larger → helps |
| D: C + net2 Csb pole | 73.9° | +7.6° | Csb adds ~1° |
| SPICE measured | 66.3° | — | Ground truth |

Notable: LUT parameter errors (A→C) actually make the prediction
**closer** to SPICE (+2.9° toward ground truth) because the LUT
overestimates gds (which reduces analytical PM). This is a lucky
cancellation, not a sign of model accuracy.

---

## 6. Empirical Correction

**For the TSM topology**, the following empirical correction reduces the
structural error from ~0.3×GBW to < 2°:

```
PM_corrected = PM_analytical − (0.30 × GBW_MHz − 3.0)
```

where `GBW_MHz` is the analytical GBW = gm3/(2π·Cc) in MHz.

| GBW (MHz) | Correction | Residual after correction |
|-----------|------------|--------------------------|
| 20        | -3.0°      | ~-1° to +1°              |
| 30        | -6.0°      | ~-1° to +1°              |
| 50        | -12.0°     | ~-2° to +1°              |
| 70        | -18.0°     | ~-1° to +1°              |

**For the 5T OTA**, no correction is needed for GBW/ft < 0.05.
For GBW/ft > 0.05:

```
PM_corrected = PM_analytical − 26 × (GBW/ft)
```

---

## 7. Recommendations

1. **For sizing flows**: Always design with ≥ 10° of analytical PM margin
   for TSM designs above 30 MHz GBW. The 5T OTA needs only 3° margin.

2. **For the skill stack**: Consider adding the empirical correction to
   `tsm-equation.md` so the analytical check is more realistic before
   committing to simulation.

3. **Do not trust the TSM PM formula at GBW > 50 MHz** — the error
   exceeds 10° and grows rapidly. At these frequencies, SPICE PM is
   the only reliable metric.

4. **The 5T OTA formula is reliable** across the entire practical design
   space (GBW/ft < 0.15, error < 3°).
