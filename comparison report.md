# AnalogAgent vs. Pure-LLM Analog Circuit Sizing
## A Controlled Comparison on a Two-Stage Miller OTA (SKY130)

---

## Experiment Setup

This document compares two approaches to analog transistor sizing on the **same circuit** with the **same specifications**:

- **Approach A — AnalogAgent**: Claude Code equipped with the AnalogAgent skill stack (gm/ID look-up tables, circuit-specific equation files, root-cause fault trees, and a simulation bridge to ngspice via CircuitCollector).
- **Approach B — Pure LLM**: Claude Code with no skills, no LUTs, no equation files, and no structured design flow. The LLM relied entirely on its own circuit design knowledge.

**Controlled variables:**
- **Topology**: `tsm_single` (two-stage Miller OTA, single-ended, PMOS mirror load) — identical netlist file
- **Specifications**: 11 targets (70 dB gain, 50 MHz GBW, 50 deg PM, 500 uW power, 10 V/us SR, 60 dB CMRR/PSRR, 30 uV noise, 1.1 V swing) — identical spec form
- **Process**: SKY130 ff corner, 20 C, VDD = 1.8 V, CL = 5 pF, Ibias = 10 uA
- **Starting point**: Both started from a fresh Claude Code session with no prior conversation context
- **Human intervention**: Both ran in bypass mode — no additional prompting was provided during the sizing process. Each approach received the topology and spec form as its sole input and ran autonomously until convergence or iteration limit.
- **Simulator**: Both used the same ngspice backend (via CircuitCollector) for SPICE verification
- **LLM model**: Both used the same Claude model

The only difference was whether the AnalogAgent skill stack was available.

---

## 1. Executive Summary

| Metric | AnalogAgent | Pure LLM |
|--------|-------------|----------|
| Simulation iterations | **2** | 8 (did not converge) |
| Final specs met | **11 / 11** | 9 / 11 |
| CMRR achieved | **72.2 dB** (target: 60) | 44.8 dB (failed) |
| PSRR+ achieved | **85.1 dB** (target: 60) | 44.5 dB (failed) |
| Parameter reversions | 0 | 2 (M1_L, M5_L reverted) |
| Concluded topology-limited? | No | Yes (incorrectly) |
| Final power | 423 uW | 488 uW |
| PM margin | +17.9 deg | +0.2 deg |
| GBW margin | +8.4% | +1.6% |

The skill-based approach converged in 2 simulation iterations, met all 11 specs, and had wider margins on every passing spec. The pure-LLM approach exhausted 8 iterations, failed to meet CMRR and PSRR+, and concluded these specs were fundamentally impossible with this topology — a conclusion AnalogAgent disproved by achieving 72 dB CMRR.

---

## 2. Initialization Strategy

### 2.1 Current Budget Allocation — The Foundational Divergence

| Current | AnalogAgent | Pure LLM |
|---------|-------------|----------|
| I_bias (M5) | 10 uA | 10 uA |
| I_tail (M6) | **130 uA** | **40 uA** |
| ID7 (M8) | 100 uA | 200 uA |
| Total | 240 uA | 250 uA |
| **1st : 2nd stage ratio** | **1.3 : 1** | **1 : 5** |

The LLM allocated 5x more current to the second stage, reasoning that a "strong 2nd stage for GBW/PM" was needed. AnalogAgent did the opposite: it invested heavily in the first stage because GBW = gm3/(2*pi*Cc), so first-stage gm is the primary GBW driver.

**Why this matters**: With I_tail = 40 uA, the LLM's gm3 = 300 uS required Cc ~ 1 pF for 50 MHz GBW. With I_tail = 130 uA, AnalogAgent's gm3 = 1170 uS allowed Cc ~ 3 pF — giving better compensation stability.

**How it happened**: AnalogAgent derived gm3 directly from the GBW equation, then the LUT determined ID3 = gm3/(gm/ID), from which I_tail followed. The LLM estimated gm from intuition without rigorously linking current allocation to the GBW equation.

### 2.2 Channel Length Selection — L3 = 0.5 vs 1.0 um

