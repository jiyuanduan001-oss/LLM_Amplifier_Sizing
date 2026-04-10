# 5T OTA Equations

## Circuit Structure

```
         VDD
          |
    ┌─────┤─────┐
    M6    |     M5        ← LOAD (PFET current mirror)
    |     |     |
    └──┬──┘     └──── Vout ── CL ── GND
       |   |
       M2  M1            ← DIFF_PAIR (NFET input pair)
       └─┬─┘
         |
         M3               ← TAIL (NFET tail current source)
         |
        GND

    M4 (diode-connected NFET) ← BIAS_REF, mirrors to M3

Nodes:
  vout   (output)  : drain M1, drain M5
  net1   (mirror)  : drain M2, drain M6 (= gate M6 = gate M5)
  net2   (tail)    : source M1, source M2, drain M3
  net3   (bias)    : gate M3, gate M4 (= drain M4)
```

| Role | Device | Drain at | Circuit function |
|------|--------|----------|-----------------|
| DIFF_PAIR | M1 | vout (output) | Output-side input transistor |
| DIFF_PAIR | M2 | net1 (mirror) | Mirror-side input transistor |
| LOAD | M5 | vout (output) | Mirror follower load |
| LOAD | M6 | net1 (mirror) | Diode-connected mirror reference |
| TAIL | M3 | net2 (tail) | Tail current source |
| BIAS_REF | M4 | net3 (bias) | Diode-connected bias reference |

Matching: M1 ≡ M2 (same W, L, M), M5 ≡ M6 (same W, L, M).
M3/M4 share L; mirror ratio set by finger count (M3_M / M4_M).

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

Since M1 ≡ M2: `gm1 = gm2`, `gds1 = gds2`, `Cgs1 = Cgs2`, `Cgd1 = Cgd2`.
Since M5 ≡ M6: `gm5 = gm6`, `gds5 = gds6`, `Cgs5 = Cgs6`, `Cgd5 = Cgd6`.

⚠️ LUT `vov` for PFET may return Vgs instead of Vov. Use `vov ≈ 2/(gm/ID)`
as an analytical estimate if the LUT value seems unreasonable (|vov| > 0.5V).

---

## Equations

All values are computable from the LUT except noise parameters (Kf, Cox, µ)
which are process-dependent and evaluated by the simulator.

### DC Gain

`A0 = gm1 / (gds1 + gds5)`

To select L during initial sizing: sweep L, query `gm_gds` for nfet,
pick L where `gm_gds_M1 / 2 ≥ A0_target` (rough estimate assuming gds1 ≈ gds5).
Then compute the exact A0 once all devices are sized.

### GBW

`GBW = gm1 / (2π × C_out)`

where `C_out = CL + Cgd1 + Cgd5`

### Dominant Pole

`fp1 = (gds1 + gds5) / (2π × C_out)`

### Mirror Pole-Zero Doublet

The current mirror creates both a pole and an LHP zero. The direct path
(M1 → vout) is instantaneous; the mirror path (M2 → net1 → M5 → vout) is
delayed by C_mirror. This gives the transfer function a factor:

`H_mirror(s) = (1 + s/(2·ω_p)) / (1 + s/ω_p)`

where `C_mirror = Cgs5 + Cgs6 + Cgd2`

Mirror pole: `fp2 = gm6 / (2π × C_mirror)`
Mirror zero (LHP): `fz2 = 2 × fp2 = gm6 / (π × C_mirror)`

The zero is at exactly 2× the pole. It partially cancels the pole in
magnitude response but causes a slow settling component in step response.

PM design rule: fp2 > 2.2 × GBW for PM ≥ 60°.

### Phase Margin

`PM = 90° - arctan(GBW/fp2) + arctan(GBW/fz2)`

No RHP zeros (no Miller cap).

### Slew Rate

`SR = I_tail / CL`

⚠️ SR+ and SR- are NOT equal in practice. The mirror node settling time
creates asymmetry. SPICE measures both separately; the analytical formula
is an upper bound for the faster direction.

### Output Swing

`V_out,min = Vov_M1`
`V_out,max = VDD - |Vov_M5|`
`V_swing = VDD - Vov_M1 - |Vov_M5|`

Testbench measures swing as the range where |Vout - Vin| < 10mV in
unity-gain feedback, which is tighter than the analytical Vov bounds.

### Thermal Noise (input-referred)

`S_thermal² = (16kT)/(3·gm1) × [1 + gm5/gm1]`

In the 5T OTA, ID5 = ID1, so gm5/gm1 ≈ 0.5–1.0. The load contribution
is NOT negligible.

### 1/f Noise (input-referred)

`S_1f² = (2·Kf_n)/(Cox·W1·L1·f) × [1 + (Kf_p·µp·W1·L1)/(Kf_n·µn·W5·L5) × (gm5/gm1)²]`

### Integrated Noise

`V²_noise = S_1f² × ln(fH/fL) + S_thermal² × (fH - fL)`

Testbench integrates from 0.1 Hz to 1 GHz.

### CMRR

`Acm ≈ -1 / (2·gm5·ro3)` where `ro3 = 1/gds3`
`CMRR = |A0 / Acm| ≈ 2·gm1·gm5·Rout·ro3`

where `Rout = 1/(gds1+gds5)`. Design knob: increase L3 to improve ro3.

### PSRR⁺ (VDD coupling)

`Add ≈ 1` (PMOS mirror source sits on VDD, output follows VDD directly)
`PSRR⁺ = |A0 / Add| ≈ A0`

PSRR⁺ is limited by the DC gain.

### PSRR⁻ (VSS coupling)

`Ass ≈ 1 / (2·gm5·ro3)`
`PSRR⁻ = |A0 / Ass| ≈ 2·gm1·gm5·Rout·ro3 ≈ CMRR`

PSRR⁻ ≈ CMRR at low frequency. Design knob: increase L3.

### CM Input Range

`V_cm,min = Vov_M3 + Vth_n + Vov_M1` (M3 saturation limit)
`V_cm,max = VDD - |Vsg_M5| + Vth_n` (M5 diode, always saturated)

### Node Capacitances

| Node | Devices at node | Capacitance |
|------|----------------|-------------|
| Output (vout) | M1 drain, M5 drain | `C_out = CL + Cgd1 + Cgd5` |
| Mirror (net1) | M2 drain, M6 drain/gate, M5 gate | `C_mirror = Cgs5 + Cgs6 + Cgd2` |
