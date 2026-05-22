# LLM-Assisted Analog Amplifier Sizing

An LLM-driven analog amplifier sizing system using **gm/ID methodology**, **ngspice SPICE simulation**, and **self iteration** on the SKY130 open-source PDK.

## Why this project?

LLMs can reason about circuits, but they cannot size them reliably. They lack of domain knowledge and PDK information, and have no way to verify whether a design actually works. Meanwhile, traditional analog sizing tools require deep expert knowledge to set up and iterate.

This project bridges the gap. It gives the LLM agent everything a human designer uses — **gm/ID look-up tables**, **analytical equations**, **SPICE simulation**, and **structured diagnosis** — so the agent can size circuits the way an expert would, but faster and without manual intervention.

What makes it work:

1. **gm/ID look-up tables** map operating-point targets directly to transistor dimensions — no manual BSIM4 model evaluation, no guessing W and L
2. **Procedural skill stack** encodes the complete design methodology as markdown files that any LLM agent can read and execute step by step
3. **SPICE-in-the-loop** verifies every sizing iteration against ngspice — the agent never reports a result it hasn't simulated
4. **Root-cause fault trees** link each spec failure to its root cause and recommended fix, with side-effect warnings and priority ordering
5. **Numerical optimizer** (CMA-ES / coordinate descent) fine-tunes the final sizing after the LLM converges

In a [controlled experiment](comparison_report_tsm_single.md) on a two-stage Miller OTA with 12 specs, the skill-equipped agent met all targets in 2 iterations. A bare LLM with the same model and tools but no skills failed to converge after 8 iterations, missing 2 specs.

## Architecture

```
User (specs + netlist)
        |
        v
+-------------------+     HTTP (port 8001)     +--------------------+
|   AnalogAgent     | <--------------------->  |  CircuitCollector  |
|                   |                          |                    |
|  - LLM reasoning  |    /simulate/            | - Testbench gen    |
|  - gm/ID LUT      |    /register_circuit/    | - ngspice runner   |
|  - Skill stack    |    /health               | - Result parser    |
|  - Optimizer      |                          | - SKY130 PDK       |
+-------------------+                          +--------------------+
```

| Component | What it does |
|-----------|-------------|
| **AnalogAgent** | LLM agent with gm/ID LUTs, design skills, simulation bridge, optimizer |
| **CircuitCollector** | FastAPI server that generates testbenches, runs ngspice, parses results |

## Supported topologies

| Topology | Variants | Example netlist |
|----------|----------|-----------------|
| 5-Transistor OTA | single, cascode, wide-swing cascode | `examples/5tota_variants/` |
| Two-Stage Miller OTA | single, cascode, wide-swing cascode | `examples/tsm_variants/` |

Custom netlists are also supported. Drop a `.sp` SPICE subcircuit and the agent will parse the topology, register it, and size it.

## Using the sizing flow

Fill in `spec-form-template.md` with your targets, then prompt the agent:

```
Use the skills to size the 5tota_single; use the specs in the template.
```

The agent reads the skill stack in `skills/analog-amplifier/`, identifies the topology, and runs the full flow:

1. Spec validation 
2. Topology identification from the netlist
3. gm/ID-based initial sizing with LUT queries
4. Analytical pre-screening (poles, zeros, PM, gain, all specs)
5. SPICE simulation via CircuitCollector
6. Root-cause diagnosis and iterative fix (up to 10 iterations)
7. Design review with analytical vs SPICE comparison
8. Optional extreme PVT check (SS/85C + FF/-40C)
9. Optional numerical optimization (CMA-ES)

### Agent compatibility

| Platform | Entry file | How it works |
|----------|-----------|--------------|
| **Claude Code** | `CLAUDE.md` | Auto-loaded at session start |
| **Codex** | `AGENTS.md` | Auto-loaded at session start |
| **Cursor / Windsurf** | `.cursorrules` | Copy content from `CLAUDE.md` |
| **Other LLM agents** | -- | Tell the agent: "Read `CLAUDE.md` first" |

All entry files point to the same skill stack. `skills/analog-amplifier/SKILL.md` is the single source of truth.

## Repository structure

```
AnalogAgent/
  skills/analog-amplifier/            Procedural skill stack (design flow, equations, fault trees)
  tools/                              Simulation bridge, optimizer, topology manager
  scripts/                            gm/ID LUT query API
  asset_new/                          Pre-computed LUT data (nfet/pfet, 5 corners, 3 temps)
  examples/                           Reference netlists (5T OTA + TSM, 3 variants each)
  agent/                              Programmatic agent entry point (Anthropic API)
  spec-form-template.md               User-facing spec form
  setup_and_run.ipynb                 Step-by-step setup and run notebook
  comparison_report_tsm_single.md     AnalogAgent vs pure-LLM controlled experiment
  README.md                           AnalogAgent documentation

CircuitCollector/
  CircuitCollector/                   Main package (API, runner, cache, templates, PDK)
  setup.py                            Package installation
  README.md                           CircuitCollector documentation
```

See [AnalogAgent/README.md](README.md) and [CircuitCollector/README.md](../CircuitCollector/README.md) for detailed documentation of each component.

## Tools and versions

| Tool | Version | Purpose |
|------|---------|---------|
| ngspice | 46 | SPICE simulation |
| SKY130 PDK | Open-source | 130nm process (bundled) |
| Python | 3.11 | Agent logic, gm/ID LUT queries |
| FastAPI | 0.118+ | Simulation server |
| Conda/Miniforge | Latest | Environment management |

## Contributors

| Name | Affiliation | Email |
|------|-------------|-------|
| Jiyuan Duan    | Rice University              | jd200@rice.edu          |
| Shikai Wang    | George Washington University | shikai.wang@gwu.edu     |
| Gerald Topalli | Rice University              | gerald.topalli@rice.edu |
| Houbo He       | Rice University              | houbo.he@rice.edu       |
| Lei Xia        | Rice University              | lx27@rice.edu           |
| Weidong Cao    | George Washington University | weidong.cao@gwu.edu     |
| Taiyun Chi     | Rice University              | taiyun.chi@rice.edu     |

## References

- P. G. A. Jespers and B. Murmann, *Systematic Design of Analog CMOS Circuits: Using Pre-Computed Lookup Tables*. Cambridge University Press, 2017.
- Razavi, B. 2000a. Design of Analog CMOS Integrated Circuits. McGraw-Hill, Inc.
- SkyWater SKY130 Open-Source PDK: https://github.com/google/skywater-pdk
- ngspice Open-Source SPICE Simulator: https://ngspice.sourceforge.io/

## License

MIT
