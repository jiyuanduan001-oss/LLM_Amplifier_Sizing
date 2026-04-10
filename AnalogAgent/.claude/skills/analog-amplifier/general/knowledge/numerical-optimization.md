# Numerical Optimization Skill

## Purpose

After the LLM-driven sizing flow converges (design review complete),
this skill further optimizes the design using a derivative-free
numerical optimizer. It treats the simulator as a black-box function
and searches the design space to minimize power while maximizing gain
and GBW, subject to all user-specified constraints.

## When to Invoke

Only when `Optimize = yes` in the validated spec form. Invoked **after**
the design review (Stage [6]), including Extreme PVT if enabled.

## Prerequisites

The following must be available from the completed design flow:
- `params` dict and `config_path` from the final converged simulation
- `corner` and `temperature` from the validated spec form
- All user targets from the validated spec form
- The topology name (e.g., `'twostage'`)
- The role-to-device mapping for the topology
- The converged sizing variables (gm/ID, L, mirror multipliers, Cc, I_bias)
- **Optimization weights** (`w_pwr`, `w_gain`, `w_gbw`) from user
  priority selection (see `design-review.md` Step 4a)

---

## Procedure

### Step 1 — Identify Optimization Variables from the Topology

This skill is **topology-agnostic**. The optimization variables are
derived from the `params` dict produced by `convert_sizing`, not from
hardcoded TSM roles.

Extract all tunable parameters from the `params` dict:

```python
# params dict example (topology-dependent):
# {'M3_L': 1.08, 'M3_WL_ratio': 9.41, 'M3_M': 3,
#  'M1_L': 0.72, 'M1_WL_ratio': 9.20, 'M1_M': 11, ...
#  'C1_value': 2.05e-12, 'Rc_value': 1267, 'ibias': 1e-5}

# Optimization variables: every key ending in '_L', '_WL_ratio', '_M',
# plus 'C1_value', 'Rc_value', 'ibias'.
```

**Variable classification:**

| Suffix / Key  | Type       | Bounds                        |
|---------------|------------|-------------------------------|
| `*_L`         | continuous | [0.15, 5.0] um                |
| `*_WL_ratio`  | continuous | device-dependent min to 10.0  |
| `*_M`         | integer    | [1, 100]                      |
| `C1_value`    | continuous | [0.1pF, 20pF]                 |
| `Rc_value`    | continuous | [100, 100k] ohm               |
| `ibias`       | continuous | [1uA, 100uA]                  |

The LLM-converged `params` dict provides the initial point `x0`.

**Key design choice:** All parameters in the `params` dict become
optimization variables — including `*_M` (finger multipliers) and
`ibias`. This allows the optimizer to genuinely reduce power by
adjusting mirror ratios and bias current, unlike a formulation where
currents are fixed.

Integer variables (`*_M`) are handled by rounding after each optimizer
step and before calling `simulate_circuit`.

### Step 2 — Define Objective and Constraints

**Objective (minimize):**

This is a **single-objective** optimization using a weighted
scalarization of three goals:

```
cost = w_pwr  * (Power / Power_ref)
     - w_gain * (Gain_linear / Gain_ref_linear)
     - w_gbw  * (GBW / GBW_ref)

where:
  Gain_linear     = 10^(Gain_dB / 20)        # V/V
  Gain_ref_linear = 10^(Gain_ref_dB / 20)    # V/V
```

**IMPORTANT:** Gain MUST be converted from dB to linear scale (V/V)
before normalization. dB is logarithmic — a 6 dB improvement (2×
linear) appears as only ~8% in dB but 100% in linear. Using dB
compresses the dynamic range and prevents the optimizer from
properly prioritizing gain improvements.

Where `*_ref` are the values from the LLM-converged simulation.

**Weights are set by the user's priority selection** (from
`design-review.md` Step 4a):

| Priority | w_pwr | w_gain | w_gbw | Effect |
|----------|-------|--------|-------|--------|
| Power    | 1.0   | 0.15   | 0.15  | Aggressively reduce power |
| Gain     | 0.15  | 1.0    | 0.15  | Maximize DC gain headroom |
| GBW      | 0.15  | 0.15   | 1.0   | Maximize bandwidth |

The non-prioritized metrics still receive weight 0.15 (not zero),
so the optimizer considers them as secondary objectives rather than
ignoring them entirely.