| Parameter | AnalogAgent | Pure LLM |
|-----------|-------------|----------|
| L3 (diff pair) | **0.5 um** | **1.0 um** |
| Rationale | LUT sweep: shortest L where gm_gds/1.5 >= sqrt(A0) AND GBW/ft < 0.4 | "L = 1.0 um for gain (high gm/gds at long channel)" |

Cascading consequences:
1. **VGS reduction**: SKY130 Vth is higher at L = 1.0 um than 0.5 um (reverse short-channel effect). The LLM's VGS_M3 = 0.768 V vs AnalogAgent's lower VGS at L = 0.5 um.
2. **M6 headroom**: VDS_M6 = Vcm - VGS_M3. The LLM's L3 = 1.0 left VDS_M6 = 0.128 V (below Vdsat = 0.142 V, in triode). AnalogAgent's L3 = 0.5 left VDS_M6 = 0.206 V with 99 mV margin.

### 2.3 M7 Sizing and Compensation

| Parameter | AnalogAgent | Pure LLM |
|-----------|-------------|----------|
| M7 effective W/L | ~124 | 20 |
| M7 gm/Id | 12 (moderate) | 3.6 (extreme strong) |
| M7 gm7 | 1203 uS | 721 uS |
| Cc | 2.48 pF | 1.0 pF |
| Rc | 2154 ohm (from KCL cubic) | 420 ohm (~ 1/gm7) |

The LLM's M7 consumed 203 uA while producing only 721 uS. AnalogAgent's M7 achieved 1203 uS with 100 uA. The LUT guarantees the intended operating point; without it, the LLM landed at gm/ID = 3.6 instead of the intended 10.

---

## 3. Root-Cause Diagnosis

### 3.1 The M6 Triode Problem — Same Symptom, Different Responses

Both approaches encountered M6 in triode. AnalogAgent's fault tree prescribed a simultaneous 4-parameter fix (gm/ID of diff pair and bias mirrors, L5, GBW overshoot) that resolved it in one simulation iteration (margin: -6 mV to +99 mV). The LLM fixed M6 (to 63 mV margin) but never addressed the underlying current allocation, leaving gm3 permanently limited.

### 3.2 CMRR — Correct vs. Incorrect Conclusion

The LLM concluded CMRR > 60 dB was a topology limitation:
> "Reaching 60 dB CMRR would require M3_L ~ 2100 um — physically impossible."

