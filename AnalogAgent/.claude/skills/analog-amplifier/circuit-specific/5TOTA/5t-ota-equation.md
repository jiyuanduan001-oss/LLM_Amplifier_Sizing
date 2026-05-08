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

    M4 (diode-connected NFET) ← BIAS_GEN, mirrors to M3

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
| BIAS_GEN | M4 | net3 (bias) | Diode-connected bias reference |

Matching: M1 ≡ M2 (same W, L, M), M5 ≡ M6 (same W, L, M).
M3/M4 share L; mirror ratio set by multiplier (M3_M / M4_M).

---

## Symbol Definitions — LUT Derivation

Once **(gm, L, gm/ID)** are determined for a device (see design-flow),
all remaining parameters are derived from the LUT.

**LUT units:** id_w is stored in A/m (= µA/µm), cgs_w/cgd_w/cdb_w in F/m, ft in Hz, vgs/vth/vdsat in V.
Ensure unit consistency when mixing SI-derived values (gm in S, ID in A) with LUT values.

```
LUT query format: lut_query(device_type, metric, L, corner=corner, temp=temp_str, gm_id_val=gm_id)
  where temp is a string like '27C', '40C' — NOT a bare integer.

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

⚠️ W = ID / id_w yields **meters** (not µm). Display as W×1e6 for µm.
Cgs = cgs_w × W needs NO extra 1e-6 factor.

Since M1 ≡ M2: `gm1 = gm2`, `gds1 = gds2`, `Cgs1 = Cgs2`, `Cgd1 = Cgd2`, `Cdb1 = Cdb2`.
Since M5 ≡ M6: `gm5 = gm6`, `gds5 = gds6`, `Cgs5 = Cgs6`, `Cgd5 = Cgd6`, `Cdb5 = Cdb6`.

---

## Equations

All values are computable from the LUT except noise parameters (Kf, Cox, µ)
which are process-dependent and evaluated by the simulator.

### Sub-Block Abstraction for the LOAD

The LOAD role (M5/M6) may be a single transistor, a regular cascode, or a
low-voltage cascode. All small-signal gain and pole equations below use
the sub-block's effective quantities (see
`general/knowledge/mirror-load-structures.md`):

| Symbol | single | cascode / lv_cascode |
|--------|--------|----------------------|
| `gds_eq_LOAD` | `gds5` | `(gds5 × gds_cas) / gm_cas` |
| `C_eq_LOAD` (at output) | `Cgd5 + Cdb5` | `Cgd_cas + Cdb_cas` |
| `p_int_LOAD` | none | `gm_cas / C_int_LOAD` |
| `C_int_LOAD` | — | `Cgs_cas + Cdb5 + Cgd5` |

Substitute these into the equations below. The cascode variants boost
`ro_eq_LOAD = 1/gds_eq_LOAD` by a factor of `gm_cas / gds_cas` (the
intrinsic gain of the cascode device), raising A0 by the same factor.

### Sub-Block Abstraction for the TAIL

Parallel structure to LOAD. The TAIL role (M3) is the mirror of the
diode-connected BIAS_GEN (M4); `ID3 = I_tail = (M3_M/M4_M)·I_bias`.

The sub-block type (detected during circuit-understanding) selects both
the equivalent output conductance seen by the diff-pair source (net2)
AND the headroom consumed from VSS → net2:

| Symbol | single | cascode / lv_cascode |
|--------|--------|----------------------|
| `gds_eq_TAIL` | `gds3` | `(gds3 × gds_tcas) / gm_tcas` |
| `V_headroom_TAIL` (VSS→net2) | `vdsat3` | `vdsat3 + vdsat_tcas` |

where `M_tcas` is the cascode companion (role `TAIL_CAS`). Sizing for
the cascode companion is in the design flow (same pattern as LOAD_CAS).

For the lv_cascode variant, the cascode gate is an external bias port
(`Vbias_cas_n`) on the top-level subcircuit, computed as:

`Vbias_cas_n = vdsat3 + vdsat_tcas + vth_tcas`

(NMOS rail = VSS, both vdsat values positive magnitudes). The sizing
flow emits this as the `extra_ports` value when registering the
topology.

Substitute `gds_eq_TAIL` wherever `gds3` appears in CMRR/PSRR⁻ equations,
and substitute `V_headroom_TAIL` wherever `vdsat3` appears in CM-range
equations. The cascode variants boost `ro_eq_TAIL = 1/gds_eq_TAIL` by a
factor of `gm_tcas/gds_tcas`, directly improving CMRR and PSRR⁻ by the
same factor.

### DC Gain

`A0 = gm1 / (gds1 + gds_eq_LOAD)`

To select L during initial sizing (single load): sweep L, query `gm_gds`
for nfet, pick L where `gm_gds_M1 / 1.5 ≥ A0_target` (rough estimate;
load L is chosen separately in Step 2). For cascode loads, a much shorter
L1 can still meet gain because `gds_eq_LOAD << gds5`.

### Poles, Zeros, GBW, and Phase Margin

Derived from the full small-signal transfer function H(s) = N(s)/D(s)
via KCL at all nodes with all parasitic capacitances. See
`5tota-transfer-function.md` for the complete derivation.

#### Node Capacitances

The pole/zero locations depend on the total capacitance at each node.
These change with the LOAD sub-block type:

**Single load:**
```
C1 = CL + Cdb1 + Cdb5 + Cgd1 + Cgd5               (at vout)
C2 = Cdb2 + Cdb6 + Cgs5 + Cgs6 + Cgd2 + Cgd5      (at net1)
G1 = gds1 + gds5
G2 = gds2 + gm6 + gds6
```

**Cascode / LV-cascode load** (M_cas between M_main and output):
```
C1 = CL + Cdb1 + Cdb_cas + Cgd1 + Cgd_cas          (at vout — M_cas drain-side caps)
C2 = Cdb2 + Cdb6 + Cgs5 + Cgs6 + Cgd2 + Cgd_cas   (at net1)
C_int = Cgs_cas + Cdb5 + Cgd5                        (at internal cascode node)
G1 = gds1 + gds_eq_LOAD
G2 = gds2 + gm6 + gds6
```

#### Poles

**Dominant pole (at vout):**
```
fp1 = G1 / (2π·C1) = (gds1 + gds_eq_LOAD) / (2π·C1)
```

**Mirror pole (at net1):**
```
fp2 = G2 / (2π·C2) = (gm6 + gds6 + gds2) / (2π·C2)
```

**Cascode internal pole** (only for cascode/lv_cascode load):
```
p_int_LOAD = (gm_cas + gmb_cas) / C_int  ≈  gm_cas / C_int
```

#### Zeros

**Mirror zero (LHP):**
```
C_mir = C2 − Cgd5 = Cdb2 + Cdb6 + Cgs5 + Cgs6 + Cgd2
fz_mirror = (gm5 + gm6) / (2π·C_mir)  ≈  2 × fp2
```

**Cgd feedforward zero (RHP):**
```
fz_rhp = gm1 / (2π·Cgd1)
```

This RHP zero arises from the Cgd1 feedforward path from input (vinn)
to output (vout). It adds negative phase at frequencies approaching ft.

#### GBW

```
GBW = gm1 / (2π·C1)
```

**⚠️ GBW / ft validity:** This formula and the PM formula below are
valid only when GBW < ft for all signal-path devices. Check ft of M1
and M5 after sizing — if GBW/ft > 0.3, the analytical PM will be
optimistic (see `lut-parameter-derivation.md` GBW/ft table).

#### Phase Margin

```
PM = 90° − arctan(GBW/fp2) + arctan(GBW/fz_mirror) − arctan(GBW/fz_rhp)
```

With cascode/lv_cascode load, add the internal pole penalty:
```
PM -= arctan(2π·GBW / p_int_LOAD)
```

### Slew Rate

```
SR = I_tail / (CL + Cdb1 + Cdb5 + Cgd5)
```

The output node parasitic capacitances (Cdb1, Cdb5, Cgd5) must be
charged along with CL during slewing. Use `SR = I_tail / CL` only
when parasitics are negligible compared to CL.

⚠️ SR+ and SR- are NOT equal in practice. SPICE measures both
separately.

### Output Swing

Depends on the LOAD sub-block type (`V_headroom_LOAD` from the sub-block):

| LOAD type  | V_out,max                              | V_swing contribution |
|------------|----------------------------------------|---------------------|
| single     | `VDD - vdsat_M5`                       | `vdsat_M5`          |
| cascode    | `VDD - (vdsat_M5 + |Vgs_cas|)`         | `|Vgs + vdsat|` (high)|
| lv_cascode | `VDD - (vdsat_main + vdsat_cas)`       | `vdsat_main + vdsat_cas` (low)|

`V_out,max = VDD - V_headroom_LOAD`
`V_out,min = V_headroom_TAIL + Vdsat_M1`
`V_swing   = VDD - V_headroom_LOAD - V_headroom_TAIL - Vdsat_M1`

Testbench measures swing as the range where |Vout - Vin| < 10mV in
unity-gain feedback, which is tighter than the analytical Vdsat bounds.

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

`Acm ≈ -1 / (2·gm5·ro_eq_TAIL)` where `ro_eq_TAIL = 1/gds_eq_TAIL`
`CMRR = |A0 / Acm| ≈ 2·gm1·gm5·Rout·ro_eq_TAIL`

where `Rout = 1/(gds1+gds_eq_LOAD)`.

**Warning: overestimates by 20–30 dB for single-ended 5T OTA.**
The mirror provides strong CM cancellation, but body effect on M1/M2
(gmb/gm ≈ 0.2) and DC Vds asymmetry (M1 at high-Z vout vs M2 at
low-Z diode) limit practical CMRR to **50–65 dB** in SKY130.
Use SPICE for accurate values. PSRR⁻ is not similarly affected
(see note below).

### PSRR⁺ (VDD coupling)

`Add ≈ 1` (PMOS mirror source sits on VDD, output follows VDD directly)
`PSRR⁺ = |A0 / Add| ≈ A0`

PSRR⁺ is limited by the DC gain.

### PSRR⁻ (VSS coupling)

`Ass ≈ 1 / (2·gm5·ro_eq_TAIL)`
`PSRR⁻ = |A0 / Ass| ≈ 2·gm1·gm5·Rout·ro_eq_TAIL ≈ CMRR`

PSRR⁻ ≈ CMRR at low frequency (per the formula above).

**Note:** Unlike CMRR, PSRR⁻ is NOT severely overestimated. VSS
perturbation enters via M1/M2 body (symmetric, absorbed by the tail
constraint as Vn adjusts) and M3/M4 (self-protected: M4 diode tracks
gnda, keeping M3 Vgs constant). The mirror has little residual to
cancel, so PSRR⁻ is typically 10–15 dB better than CMRR in SPICE.

### CM Input Range

`V_cm,min = V_headroom_TAIL + Vth_n + Vdsat_M1`
`V_cm,max = VDD - |Vsg_M5| + Vth_n` (M5 diode, always saturated)

### Node Capacitances

See the Poles/Zeros section above for complete C1, C2, C_int definitions
by LOAD sub-block type.

| Node | Devices at node | Capacitance (single load) |
|------|----------------|---------------------------|
| Output (vout) | M1 drain, M5 drain, CL | `C1 = CL + Cdb1 + Cdb5 + Cgd1 + Cgd5` |
| Mirror (net1) | M2 drain, M6 drain/gate, M5 gate | `C2 = Cdb2 + Cdb6 + Cgs5 + Cgs6 + Cgd2 + Cgd5` |
| Tail (net2) | M1 source, M2 source, M3 drain | `C3 = Cdb3 + Cgd3 + Cgs1 + Cgs2` |
| Cascode internal | M_main drain, M_cas source | `C_int = Cgs_cas + Cdb5 + Cgd5` |
