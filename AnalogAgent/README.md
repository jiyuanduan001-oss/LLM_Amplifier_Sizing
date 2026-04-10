# AnalogAgent

LLM-guided gm/Id methodology sizing agent.

## Installation

**Prerequisites**: place `AnalogAgent` and `CircuitCollector` side by side under the same parent directory:

```markdown
parent/
├── AnalogAgent/
└── CircuitCollector/
```

**Create the conda environment**:

```bash
cd AnalogAgent
conda env create -f environment.yml
conda activate Agent
```

**Create a `.env` file** with your Anthropic API key:

```bash
echo "ANTHROPIC_API_KEY=<your_api_key>" > .env
```

OR you can manually create the file in the root directory.

```bash
touch .env
```

And write the API key in the file.

```bash
ANTHROPIC_API_KEY=<your_api_key>
```

> `.env` is listed in `.gitignore` and will not be committed.

---

## Structure

```markdown
skills/       # Sizing skill descriptions (MD format)
luts/         # Device LUT CSV files: <device>_L<nm>.csv
scripts/      # Python: LUT lookup + gm/Id formulas
tools/        # API client -> local FastAPI simulation server
agent/        # Agent orchestration + trace collection
traces/       # Reasoning traces for post-training (gitignored)
```

## Simulation API

Local FastAPI server at `http://localhost:8001`.

**Request** `POST /simulate`:

```json
{
  "role": "input_pair",
  "device_type": "nmos",
  "params": { "gm_id": 15, "id_ua": 50, "l_nm": 180 }
}
```

**Response**:

```json
{
  "specs": { "gm": 7.5e-4, "gds": 1.2e-5, "cgg": 8e-15, "ft": 14.9e9 },
  "op": { "vgs": 0.52, "vds": 0.4, "vth": 0.38, "vdsat": 0.12 }
}
```

## LUT Format

CSV files in `luts/`, named `<device_type>_L<l_nm>.csv`
(e.g. `nmos_L180.csv` for NFET at L=180 nm).

| gm_id | id_w  | cgg_w | ft   | gds_gm |
| ----- | ----- | ----- | ---- | ------ |
| 5.0   | 120.0 | 1.8   | 85.0 | 0.08   |
| ...   | ...   | ...   | ...  | ...    |

- `gm_id`: gm/Id (S/A) — index axis, independent variable
- `id_w`: Id/W (uA/um)
- `cgg_w`: Cgg/W (fF/um)
- `ft`: transit frequency (GHz)
- `gds_gm`: **gds/gm** (dimensionless, small number e.g. 0.08)

> **Column naming note:** The stored column is `gds_gm` = gds/gm.
> Skills reference `gm_gds` = gm/gds (intrinsic gain, large number e.g. 12.5).
> These are reciprocals. **Do not rename the column.**
> `lut_query(metric='gm_gds')` inverts it automatically.

## LUT Query API (`scripts/lut_query.lut_query`)

```python
lut_query(device, metric, L, gm_id_val=None)
```

- `device`: `'nfet'` or `'pfet'`
- `metric`: `'gm_gds'`, `'id_w'`, `'cgg_w'`, `'ft'`, or `'gm_id'`
- `L`: channel length in **micrometers** (e.g. `0.18` for 180 nm)
- `gm_id_val`: if provided → returns single float (interpolated); if omitted → returns full curve DataFrame

## Run the agent

Run the agent with the following command and display the output in the terminal.

```bash
conda activate Agent
python -u run_agent.py
```

---

## Slash Command: `/size-ota`

The fastest way to run a full 5T OTA sizing flow inside **Claude Code**.

### Syntax

```
/size-ota GBW=<Hz> A0=<dB> CL=<F> VDD=<V> Ib=<A>
```

### Example

```
/size-ota GBW=50MHz A0=36dB CL=5pF VDD=1.8V Ib=20uA
```

### What it does

1. Parses specs and selects the inversion region for the differential pair.
2. Sweeps L (0.18–5 µm) via `lut_query` to find the minimum L where `A0_upper ≥ A0_target + 3 dB`.
3. Runs `tools/bridge.py` (full sizing → SPICE simulation → OP extraction pipeline).
4. Evaluates six exit-criteria flags: `A0`, `GBW`, `PM`, `tail_VDS_margin`, `bias_mismatch`, `all_saturated`.
5. Iterates (up to 5 rounds) adjusting `l_overrides` until all flags pass.
6. Outputs a final role-level sizing table and SPICE-verified specs.

### Requirements

- CircuitCollector FastAPI server running at `http://localhost:8000`
- `conda` environment `Agent` activated (or `conda run -n Agent` prefix used internally)

### Known design constraints

| Condition | Effect |
|-----------|--------|
| Large GBW × CL with small Ib | Mirror ratio (I_tail / Ib) >> 8 — M3 VDS headroom risk |
| Long L (needed for A0) | Parasitic output capacitance reduces SPICE GBW below formula estimate |
| Iterating to shorter L for GBW | Reduces tail VDS margin — monitor `tail_VDS_margin` flag |

---

## Python CLI Tools

All scripts output JSON to stdout. Run via `conda run -n Agent python -m <module>`.

### LUT Lookup

```bash
conda run -n Agent python -m scripts.lut_lookup \
  --device nfet \       # nfet | pfet
  --metric gm_gds \     # gm_gds | id_w | cgg_w | ft | gm_id
  --L 0.5 1.0 2.0 \     # one or more L values in µm
  --gm_id 12.5          # optional: interpolate at this gm/ID operating point
```

### Sizing Engine (analytical, no simulation)

```bash
conda run -n Agent python -m scripts.sizing_engine \
  --GBW 50e6 \          # Hz
  --A0 63.1 \           # linear V/V  (convert dB: 10^(dB/20))
  --CL 5e-12 \          # F
  --VDD 1.8 \           # V
  --Ib 20e-6            # A
```

Optional overrides: `--PM 60 --L_dp 1.0 --L_load 1.0 --L_tail 3.0`

### Full Pipeline (sizing + SPICE simulation)

```bash
conda run -n Agent python -m tools.bridge \
  --GBW 50e6 \
  --A0 63.1 \
  --CL 5e-12 \
  --VDD 1.8 \
  --Ib 20e-6 \
  --l_overrides '{"DIFF_PAIR": 1.0, "LOAD": 1.0, "TAIL": 3.0, "BIAS_REF": 3.0}'
```

Returns JSON with `sizing`, `sim_params`, `specs`, `transistors`, `flags`, and `recommendations`.

> **Note:** `--A0` is always linear V/V. To convert from dB: `python -c "print(10**(36/20))"` → `63.1`