A single-objective formulation is used because:
- A multi-objective Pareto approach (e.g., NSGA-II) requires 500+
  evaluations — too expensive for ~10s/sim.
- The weighted sum is practical: the user selects the primary
  priority and the weights encode it directly.
- The LLM starting point is already feasible; we seek incremental
  improvement, not a full design-space exploration.

**Constraints (penalty method):**

Every user-specified active target is an inequality constraint.
Constraints are enforced via quadratic penalty:

```
penalty += k * (max(0, violation))^2

where:
  k = 1000  (penalty weight)
  violation = (target - achieved) / |target|  for >= constraints
  violation = (achieved - target) / |target|  for <= constraints
```

Additional penalty for non-saturated devices: `+1e6` per device.

**Gain-plateau constraint (mandatory):**

The testbench reports `gain_peaking_dB` — a metric that compares
the open-loop measured GBW (0 dB crossing) against the true
effective GBW derived from the closed-loop -3 dB bandwidth.
When over-sized Rc creates a gain plateau that inflates the
measured GBW, `gain_peaking_dB > 0`.

This constraint MUST always be included, regardless of user targets:
```
penalty += 1e4 * max(0, gain_peaking_dB) ^ 2
```

This prevents the optimizer from exploiting the gain-plateau
artifact as a "free" GBW improvement.

### Step 3 — Build the Objective Function

Write and execute a Python script that defines `f(x)`:

```python
def f(x):
    # 1. Unpack x into a params dict
    params = dict(zip(param_names, x))

    # 2. Round integer variables (*_M)
    for k in params:
        if k.endswith('_M'):
            params[k] = max(1, round(params[k]))

    # 3. Call simulate_circuit(params, config_path, corner, temperature)
    #    Use a unique output_dir (tempfile.mkdtemp) to enable parallel eval.
    # 4. Extract specs. Convert gain from dB to linear: 10^(gain_dB/20)
    # 5. Compute cost (using linear gain) + penalty
    # 6. Return cost + penalty (or 1e9 on failure)
```

**IMPORTANT:** The `params` dict is passed directly to
`simulate_circuit` — no need to call `convert_sizing`. The optimizer
works at the CircuitCollector parameter level, bypassing the LUT
entirely. This is the key simplification: the optimizer doesn't need
to know about gm/ID methodology or circuit equations.

**Parallel evaluation:** Each `simulate_circuit` call must use a
unique `output_dir` (via `tempfile.mkdtemp()`) to avoid file-path
conflicts between concurrent ngspice processes. The CircuitCollector
API supports concurrent requests when output directories are
isolated.

### Step 4 — Run the Optimizer

Use **CMA-ES** (Covariance Matrix Adaptation Evolution Strategy).

**Why CMA-ES:**

| Method | Evals (N=10) | Coupling | Parallelism | Complexity |
|--------|-------------|----------|-------------|------------|
| Coordinate search | 50–80 | No | No | Simple |
| Nelder-Mead | 100–200 | Partial | No | Simple |
| CMA-ES | 80–160 | **Yes** (covariance) | **Yes** (population) | Moderate |
| Bayesian Opt | 30–50 | Yes (GP) | Limited | Needs library |

CMA-ES is chosen because:
1. **Handles variable coupling** — adapts a full covariance matrix
   that learns correlated directions (e.g., Rc–Cc–gm7). No separate
   fixup step needed.
2. **Population-based** — each generation evaluates λ candidate
   solutions independently. These can be simulated **in parallel**
   using concurrent API calls with unique output directories.
3. **Sample-efficient** — with population λ=16 and ~10 generations,
   total evaluations ≈ 160 simulations. At 16-way parallelism with
   ~12s per batch, wall-clock time ≈ **2 minutes**.
4. **Numpy-only** — no external dependencies.

**CMA-ES implementation (numpy-only):**

