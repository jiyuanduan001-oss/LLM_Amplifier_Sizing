# Circuit Understanding Skill

## Purpose

Given a circuit netlist, identify the topology, assign roles to devices,
produce a parameterized netlist template, and register it for simulation.

This skill bridges the gap between a raw user netlist and the simulation
pipeline. It outputs two structured artifacts:
1. **Parameterized netlist** (`netlist.j2`) — Jinja2 template with `{{ Mx_L }}`,
   `{{ Mx_W }}`, `{{ Mx_M }}` placeholders
2. **Role-device map** — structured dict mapping circuit roles to devices

These artifacts feed directly into `ensure_topology_registered()` to make
the topology simulatable.

## Supported Topologies

| Pattern | Classification | Directory |
|---|---|---|
| Diff pair + mirror load, single output node | 5T OTA | `circuit-specific/5TOTA/` |
| Diff pair + mirror load + CS stage + Miller cap | Two-Stage Miller (TSM) | `circuit-specific/tsm/` |
| Diff pair + cascode output, same-type stack, no fold | Telescopic OTA (TCO) | `circuit-specific/telescopic/` |
| Diff pair folded into opposite-type cascode output | Folded-Cascode OTA (FC-OTA) | `circuit-specific/folded cascode/` |
| Complementary N+P diff pairs + gm-control + class-AB output | Rail-to-Rail Opamp (R2R) | `circuit-specific/rtr/` |

## Accepted Netlist Formats

The skill accepts any of these formats:

| Format | Example | How to detect |
|---|---|---|
| **Bare** | `XM1 net1 net1 vdda vdda sky130_fd_pr__pfet_01v8` | No W/L/M params at all |
| **Literal** | `... l=0.15 w=1.0 m=2` | Numeric W/L/M values |
| **Passive-only** | MOSFETs bare, but `{{ Rc_value }}`, `{{ C1_value }}` | Mixed |
| **Jinja2** | `... l={{ M1_L }} w={{ M1_W }} m={{ M1_M }}` | `{{ Mx_ }}` patterns |
| **MOSFET_expr** | `... l=MOSFET_1_L w=MOSFET_1_W` | `MOSFET_<n>_` patterns |

All formats are converted to the Jinja2 format in Step 3.

## Procedure

### Step 1 — Parse Netlist and Identify Topology

Parse the netlist to identify:
1. **Device inventory**: count NMOS, PMOS, passives (R, C).
2. **Supply and ground nets**: VDD, VSS/GND.
3. **Signal I/O**: input nodes (vinn, vinp), output node (vout).
4. **Device connections**: for each MOSFET, record drain, gate, source, bulk.

Match the identified structure against the supported topologies table.

If the netlist does NOT match any supported topology:
→ **STOP.** Print: "Topology not supported. Supported types: [list]."
→ Do NOT attempt to size it with first-principles reasoning.

If ambiguous between two topologies, state the ambiguity and ask the user.

### Step 2 — Assign Roles to Devices

For each device in the netlist, assign a functional role based on its
connections and position in the circuit. Use the topology-specific
knowledge to guide role assignment.

**Standard role vocabulary** (use these names consistently):

| Role | Description | Detection heuristic |
|---|---|---|
| `DIFF_PAIR` | Input differential pair | Gates connect to vinn/vinp |
| `LOAD` | Active load (current mirror) | Drains connect to diff pair drains; diode + mirror |
| `BIAS_GEN` | Bias reference (diode-connected) | Gate = drain, current source connects to it |
| `TAIL` | Tail current source | Connects to diff pair sources; mirrors BIAS_GEN |
| `OUTPUT_CS` | Common-source output stage | Gate driven by 1st-stage output; drain = vout |
| `OUTPUT_BIAS` | Output stage current source | Drain = vout; mirrors BIAS_GEN |
| `CASCODE_N` | NMOS cascode device | Stacked between diff pair and load |
| `CASCODE_P` | PMOS cascode device | Stacked above load or in folded path |
| `CMFB` | Common-mode feedback device | Senses output CM and adjusts bias |

Not all roles apply to every topology. Use only the roles that exist
in the identified topology.

**Mirror group detection:**

Devices that share the same W/L sizing form a mirror group. Detect by:
- Same gate net (current mirror)
- One device is diode-connected (gate = drain) → it's the reference
- Other devices in the group are mirrors

Within a mirror group:
- The **reference** device (diode-connected or primary) gets its own
  parameter prefix and is sized independently.
- **Mirror** devices share the same per-finger W/L as the reference.
  Their current is set by the finger multiplier M.

**Matched pair detection:**

Devices that must match exactly (same W, L, M) form a matched pair:
- Differential pair (M3/M4): both gates are signal inputs
- Active load mirror (M1/M2): one diode, one mirror
- Any symmetric pair with complementary signal connections

Matched pairs share a single parameter prefix in the netlist template
(e.g., both M1 and M2 use `{{ M1_L }}`, `{{ M1_W }}`, `{{ M1_M }}`).

### Step 3 — Generate Parameterized Netlist

Convert the user's netlist to a Jinja2-parameterized template. This is
the **netlist.j2** that CircuitCollector will use for simulation.

