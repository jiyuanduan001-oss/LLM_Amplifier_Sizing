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
- **Mirror** devices share the same per-instance W/L as the reference.
  Their current is set by the multiplier M.

**Matched pair detection:**

Devices that must match exactly (same W, L, M) form a matched pair:
- Differential pair (M3/M4): both gates are signal inputs
- Active load mirror (M1/M2): one diode, one mirror
- Any symmetric pair with complementary signal connections

Matched pairs share a single parameter prefix in the netlist template
(e.g., both M1 and M2 use `{{ M1_L }}`, `{{ M1_W }}`, `{{ M1_M }}`).

### Step 2b — Mirror/Load Sub-Block Detection (5T OTA and TSM only)

Applies to roles that are current mirrors or active loads: `LOAD`, `TAIL`,
`OUTPUT_BIAS`, `BIAS_GEN`. Each such role is realized as one of three
sub-block types (see `general/knowledge/mirror-load-structures.md`):

- `single`: one transistor (default, backward compatible)
- `cascode`: two stacked transistors, both gates in the mirror/diode chain (self-biased)
- `lv_cascode`: two stacked transistors, main.gate = cas.drain, cas.gate = external bias port

Other topologies (e.g. telescopic, folded-cascode) may have dedicated
cascode roles and would NOT be processed by this step.

**Detection algorithm (per mirror/load role):**

The algorithm is polarity- and role-agnostic. The "external output/signal
node" is whichever net the sub-block drives:

| Role | Rail | Output node |
|------|------|-------------|
| `LOAD` (PMOS)      | VDD | amplifier output (e.g. `vout`, `net5` in TSM) |
| `OUTPUT_BIAS` (NMOS) | VSS | amplifier output |
| `TAIL` (NMOS)      | VSS | diff-pair source node (e.g. `net2`) |
| `BIAS_GEN` (NMOS)  | VSS | bias reference node |

For each candidate main device `M_main` identified in Step 2:

```
Look for a device M_cas in the netlist such that:
  - same type as M_main (both NMOS or both PMOS)
  - M_cas.source == M_main.drain                    (stacked in series)
  - M_cas.drain  == external output/signal node     (see table above)

If no M_cas found:
  → sub_block_type = "single"
  → no cascode companion role created

If M_cas found, inspect gate wiring:
  if M_main.gate is in the mirror/diode chain
     AND M_cas.gate is in the mirror/diode chain
       → sub_block_type = "cascode"
  elif M_main.gate == M_cas.drain (== output node)
     AND M_cas.gate is a top-level subcircuit port
       → sub_block_type = "lv_cascode"
  else:
       → ambiguous wiring. Stop and report to user.
```

**Example — NMOS lv_cascode TAIL:**

```spice
* Tail cascode pair (NMOS, rail = gnda = VSS):
XM3  net2     net3          net_tmid  gnda  nfet_01v8  ← cas: drain=net2, source=net_tmid
XM3m net_tmid Vbias_cas_n   gnda      gnda  nfet_01v8  ← main: drain=net_tmid, source=gnda
```
Here the roles are: TAIL primary = `M3m`, TAIL_CAS = `M3`; `extra_ports`
emits `Vbias_cas_n`. Some netlists place the external-bias device as the
top one (gate=port) and the bias-chain device at the bottom
(gate=net3) — the Sooch signature `main.gate == cas.drain` still
identifies the structure correctly regardless of which device is labelled
`M3` vs `M3m`.

If a cascode is detected, assign `M_cas` the role `<MAIN_ROLE>_CAS`
(e.g., `LOAD_CAS`, `TAIL_CAS`). Record `sub_block_type` on the main role
entry in the role_device_map. For `lv_cascode`, also record the external
bias port name in a topology-level `extra_ports` field.

**Important**: the companion `_CAS` role carries the same DC current as
its parent but is **sized independently** (different gm/ID and L). It is
NOT a current mirror of the parent; it is a series element. Do not add
`mirror_of` on the `_CAS` role. See Step 4 below.

### Step 3 — Generate Parameterized Netlist

Convert the user's netlist to a Jinja2-parameterized template. This is
the **netlist.j2** that CircuitCollector will use for simulation.

**Rules:**