```python
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import tempfile

def cma_es(f_batch, x0, sigma0, bounds, int_params,
           max_gen=20, lam=32, n_workers=16):
    """
    CMA-ES with bound handling and parallel batch evaluation.

    Args:
        f_batch:    function(list[array]) -> list[float]
                    Evaluates a batch of candidate solutions in parallel.
        x0:         initial mean (1D array, normalized to [0,1])
        sigma0:     initial step size (e.g. 0.2)
        bounds:     list of (lo, hi) per dimension (original scale)
        int_params: set of indices that are integers
        max_gen:    maximum generations
        lam:        population size (set to n_workers for full parallelism)
        n_workers:  number of concurrent simulation workers

    Returns:
        dict with 'x' (best params, original scale), 'fun', 'nfev'
    """
    n = len(x0)
    lo = np.array([b[0] for b in bounds], dtype=float)
    hi = np.array([b[1] for b in bounds], dtype=float)

    # Normalize search space to [0, 1]
    def to_unit(x):
        return (x - lo) / (hi - lo)
    def from_unit(u):
        x = lo + u * (hi - lo)
        for i in int_params:
            x[i] = max(lo[i], round(x[i]))
        return np.clip(x, lo, hi)

    # CMA-ES state
    mu = lam // 2                        # parent count
    weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    weights /= weights.sum()
    mu_eff = 1.0 / (weights ** 2).sum()

    # Adaptation parameters
    c_sigma = (mu_eff + 2) / (n + mu_eff + 5)
    d_sigma = 1 + 2 * max(0, np.sqrt((mu_eff - 1) / (n + 1)) - 1) + c_sigma
    c_c = (4 + mu_eff / n) / (n + 4 + 2 * mu_eff / n)
    c_1 = 2 / ((n + 1.3) ** 2 + mu_eff)
    c_mu = min(1 - c_1, 2 * (mu_eff - 2 + 1 / mu_eff) / ((n + 2) ** 2 + mu_eff))
    chi_n = np.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n ** 2))

    # State variables
    mean = to_unit(x0)
    sigma = sigma0
    C = np.eye(n)
    p_sigma = np.zeros(n)
    p_c = np.zeros(n)
    best_x = x0.copy()
    best_f = float('inf')
    n_evals = 0

    for gen in range(max_gen):
        # Sample population
        try:
            A = np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            C = np.eye(n)
            A = np.eye(n)

        z = np.random.randn(lam, n)
        y = z @ A.T
        population_unit = mean + sigma * y
        population = np.array([from_unit(np.clip(u, 0, 1))
                               for u in population_unit])

        # Evaluate batch in parallel
        f_vals = f_batch(population)
        n_evals += lam

        # Sort by fitness
        order = np.argsort(f_vals)
        f_vals_sorted = np.array(f_vals)[order]

        # Track best
        if f_vals_sorted[0] < best_f:
            best_f = f_vals_sorted[0]
            best_x = population[order[0]].copy()

        # Recombination: weighted mean of top-mu
        y_sel = y[order[:mu]]
        y_w = weights @ y_sel           # weighted step

        # Update mean
        mean_old = mean.copy()
        mean = mean + sigma * y_w
        mean = np.clip(mean, 0, 1)

        # Update evolution paths
        C_inv_sqrt = np.linalg.inv(A)   # A @ A.T = C → A^{-1}
        p_sigma = (1 - c_sigma) * p_sigma + \
                  np.sqrt(c_sigma * (2 - c_sigma) * mu_eff) * (C_inv_sqrt @ y_w)
        h_sigma = (np.linalg.norm(p_sigma) /
                   np.sqrt(1 - (1 - c_sigma) ** (2 * (gen + 1))) < \
                   (1.4 + 2 / (n + 1)) * chi_n)
        p_c = (1 - c_c) * p_c + \
              h_sigma * np.sqrt(c_c * (2 - c_c) * mu_eff) * y_w

        # Update covariance matrix
        rank_one = np.outer(p_c, p_c)
        rank_mu = sum(w * np.outer(y_sel[i], y_sel[i])
                      for i, w in enumerate(weights))
        C = (1 - c_1 - c_mu) * C + c_1 * rank_one + c_mu * rank_mu

        # Update step size
        sigma *= np.exp((c_sigma / d_sigma) *
                        (np.linalg.norm(p_sigma) / chi_n - 1))
        sigma = min(sigma, 0.5)  # cap (keep perturbations local)

        print(f"  Gen {gen+1}/{max_gen}: best={best_f:.4f}, "
              f"gen_best={f_vals_sorted[0]:.4f}, sigma={sigma:.4f}, "
              f"evals={n_evals}")

        # Convergence: sigma too small
        if sigma < 1e-6:
            break

    return {'x': best_x, 'fun': best_f, 'nfev': n_evals,
            'ngen': gen + 1}
```

