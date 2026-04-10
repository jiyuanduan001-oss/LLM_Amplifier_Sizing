# Mismatch and PVT Skill

## Purpose

Guide the LLM to reason about mismatch and PVT variations at both the
physical and mathematical levels during design. This skill is invoked by
the Circuit Design Flow and Root-Cause Diagnosis skills when mismatch or
PVT considerations are needed.

---

## Part 1 — Mismatch

### Physical Basis

Random mismatch arises from statistical fluctuations in doping, oxide
thickness, and geometry during fabrication. For two identically-drawn
transistors placed close together, the mismatch follows the Pelgrom model.

### Pelgrom Model

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
σ(ΔVT) = A_VT / √(W·L)          [threshold voltage mismatch]
```
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
σ(Δβ/β) = A_β / √(W·L)           [current factor mismatch]
```

Where:
- A_VT: process-specific V_T mismatch coefficient (units: mV·µm)
- A_β: process-specific β mismatch coefficient (units: %·µm)
- W, L: device dimensions of each transistor in the matched pair

**Typical A_VT values** (approximate — use process-specific values from PDK):
- 180nm CMOS: A_VT ≈ 4–6 mV·µm (NMOS), 5–8 mV·µm (PMOS)
- 130nm CMOS: A_VT ≈ 3–5 mV·µm
- 65nm CMOS: A_VT ≈ 2–4 mV·µm
- 28nm CMOS: A_VT ≈ 1–2 mV·µm
- SKY130: A_VT ≈ 5 mV·µm (NMOS), 6 mV·µm (PMOS) [approximate]

### Input-Referred Offset Propagation

For a differential pair (M1, M2) with current mirror load (M3, M4):

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
σ(Vos)² = σ(ΔVT_12)² + (Vov1/2)² · σ(Δβ/β_12)²
        + σ(ΔVT_34)² · (gm3/gm1)²
        + (Vov3/2)² · σ(Δβ/β_34)² · (gm3/gm1)²
```

**Simplified** (V_T mismatch dominates at moderate inversion):
> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
σ(Vos) ≈ √[ σ(ΔVT_12)² + σ(ΔVT_34)² · (gm3/gm1)² ]
```

**Design implication**: to minimize offset:
- Increase W1·L1 (reduces σ(ΔVT_12))
- Minimize gm3/gm1 ratio (reduces load contribution)
- But: increasing W1·L1 adds capacitance → impacts bandwidth

### Current Mirror Mismatch

> **Compute the following using Python (show the code execution, do NOT calculate mentally):**
```
σ(ΔI/I) = √[ (2/Vov)² · σ(ΔVT)² + σ(Δβ/β)² ]
```

At low Vov: V_T mismatch dominates → increase W·L or increase Vov.
At high Vov: β mismatch dominates → increase W·L.

### Minimum Area for Offset Budget

To achieve 3σ offset ≤ Vos_max (input pair only):
```
W1·L1 ≥ (3 · A_VT / Vos_max)²
```

Example: A_VT = 5 mV·µm, Vos_max = 5mV (3σ):
→ W1·L1 ≥ (15/5)² = 9 µm² → e.g., W=18µm, L=0.5µm

### Layout Flags (Schematic Level)

Even at schematic level, flag these for the layout engineer:
- **Matching-critical pairs**: must be common-centroid or interdigitated
  → Input pair (M1, M2)
  → Active load (M3, M4)
  → Any current mirror pair
- **Same orientation** for matched devices
- **Dummy devices** at array edges
- **Guard rings** around sensitive analog blocks
- **Proximity** requirement: matched devices must be adjacent

---

## Part 2 — PVT (Process, Voltage, Temperature)

### Device Behavior Under Process Corners

| Corner | NMOS      | PMOS      | Effect on circuit                      |
|--------|-----------|-----------|----------------------------------------|
| TT     | Typical   | Typical   | Nominal design point                   |
| FF     | Fast      | Fast      | Higher gm, higher ID, more power       |
| SS     | Slow      | Slow      | Lower gm, lower ID, less BW, less gain |
| FS     | Fast N    | Slow P    | NMOS stronger than PMOS — bias shift   |
| SF     | Slow N    | Fast P    | PMOS stronger than NMOS — bias shift   |

**Key effects of corners on op-amp performance:**
- SS: worst-case for GBW, gain, SR (everything is slower)
- FF: worst-case for power (more current than designed for)
- FS/SF: worst-case for bias balance — mirrors may have large ratio errors
- SS+hot: combined worst case for speed (mobility degrades with temperature)
- FF+cold: combined worst case for power

### Temperature Effects

- **Mobility** decreases with temperature → gm decreases → GBW decreases
- **V_T** decreases with temperature → more subthreshold leakage
- **Thermal noise** increases linearly with T (kT factor)
- **1/f noise**: temperature dependence is process-specific

### Voltage Variation

- **VDD high**: more headroom → easier saturation, but more power
- **VDD low**: less headroom → devices may leave saturation, especially cascodes

### Using PVT in Design

**During initial sizing (Spec Understanding):**
If user specifies PVT corners → note which corners to check.
If not specified → design at TT/27°C, note in Design Review.

**During sizing (Circuit Design Flow):**
When querying LUTs, use the LUT entries corresponding to the target PVT condition.
- TT corner → use nominal LUT
- SS corner → use slow-corner LUT (if available)
- Temperature → use LUT at target temperature (if available)

**During verification (Simulation):**
If PVT specs exist → run simulation at each specified corner.
Check all specs at each corner. Worst-case performance is what matters.

**In Design Review:**
Report achieved performance at each corner. Flag any corner where
a spec is marginal or fails.

### Robust Design Guideline

For production designs, the circuit should meet specs across all specified
corners. The approach:
1. Design at TT (typical) with adequate margin
2. Verify at all corners
3. If any corner fails → adjust sizing and re-verify
4. Accept worst-case performance as the actual spec achievement

Margin guidelines:
- Gain: design for A0_target + 3dB at TT
- GBW: design for GBW_target × 1.15 at TT
- PM: design for PM_target + 5° at TT
- These margins are heuristics — actual corner variation is process-dependent