**Rules:**

1. **Subcircuit header**: Must be `.subckt {{netlist_name}} gnda vdda vinn vinp vout Ib`
   - Port order: gnda, vdda, vinn, vinp, vout, Ib (fixed by testbench)
   - Add `Ib` if missing
   - Replace the original subcircuit name with `{{netlist_name}}`

2. **MOSFETs**: Replace W/L/M with Jinja2 variables.
   - Each unique sizing group gets a prefix (e.g., `M1`, `M3`, `M5`)
   - Matched pairs share the same prefix
   - Format: `l={{ Mx_L }} w={{ Mx_W }} m={{ Mx_M }}`

3. **Passives**: Use `{{ Cx_value }}` for capacitors, `{{ Rx_value }}` for resistors.
   - If already parameterized (e.g., `{{ C1_value }}`), keep as-is.
   - If the netlist uses a named passive like `Rc`, use `{{ Rc_value }}`.

4. **Bias current source**: Must use `Ib` as the current value.
   - `I0 vdda net3 Ib`

5. **Preserve topology**: Do NOT change device connections, node names,
   or circuit structure. Only parameterize the sizing values.

**Example** — bare netlist input:
```
.subckt tsm gnda vdda vinn vinp vout Ib
XM2 net5 net1 vdda vdda sky130_fd_pr__pfet_01v8
XM3 net1 vinn net2 gnda sky130_fd_pr__nfet_01v8
XM1 net1 net1 vdda vdda sky130_fd_pr__pfet_01v8
XM4 net5 vinp net2 gnda sky130_fd_pr__nfet_01v8
...
```

**Example** — parameterized output:
```
.subckt {{netlist_name}} gnda vdda vinn vinp vout Ib
XM2 net5 net1 vdda vdda sky130_fd_pr__pfet_01v8 l={{ M1_L }} w={{ M1_W }} m={{ M1_M }}
XM3 net1 vinn net2 gnda sky130_fd_pr__nfet_01v8 l={{ M3_L }} w={{ M3_W }} m={{ M3_M }}
XM1 net1 net1 vdda vdda sky130_fd_pr__pfet_01v8 l={{ M1_L }} w={{ M1_W }} m={{ M1_M }}
XM4 net5 vinp net2 gnda sky130_fd_pr__nfet_01v8 l={{ M3_L }} w={{ M3_W }} m={{ M3_M }}
...
```

Note: M1 and M2 share prefix `M1` (matched load pair). M3 and M4 share
prefix `M3` (matched diff pair).

### Step 4 — Build Role-Device Map

Construct a Python dict that maps each role to its device(s). This dict
is used by the generic bridge for sizing conversion.

**Format:**

```python
role_device_map = {
    "<ROLE_NAME>": {
        "primary":     "<Mx>",         # Primary device prefix
        "mirrors":     ["<My>", ...],   # TOML mosfet_pairs handles these
        "device_type": "nfet"|"pfet",   # For LUT queries
        "mirror_of":   "<ROLE_NAME>",   # (optional) if this role mirrors another
    },
    ...
}
```

**Rules:**
- `primary` is the device prefix used in `{{ Mx_L }}` parameters
- `mirrors` lists devices that share the exact same W/L/M (matched pairs,
  handled by TOML `mosfet_pairs`)
- `mirror_of` indicates a current-mirror relationship where this role
  shares per-finger W/L with the reference role, and uses M to set
  the current ratio. The generic bridge handles this automatically.
- `device_type` is `"nfet"` or `"pfet"` based on the model string

**Also determine:**
- `requires_Cc`: True if the netlist has a compensation capacitor
- `passive_params`: List of passive parameter names found in the netlist
  (e.g., `["C1_value", "Rc_value"]`)
- `topology_name`: Filesystem-safe identifier for registration
  (e.g., `"tsm"`, `"5tota"`, `"tco"`, `"fc_ota"`, `"r2r"`)

### Step 5 — Register Topology and Output

Call `ensure_topology_registered()` to register the topology with
CircuitCollector. This creates the netlist.j2 and TOML config files
automatically.

```python
from tools import ensure_topology_registered

result = ensure_topology_registered(
    topology_name=topology_name,
    raw_netlist=parameterized_netlist,     # from Step 3
    role_device_map=role_device_map,       # from Step 4
    requires_Cc=requires_Cc,
    passive_params=passive_params,
)
```

Then print the mandatory output:

```
CIRCUIT IDENTIFICATION
=======================
Topology      : <name>
Match         : circuit-specific/<dir>/
Devices       : <count> NMOS, <count> PMOS [, <count> passives]
Registration  : <created / already_exists>
Config path   : <config_path>

Role-Device Map:
  <ROLE>  → <primary> [+ <mirrors>] (<device_type>) [mirrors <REF_ROLE>]
  ...

Passive params: <list or "none">

Activated design flow: circuit-specific/<dir>/<name>-design-flow.md
```

**GATE**: If topology is "NOT MATCHED", do NOT proceed.

## Next Stage

→ Read and execute `circuit-specific/<dir>/<name>-design-flow.md`.