**Batch evaluation wrapper:**

```python
def make_batch_evaluator(f_single, n_workers=16):
    """Wrap a single-point objective into a parallel batch evaluator."""
    def f_batch(population):
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(f_single, x) for x in population]
            return [fut.result() for fut in futures]
    return f_batch
```

**Runtime estimate:**

With λ=32 and max_gen=20: 32 × 20 = 640 total sims. At 16-way
parallelism, 40 batches × ~12s/batch = **~8 minutes** wall-clock.

### Step 5 — Select Variables to Optimize

Not all params need optimization. To keep runtime short, select
the **most impactful** variables:

**Default variable selection** (topology-agnostic):

```python
# From the params dict, select ALL tunable variables:
opt_vars = {}
for k, v in params.items():
    if k.endswith('_L'):         # Channel length → gain (intrinsic gm/gds)
        opt_vars[k] = v
    elif k.endswith('_WL_ratio'):# W/L ratio → gm, gds, capacitances
        opt_vars[k] = v
    elif k.endswith('_M'):       # Mirror multipliers → currents, power
        opt_vars[k] = v
    elif k == 'C1_value':        # Cc → GBW, PM tradeoff
        opt_vars[k] = v
    elif k == 'Rc_value':        # Rc → PM, zero placement
        opt_vars[k] = v
    elif k == 'ibias':           # Bias current → power
        opt_vars[k] = v
```

`*_L` and `*_WL_ratio` MUST be included. Gain is primarily
controlled by device lengths (intrinsic gain gm/gds scales with L),
so excluding them limits the optimizer to current redistribution
only — insufficient for meaningful gain improvement. Including all
variables gives ~21 dimensions (exact count depends on topology).

For higher-dimensional spaces (>15 vars), use:
- **σ₀ = 0.1** (not 0.2) to keep initial perturbations local
- **λ = 32** (not 16) for better population coverage
- **max_gen = 20** for convergence

Mirror constraints must be enforced inside the objective function
(e.g., M5/M6/M8 share L and WL_ratio in TSM).

### Step 6 — Post-Optimization Verification

After the optimizer converges:

1. Run `simulate_circuit` with the optimized `params` one final time.
2. Verify ALL constraints are satisfied.
3. If any constraint is violated by more than 1%:
   - Increase penalty weight (`k *= 10`)
   - Re-run for 5 more generations from the current best.

### Step 7 — Return Results

Return the following to the caller (`design-review.md` Step 4):

- `optimized_params`: the optimized `params` dict
- `optimized_specs`: the simulation specs from the final verification
- `llm_specs`: the reference specs from the LLM design
- `n_evals`: total simulation calls
- `runtime_s`: elapsed time in seconds
- `improved`: boolean — whether the optimized cost is lower than LLM

If the optimized design is worse than the LLM sizing (cost did not
decrease), set `improved = False`. The design-review will keep the
LLM sizing and skip Section 6.

The report formatting (Section 6) is handled by `design-review.md`,
not by this skill.

---

## Notes

- **Simulation budget**: ~640 calls (20 generations × 32 population).
  With 16-way parallelism (2 batches per generation), wall-clock
  time ≈ 8 min. Print progress after each generation.
- **Topology agnostic**: the optimizer works at the `params` dict level.
  It does not need to know about gm/ID, circuit equations, or role
  names. Any topology supported by `simulate_circuit` works.
- **Variable coupling**: CMA-ES adapts a covariance matrix that learns
  which variables move together (e.g., Rc must track Cc and gm7).
  No explicit coupling equations or fixup steps are needed.
- **Local optimization**: CMA-ES explores a neighborhood around the
  LLM starting point (controlled by sigma). This is by design — the
  LLM sizing is already a good solution, and we seek incremental
  improvement.
- **Power optimization**: primarily driven by `*_M` and `ibias`.
  `*_L` and `*_WL_ratio` also affect power indirectly through
  device efficiency (gm/ID at different L changes current needs).
- **Parallelism**: each generation's λ candidates are independent and
  evaluated concurrently via ThreadPoolExecutor. Each call uses a
  unique `output_dir` (tempfile) to avoid file-path conflicts.
  With λ=32 and 16 workers, each generation runs in 2 batches.