1. **Subcircuit header**: Must be `.subckt {{netlist_name}} gnda vdda vinn vinp vout Ib [extra_ports...]`
   - Port order: gnda, vdda, vinn, vinp, vout, Ib (fixed by testbench)
   - Add `Ib` if missing
   - If any role has `sub_block_type == "lv_cascode"`, append its
     external bias ports (e.g. `Vbias_cas_n`, `Vbias_cas_p`) at the end
   - Replace the original subcircuit name with `{{netlist_name}}`

2. **MOSFETs**: Replace W/L/M with Jinja2 variables.
   - Each unique sizing group gets a prefix (e.g., `M1`, `M3`, `M5`)
   - Matched pairs share the same prefix
   - Format: `l={{ Mx_L }} w={{ Mx_W }} m={{ Mx_M }}`

3. **Passives**: Use `{{ Cx_value }}` for capacitors, `{{ Rx_value }}` for resistors.
   - If already parameterized (e.g., `{{ C1_value }}`), keep as-is.
   - If the netlist uses a named passive like `Rc`, use `{{ Rc_value }}`.

4. **Bias current source and `Ib` port**:
   The testbench creates an external current *sink* at the `Ib` port
   (`Ib Ib vss DC='IBIAS'` — current flows FROM Ib TO vss). The `Ib`
   port is NOT a current source into the circuit. The subcircuit must
   keep its own internal current source from vdda to the bias node.
   - Quote the parameter reference for ngspice HSA compatibility:
     `I0 vdda <bias_node> 'IBIAS'`
   - Tie the `Ib` port to ground with a dummy resistor to prevent a
     floating node: `Rdum_Ib Ib gnda 1`

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
        "primary":        "<Mx>",              # Primary device prefix
        "mirrors":        ["<My>", ...],        # TOML mosfet_pairs handles these
        "device_type":    "nfet"|"pfet",        # For LUT queries
        "mirror_of":      "<ROLE_NAME>",        # (optional) current-mirror ref
        "sub_block_type": "single"|"cascode"|"lv_cascode",  # (optional, mirror/load roles only)
    },
    # Cascode companion role (only present if sub_block_type != "single"):
    "<ROLE_NAME>_CAS": {
        "primary":      "<Mx>",
        "mirrors":      ["<My>", ...],
        "device_type":  "nfet"|"pfet",
        "parent_role": "<ROLE_NAME>",           # marks this as a cascode companion
    },
    ...
}
```

**Rules:**
- `primary` is the device prefix used in `{{ Mx_L }}` parameters
- `mirrors` lists devices that share the exact same W/L/M (matched pairs,
  handled by TOML `mosfet_pairs`)
- `mirror_of` indicates a current-mirror relationship where this role
  shares per-instance W/L with the reference role, and uses multiplier M to set
  the current ratio. The generic bridge handles this automatically.
- `device_type` is `"nfet"` or `"pfet"` based on the model string
- `sub_block_type` records the detected mirror/load structure (default
  `"single"`). Only applies to roles that are mirrors or active loads.
- `parent_role` on a `_CAS` role identifies which main role this cascode
  device belongs to. The `_CAS` role does NOT have `mirror_of` — it is
  sized independently (same current, different gm/ID and L).

**Also determine:**
- `requires_Cc`: True if the netlist has a compensation capacitor
- `passive_params`: List of passive parameter names found in the netlist
  (e.g., `["C1_value", "Rc_value"]`)
- `topology_name`: Filesystem-safe identifier for registration
  (e.g., `"tsm"`, `"5tota"`)
- `extra_ports`: List of additional subcircuit ports needed beyond the
  standard `(gnda, vdda, vinn, vinp, vout, Ib)`. Required when any role
  has `sub_block_type == "lv_cascode"` — add one port per LV cascode pair
  (e.g. `["Vbias_cas_n"]` or `["Vbias_cas_n", "Vbias_cas_p"]`).

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
    extra_ports=extra_ports,               # (optional) LV cascode bias ports
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

Sub-block structures (mirror/load roles only):
  <ROLE>  : single / cascode / lv_cascode  [→ companion <ROLE>_CAS → <Mx>]
  ...

Extra subcircuit ports: <list or "none">
Passive params: <list or "none">

Activated design flow: circuit-specific/<dir>/<name>-design-flow.md
```

**GATE**: If topology is "NOT MATCHED", do NOT proceed.

## Next Stage

→ Read and execute `circuit-specific/<dir>/<name>-design-flow.md`.
