# Self-Evolving Corrections

## Purpose

Empirical correction models derived from systematic comparison of
analytical predictions against SPICE across many design points. These
corrections compensate for structural model limitations that cannot be
fixed by analytical formulas alone.

Each topology has its own persistent dataset under
`regression_analysis/<topology_name>.json` that grows as new designs
are sized. The regression is re-fitted from the full dataset at
design-review time (Step 1b).

---

## Correction 1 — TSM Phase Margin

**Dataset file:** `regression_analysis/tsm_single.json`

**Initial dataset:** 77 design points across CL ∈ {1, 2, 5, 10, 20} pF,
gm/ID ∈ {10, 12, 15, 18}, GBW ∈ {20, 30, 50, 70} MHz, Cc/CL = 0.4,
SKY130 ff/20°C.

**Regression:**

```
PM_regression = PM_analytical − (b_GBW × GBW_MHz + b_CcCL × Cc_over_CL + intercept)
```

Initial coefficients (re-fitted automatically each run):

| Statistic | Value |
|-----------|-------|
| b_GBW     | 0.31 °/MHz |
| b_CcCL    | −134.0 °/unit |
| Intercept | 48.6° |
| R²        | 0.89 |
| RMS residual | 2.3° |
| Valid range | 15–80 MHz GBW, Cc/CL ∈ 0.3–0.6 |

---

## Correction 2 — 5T OTA Phase Margin

**Dataset file:** `regression_analysis/5tota_single.json`

**Initial dataset:** 20 design points, gm/ID ∈ {8, 10, 12, 15, 18},
L ∈ {0.5, 1.0, 1.5, 2.0} µm, CL = 5 pF, SKY130 tt/27°C.

**Regression:**

```
PM_regression = PM_analytical − 26 × (GBW / ft_min)
```

| Statistic | Value |
|-----------|-------|
| Slope     | −26 °/unit |
| R²        | 0.82 |
| Residual  | ±1.5° |
| Valid range | GBW/ft < 0.15 |

---

## Integration with Sizing Flow

**Data collection** (simulation-verification.md Step 6):
After every simulation iteration, a data point is appended to
`regression_analysis/<topology_name>.json`.

**Re-fit** (design-review.md Step 1b):
Before printing the report, the regression is re-fitted from the full
per-topology dataset and `PM_regression` is computed with the fresh
coefficients.