**AnalogAgent achieved 72.2 dB CMRR** with L3 = 0.5 um (shorter than the LLM's 1.0 um). The key was exploiting the CMRR numerator:

```
CMRR = 2 * gm3 * gm1 / [(gds3 + gds1) * gds_tail]
```

| Quantity | AnalogAgent | Pure LLM | Ratio |
|----------|-------------|----------|-------|
| gm3 * gm1 | 962,098 | 73,100 | **13.2x** |
| (gds3+gds1) * gds_tail | 474 | 118 | 4.0x |

The 13x numerator increase overwhelmed the 4x denominator increase. The LLM spent 6 iterations trying to shrink the denominator while the real leverage was in the numerator.

---

## 4. Convergence Behavior

### 4.1 Monotonic vs. Oscillating

AnalogAgent (monotonic):
```
                Gain   GBW    CMRR   IRN    Pass
Baseline sim    73.7   42.2   52.5   46.0   7/11
Sim iter 1      74.4   54.0   69.7   31.5   10/11
Sim iter 2      74.6   54.2   72.2   23.8   11/11
```

Pure LLM (oscillating):
```
Iter  Gain   GBW    CMRR   IRN    Pass
1     51.2   24.3   29.1   67.2   2/11
2     74.2   39.3   49.3   38.5   5/11
3     76.3   45.3   43.9   34.2   6/11   CMRR worsened
4     78.7   43.4   39.9   29.4   6/11   GBW, CMRR worsened
5     78.9   39.7   38.7   33.0   6/11   GBW, CMRR, IRN worsened
6     77.3   47.2   44.9   28.8   8/11   partial recovery
7     77.8   50.8   44.8   28.8   9/11   best, CMRR stuck
8     80.8   29.9   48.2   15.9   7/11   exploratory, crashed GBW
```

The LLM oscillated because fixes for one spec degraded another (M1_L increase killed PM and CMRR; M5_L increase gave no CMRR benefit). Each reversion wasted two iterations.

### 4.2 Why AnalogAgent Avoided Oscillations

1. **LUT-grounded predictions** — expected effects computed before committing changes
2. **Fault tree priority** — saturation fixed before spec failures (prevented the LLM's Iter 4 mistake)
3. **Analytical pre-screening** — full spec evaluation at every parameter change, before simulation

### 4.3 Efficiency Metrics

| Metric | AnalogAgent | Pure LLM |
|--------|-------------|----------|
| Simulation iterations to converge | **2** | 8 (did not converge) |
| Analytical pre-screening iterations | 2 | 0 |
| Wasted iterations (reversions) | 0 | 2 |
| Convergence direction | Monotonic (7 -> 10 -> 11) | Oscillating |

---

## 5. Role of Each Tool

| Tool | Function | Impact on Convergence |
|------|----------|----------------------|
| **gm/ID LUT** | Maps (gm/ID, L) to id_w, gm_gds, ft, caps, vdsat | Eliminated W guesswork; enabled L sweep with quantitative gain + GBW/ft checks |
| **Equation files** | KCL cubic for exact poles; 4-node PSRR+; two-path PSRR-; extrinsic cap corrections | Accurate Rc (2154 vs 420 ohm); caught TAIL coupling path the LLM missed |
| **Fault trees** | Map each spec failure to prioritized root causes | Multi-pronged M6 fix in one iteration; prevented harmful M1_L change |
| **Simulation bridge** | Converts gm/ID targets to CircuitCollector params; handles mirror groups, W splitting | Guaranteed LUT-SPICE consistency; automatic PDK-compliant device sizing |

---

## 6. Key Takeaways

1. **Current allocation is the most consequential design decision.** The gm/ID methodology derives it from the GBW equation. The LLM's "strong 2nd stage" heuristic led to a 1:5 split that was fundamentally suboptimal.

2. **Channel length selection needs quantitative tradeoff evaluation**, not heuristics like "longer L for more gain." The L sweep found L3 = 0.5 um — adequate for gain and critical for M6 headroom, a connection the heuristic missed.

3. **Analytical pre-screening eliminates bad parameter choices before simulation**, preventing oscillations and reversions.

4. **Topology limitations should not be concluded without exploring the full design space.** The LLM's premature conclusion was caused by exploring only a narrow region (low gm3, high L3). The skill stack naturally explored a wider region because the LUT and equations quantify the full CMRR formula, not just the denominator.

5. **Codified circuit knowledge prevents ad-hoc reasoning errors.** The KCL cubic, 4-node PSRR+, and two-path PSRR- are all "known" to the LLM in principle, but it defaults to simpler approximations under the cognitive load of multi-spec optimization.

---
---

## Appendix A: AnalogAgent Sizing Report

### A.1 Method

AnalogAgent skill stack: gm/ID LUT + analytical equations + SPICE iteration. Converged in 2 simulation iterations.

### A.2 Initial Analytical Design

The skill stack works backward from GBW: gm3 = 2*pi * 50 MHz * 2.5 pF = 785 uS. At gm/ID = 12: ID3 = 65 uA, I_tail = 130 uA. LUT sweep selected L3 = 0.5 um. Load L1 = 1.0 um (A_v1 = 67.6). Output stage L7 = 0.18 um initially.

**Analytical gate caught failures before simulation:** A0 = 57.8 dB (A_v2 = 11.4 at L7=0.18) and Power = 594 uW. Fixed analytically: L7 -> 0.5 um (gm_gds: 13 -> 92), gm_id_7 -> 12, M8_M: 19 -> 13. Verified to pass, then submitted to SPICE.

### A.3 Baseline Simulation

| Device | L (um) | WL_ratio | M | gm/ID |
|--------|--------|----------|---|-------|
| M1/M2 | 1.0 | 9.87 | 8 | 12 |
| M3/M4 | 0.5 | 6.71 | 3 | 12 |
| M5 | 1.0 | 2.96 | 1 | 12 |
| M6 | 1.0 | 2.96 | 13 | (mirror) |
| M7 | 0.5 | 9.48 | 17 | 12 |
| M8 | 1.0 | 2.96 | 13 | (mirror) |

Cc = 2.48 pF, Rc = 1896 ohm.

**Results (7/11 pass):** Gain 73.7 dB, GBW 42.2 MHz (FAIL), PM 74.1, Power 451, CMRR 52.5 (FAIL), PSRR- 55.0 (FAIL), IRN 46.0 uV (FAIL).

**Diagnosis:** M6 in triode (VDS=0.137, VDSat=0.143, gds=248 uS). Explains CMRR, PSRR-, GBW failures.

### A.4 Simulation Iteration 1: Fix M6 Headroom

| Change | From | To | Reason |
|--------|------|----|--------|
| gm/ID (M3) | 12 | 16 | Lower VGS_M3 -> more M6 headroom; wider W3 -> noise |
| gm/ID (M1) | 12 | 14 | Better M3/M4 VDS balance |
| gm/ID (M5) | 12 | 16 | Lower Vdsat_M6 |
| L5 | 1.0 | 1.5 | Higher tail ro |
| M8_M | 13 | 10 | Power budget |
| GBW target | 50 | 60 MHz | Compensate ~15% SPICE shortfall |

**Results (10/11 pass):** CMRR 52.5 -> 69.7 dB. GBW 42.2 -> 54.0 MHz. M6 margin = 75 mV. **Only IRN fails** (31.6 vs 30 uV).

### A.5 Simulation Iteration 2: Fix Noise (Converged)

| Change | From | To | Reason |
|--------|------|----|--------|
| gm/ID (M3) | 16 | 18 | Gate area nearly doubles -> 1/f noise |
| M6_M | 12 | 13 | +8% gm3 -> thermal noise |

**Results (11/11 pass):** IRN 31.6 -> 23.8 uV. All specs met.

### A.6 Final Operating Point

| Dev | gm (uS) | Id (uA) | gm/Id | gm/gds | VDS (V) | VDSat (V) | Region |
|-----|----------|---------|-------|--------|---------|-----------|--------|
| M1 | 861.1 | 65.0 | 13.2 | 480 | 1.081 | 0.113 | SAT |
| M2 | 861.0 | 65.0 | 13.2 | 479 | 1.076 | 0.113 | SAT |
| M3 | 1118 | 65.0 | 17.2 | 100 | 0.514 | 0.082 | SAT |
| M4 | 1118 | 65.0 | 17.2 | 100 | 0.518 | 0.082 | SAT |
| M5 | 160.0 | 10.0 | 16.0 | 175 | 0.648 | 0.107 | SAT |
| M6 | 1969 | 130.0 | 15.1 | 54 | 0.206 | 0.107 | SAT (99 mV) |
| M7 | 1203 | 100.0 | 12.0 | 110 | 0.900 | 0.146 | SAT |
| M8 | 1625 | 100.0 | 16.3 | 194 | 0.900 | 0.107 | SAT |

### A.7 Final Parameters and Performance

```
M1_L = 1.0   M1_WL_ratio = 9.56   M1_M = 14
M3_L = 0.5   M3_WL_ratio = 9.50   M3_M = 8
M5_L = 1.5   M5_WL_ratio = 3.16   M5_M = 2
M6_L = 1.5   M6_WL_ratio = 3.16   M6_M = 26    (I_tail = 130 uA)
M7_L = 0.5   M7_WL_ratio = 9.53   M7_M = 13
M8_L = 1.5   M8_WL_ratio = 3.16   M8_M = 20    (ID7 = 100 uA)
C1 = 3.10 pF,  Rc = 2161 ohm,  Ibias = 10 uA
Power = 423 uW
```

| Spec | Target | Achieved | Pass? |
|------|--------|----------|-------|
| DC Gain | >= 70 dB | 74.6 dB | YES |
| GBW | >= 50 MHz | 54.2 MHz | YES |
| PM | >= 50 deg | 67.9 deg | YES |
| Power | <= 500 uW | 423 uW | YES |
| SR+ | >= 10 V/us | 101.5 V/us | YES |
| SR- | >= 10 V/us | 11.2 V/us | YES |
| CMRR | >= 60 dB | 72.2 dB | YES |
| PSRR+ | >= 60 dB | 85.1 dB | YES |
| PSRR- | >= 60 dB | 78.7 dB | YES |
| IRN | <= 30 uV | 23.8 uV | YES |
| Swing | >= 1.1 V | 1.41 V | YES |

**Result: 11/11 specs met.** No parameter reversions.

---
---

## Appendix B: Pure-LLM Sizing Report

### B.1 Method

Manual analytical sizing + SPICE iteration. No LUT, no skill stack, no structured design flow. 8 iterations, did not fully converge.

### B.2 Initial Analytical Design

Current budget: I_tail = 40 uA (M6_M=4), I_d7 = 200 uA (M8_M=20). At gm/Id ~ 15 for M3 (L=1.0 um): gm3 = 300 uS. GBW ~ 48 MHz with Cc = 1.0 pF. Gain estimate: ~56 dB (below 70 target).

### B.3 Iteration 1: Initial Parameters

| Device | L (um) | WL_ratio | M |
|--------|--------|----------|---|
| M1/M2 | 1.0 | 5.0 | 1 |
| M3/M4 | 1.0 | 4.0 | 1 |
| M5 | 1.0 | 3.0 | 1 |
| M6 | 1.0 | 3.0 | 4 |
| M7 | 0.5 | 5.0 | 4 |
| M8 | 1.0 | 3.0 | 20 |

Cc = 1.0 pF, Rc = 420 ohm.

**Results (2/11 pass):** Gain 51.2, GBW 24.3, PM 43.6, CMRR 29.1, IRN 67.2, Swing 0.80. M6 in triode (VDS=0.128, VDSat=0.142). M7 at gm/Id=3.6 (extreme strong inversion, VDSat=471 mV).

### B.4 Iteration 2: Fix M6 and M7

Wider M3 (WL 4->8), wider M5 (WL 3->5), M7 WL 5->10, M7_M 4->10.

**Results (5/11 pass):** M6 now saturated (63 mV margin). Gain 74.2, GBW 39.3, PM 50.8, Swing 1.61. Still failing: GBW, CMRR (49.3), PSRR+ (50.8), IRN (38.5).

### B.5 Iterations 3-5: CMRR Struggle with Reversions

**Iter 3:** M5_L 1.0->2.0, M6_M 4->5, Cc 1.0->1.1 pF. GBW improved (45.3) but **CMRR worsened** (49.3->43.9) due to increased M3/M4 VDS asymmetry.

**Iter 4:** M1_L 1.0->1.5, M3_WL 10->12, M5_L 2.0->3.0. IRN met (29.4) but **PM dropped** to 49.9 (mirror pole penalty) and **CMRR worsened** to 39.9.

**Iter 5:** **Reverted** M1_L to 1.0 and tested M5_L=5.0. PM recovered (55.8) but CMRR stayed at 38.7. GBW regressed to 39.7, IRN regressed to 33.0.

**Lessons learned:** M1_L > 1.0 degrades both PM and CMRR. M5_L beyond 2.0 gives diminishing CMRR returns.

### B.6 Iteration 6: Comprehensive Rebalance (Breakthrough)

M1_WL 5->7, M3_WL 10->14, M5_L **reverted** to 1.0, M5_WL 5->8, M7_M 22->24, Cc 1.43->1.35 pF.

**Results (8/11 pass):** CMRR improved to 44.9 (+6 dB from wider M1). IRN met (28.8). GBW = 47.2 (close). M6 headroom = 95 mV (best yet).

### B.7 Iteration 7: Best Design (9/11)

M5_L 1.0->2.0, Cc 1.35->1.27 pF.

**Results (9/11 pass):** GBW = 50.8 (met, 1.6% margin). PM = 50.2 (0.2 deg margin). CMRR = 44.8 and PSRR+ = 44.5 still failing.

### B.8 Iteration 8: Exploratory (M3_L = 3.0)

M3_L 1.0->3.0, Cc 1.27->1.90 pF.

**Results (7/11 pass):** CMRR +3.4 dB (48.2) but GBW crashed to 29.9 MHz. Extrapolation: 60 dB CMRR would need M3_L ~ 2100 um.

### B.9 Final Operating Point (Iteration 7)

| Dev | gm (uS) | Id (uA) | gm/Id | gm/gds | VDS (V) | VDSat (V) | Region |
|-----|----------|---------|-------|--------|---------|-----------|--------|
| M1 | 171.7 | 28.6 | 6.0 | 258 | 1.312 | 0.292 | SAT |
| M2 | 170.6 | 28.4 | 6.0 | 213 | 1.079 | 0.292 | SAT |
| M3 | 425.4 | 28.6 | 14.9 | 80 | 0.296 | 0.120 | SAT |
| M4 | 428.2 | 28.4 | 15.1 | 154 | 0.528 | 0.118 | SAT |
| M5 | 174.5 | 10.0 | 17.4 | 216 | 0.619 | 0.098 | SAT |
| M6 | 995.8 | 57.0 | 17.5 | 60 | 0.192 | 0.098 | SAT |
| M7 | 2383 | 204.3 | 11.7 | 109 | 0.898 | 0.147 | SAT |
| M8 | 3545 | 204.3 | 17.3 | 244 | 0.902 | 0.098 | SAT |

### B.10 Final Parameters and Performance

```
M1_L = 1.0   M1_WL_ratio = 7.0    M1_M = 1
M3_L = 1.0   M3_WL_ratio = 14.0   M3_M = 1
M5_L = 2.0   M5_WL_ratio = 8.0    M5_M = 1
M6_L = 2.0   M6_WL_ratio = 8.0    M6_M = 6     (I_tail = 60 uA)
M7_L = 0.5   M7_WL_ratio = 10.0   M7_M = 24
M8_L = 2.0   M8_WL_ratio = 8.0    M8_M = 20    (ID7 = 200 uA)
C1 = 1.27 pF,  Rc = 420 ohm,  Ibias = 10 uA
Power = 488 uW
```

| Spec | Target | Achieved | Pass? |
|------|--------|----------|-------|
| DC Gain | >= 70 dB | 77.8 dB | YES |
| GBW | >= 50 MHz | 50.8 MHz | YES |
| PM | >= 50 deg | 50.2 deg | YES |
| Power | <= 500 uW | 488 uW | YES |
| SR+ | >= 10 V/us | 50.3 V/us | YES |
| SR- | >= 10 V/us | 24.8 V/us | YES |
| CMRR | >= 60 dB | 44.8 dB | **NO** |
| PSRR+ | >= 60 dB | 44.5 dB | **NO** |
| PSRR- | >= 60 dB | 69.4 dB | YES |
| IRN | <= 30 uV | 28.8 uV | YES |
| Swing | >= 1.1 V | 1.71 V | YES |

### B.11 Convergence Summary

| Spec | Target | It1 | It2 | It3 | It4 | It5 | It6 | **It7** | It8 |
|------|--------|-----|-----|-----|-----|-----|-----|---------|-----|
| Gain | >= 70 | 51.2 | 74.2 | 76.3 | 78.7 | 78.9 | 77.3 | **77.8** | 80.8 |
| GBW | >= 50 | 24.3 | 39.3 | 45.3 | 43.4 | 39.7 | 47.2 | **50.8** | 29.9 |
| PM | >= 50 | 43.6 | 50.8 | 52.2 | 49.9 | 55.8 | 52.3 | **50.2** | 58.8 |
| CMRR | >= 60 | 29.1 | 49.3 | 43.9 | 39.9 | 38.7 | 44.9 | **44.8** | 48.2 |
| IRN | <= 30 | 67.2 | 38.5 | 34.2 | 29.4 | 33.0 | 28.8 | **28.8** | 15.9 |
| **Pass** | | 2/11 | 5/11 | 6/11 | 6/11 | 6/11 | 8/11 | **9/11** | 7/11 |

**Result: 9/11 specs met.** CMRR and PSRR+ limited to ~45 dB. The LLM concluded this was a topology limitation.
