# LUT Parameter Derivation Template

## Purpose

Standard procedure to derive all small-signal parameters for a single
device from the gm/ID LUT. Called by the design flow once per role
during initial sizing.

---

## Inputs

| Input | Description |
|-------|-------------|
| `device_type` | `'nfet'` or `'pfet'` |
| `gm_id` | Target gm/ID operating point (S/A) |
| `L` | Channel length (µm) |
| `ID` | Drain current (A) — total current the device carries |
| `corner` | Process corner (e.g. `'tt'`) |
| `temp` | Temperature string (e.g. `'27C'`) |

---

## Procedure

Given (device_type, gm_id, L, ID, corner, temp), derive all parameters:

```
gm     = gm_id × ID

id_w   = lut_query(device_type, 'id_w',  L, corner=corner, temp=temp, gm_id_val=gm_id)   # A/m
W      = ID / id_w                                                                         # m (display as W×1e6 for µm)

gds    = gm / lut_query(device_type, 'gm_gds', L, corner=corner, temp=temp, gm_id_val=gm_id)
ft     = lut_query(device_type, 'ft',     L, corner=corner, temp=temp, gm_id_val=gm_id)    # Hz
vdsat  = lut_query(device_type, 'vdsat',  L, corner=corner, temp=temp, gm_id_val=gm_id)    # V

Cgs    = lut_query(device_type, 'cgs_w', L, corner=corner, temp=temp, gm_id_val=gm_id) × W  # F
Cgd    = lut_query(device_type, 'cgd_w', L, corner=corner, temp=temp, gm_id_val=gm_id) × W  # F
Cdb    = lut_query(device_type, 'cdb_w', L, corner=corner, temp=temp, gm_id_val=gm_id) × W  # F
```

## Units

- `id_w` is in A/m; `W = ID / id_w` gives meters (not µm)
- `cgs_w`, `cgd_w`, `cdb_w` are in F/m; multiply by W (in meters) directly — no extra 1e-6 factor
- `vdsat` is the BSIM4 |Vds|_sat (positive magnitude)

## Extrinsic Capacitance Correction

The LUT cgd_w and cdb_w capture only **intrinsic** small-signal values.
The BSIM4 model adds extrinsic terms that dominate for node capacitance
calculations (poles, PM, SR). Always add these after deriving intrinsic caps:

```
from scripts.lut_lookup import extrinsic_caps

ex = extrinsic_caps(device_type, W, M=M)  # W in meters, M = multiplier count

# Cgd: add gate-drain overlap (dominates in saturation, intrinsic ≈ 0)
Cgd_total = Cgd + ex['cgd_ov']

# Cdb: use LUT value directly (no correction needed)
Cdb_total = Cdb    # = cdb_w × W from LUT

# Cgs: no correction needed (LUT cgs_w captures most gate charge)
```

**Why Cgd correction matters:**
Cgd_intrinsic ≈ 0 in saturation (channel charge partition). The physical
gate-drain overlap (cgdo × W) is 10–80× larger and dominates node caps.

## Analytical PM Validity: GBW / ft Check

The lumped small-signal model (frequency-independent gm with Cgs/Cgd
capacitors) breaks down when GBW approaches the transit frequency (ft)
of any device in the signal path. The BSIM4 charge model includes
transcapacitance effects that create additional PM degradation the
lumped model cannot capture.

**Hard constraint: GBW / ft < 0.4 for all signal-path devices.**

This constraint MUST be enforced during L selection in the design flow.
If a candidate L yields GBW/ft ≥ 0.4, that L is rejected and the sweep
continues to a shorter L. If no L satisfies both the gain requirement
AND GBW/ft < 0.4, report the conflict and ask the user.

After computing GBW analytically, check ft for every signal-path device:
```
ft_i = lut_query(device_type, 'ft', L, corner=corner, temp=temp_str, gm_id_val=gm_id)
ratio = GBW / ft_i

if ratio >= 0.4:
    → REJECT this L choice. The analytical model is unreliable.
    → Try a shorter L (higher ft) or lower gm/ID (higher ft at cost of W).
```

| GBW / ft | PM accuracy | Action |
|----------|-------------|--------|
| < 0.1 | < 1° error | Reliable |
| 0.1 – 0.3 | 2–5° error | Acceptable |
| 0.3 – 0.4 | 5–8° error | Marginal — flag for SPICE verification |
| ≥ 0.4 | > 10° error | **REJECT** — do not use this L |

This is validated empirically (5T OTA, SKY130 tt/25°C, L sweep and W
sweep). Large W alone does NOT degrade accuracy — only long L (low ft)
causes the breakdown.

**Where to check:** The design flow checks GBW/ft at two points:
1. **During L selection** (design-flow Step 1d / 1c): reject candidate L
   values where ft is too low relative to GBW target.
2. **During analytical evaluation** (design-flow Step 4 / 6): verify all
   signal-path devices after final sizing. If any device exceeds 0.4,
   reduce its L and re-derive.

## Usage in Design Flow

Call this template for each device being sized. Example:

> Derive all parameters for **M3** (DIFF_PAIR, nfet) from LUT using
> `general/knowledge/lut-parameter-derivation.md` with:
> device_type='nfet', gm_id=(gm/ID)_3, L=L3, ID=ID3

For mirror devices (e.g. TAIL mirrors BIAS_GEN), derive per-instance
parameters using the unit-cell current `ID_instance = I_bias`, then
scale total quantities by the multiplier M:
```
gm_total  = gm_instance × M
gds_total = gds_instance × M
Cgs_total = Cgs_instance × M
...
```
