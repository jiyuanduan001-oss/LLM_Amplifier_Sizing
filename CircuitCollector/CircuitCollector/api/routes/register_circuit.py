"""
Endpoint to dynamically register a new circuit topology.

Accepts a raw .subckt netlist, converts it to a Jinja2 template (netlist.j2),
generates the TOML config from netlist.j2, and writes both to the standard
CircuitCollector directory layout so the existing simulation pipeline works.

Flow:
  1. Detect netlist format (already-parameterized vs raw MOSFET expressions)
  2. Convert to netlist.j2 + notice.txt using convert_netlist logic
  3. Generate TOML from netlist.j2 + notice.txt using generate_toml logic
  4. Augment TOML with full testbench sections (noise, slew, swing)
  5. Write files to circuits/opamp/{name}/ and config/skywater/opamp/
"""

from __future__ import annotations

import asyncio
import logging
import re
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException

from ..schemas import RegisterCircuitRequest, RegisterCircuitResponse
from ...utils.path import PROJECT_ROOT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/register_circuit", tags=["register_circuit"])

# ---------------------------------------------------------------------------
# Import conversion functions from the repo-level scripts directory.
# These are standalone scripts; import their pure functions directly.
# ---------------------------------------------------------------------------
import importlib.util
import sys

_SCRIPTS_DIR = PROJECT_ROOT.parent / "scripts"


def _import_script(name: str):
    """Import a script from the repo-level scripts/ directory."""
    spec = importlib.util.spec_from_file_location(
        name, _SCRIPTS_DIR / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_convert_netlist = _import_script("convert_netlist")
_generate_toml = _import_script("generate_toml_from_netlist")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JINJA_PARAM_RE = re.compile(r"\{\{\s*M\d+_[LWM]")
_MOSFET_EXPR_RE = re.compile(r"MOSFET_\d+_")


def _detect_format(netlist: str) -> str:
    """Detect netlist format: 'jinja2', 'mosfet_expr', or 'literal'."""
    if _JINJA_PARAM_RE.search(netlist):
        return "jinja2"
    if _MOSFET_EXPR_RE.search(netlist):
        return "mosfet_expr"
    return "literal"


def _generate_notice_from_j2(netlist_j2: str) -> str:
    """
    Generate notice.txt content from an already-parameterized netlist.j2.

    Groups devices by their shared {{ Mx_ }} prefix. Labels differential
    pairs based on gate connections to vinn/vinp.
    """
    prefix_re = re.compile(r"l=\{\{\s*(M\d+)_L\s*\}\}")
    gate_re = re.compile(r"^[xX]?[mM]\d+\s+\S+\s+(\S+)")  # 3rd token = gate

    # Map prefix -> list of instance names
    prefix_to_instances: Dict[str, List[str]] = {}
    # Map prefix -> set of gate nets
    prefix_to_gates: Dict[str, set] = {}

    for line in netlist_j2.splitlines():
        s = line.strip()
        if not s or s.startswith(("*", ";", ".", "//")):
            continue
        m_prefix = prefix_re.search(s)
        if not m_prefix:
            continue
        prefix = m_prefix.group(1)
        tokens = s.split()
        inst = tokens[0]
        # Normalize: XM3 -> M3, xm3 -> M3
        inst_match = re.match(r"^[xX]?[mM](\d+)$", inst)
        inst_name = f"M{inst_match.group(1)}" if inst_match else inst.upper()

        prefix_to_instances.setdefault(prefix, []).append(inst_name)

        m_gate = gate_re.match(s)
        if m_gate:
            prefix_to_gates.setdefault(prefix, set()).add(m_gate.group(1).lower())

    lines: List[str] = []
    for prefix in sorted(prefix_to_instances.keys()):
        insts = sorted(prefix_to_instances[prefix])
        gates = prefix_to_gates.get(prefix, set())
        if gates & {"vinn", "vinp"}:
            label = "differential pair"
        else:
            label = prefix.lower()
        lines.append(f"{label}: {', '.join(insts)}")

    return "\n".join(lines) + "\n"


# Extra TOML sections that generate_toml_from_netlist.py doesn't produce
# but are needed for full simulation (noise, slew rate, output swing).
_EXTRA_TOML_SECTIONS = """
[testbench.noise]
measure_noise = true
noise_fstart = 0.1
noise_fstop = "1G"
noise_fspot = 10000

[testbench.slew_rate]
measure_slew_rate = true
sr_vstep = 0.5
sr_tdelay = "10n"
sr_trise = "1n"
sr_tfall = "1n"
sr_tpw = "5u"
sr_tperiod = "10u"
sr_tstep = "1n"
sr_tstop = "20u"

[testbench.output_swing]
measure_output_swing = true
swing_vstep = 0.001

[testbench.data]
data_DC = "DC"
data_AC = "AC"
data_GBW_PM = "GBW_PM"
data_NOISE = "NOISE"
data_SLEW_RATE = "SLEW_RATE"
data_OUTPUT_SWING = "OUTPUT_SWING"
"""


def _augment_toml(toml_text: str) -> str:
    """
    Add missing testbench sections to generated TOML.

    The generate_toml_from_netlist script produces a minimal TOML with only
    DC/AC/ibias/data sections. We need to add noise, slew_rate, output_swing,
    and the full data block for the simulation pipeline to run all measurements.
    """
    # Replace the minimal [testbench.data] block with the full one
    # Find and remove existing [testbench.data] section
    lines = toml_text.split("\n")
    out_lines: List[str] = []
    skip_section = False
    for line in lines:
        if line.strip().startswith("[testbench.data]"):
            skip_section = True
            continue
        if skip_section and line.strip().startswith("["):
            skip_section = False
        if skip_section:
            continue
        out_lines.append(line)

    # Also set VCM_ratio and temperature in [testbench.dc] if not present
    result = "\n".join(out_lines)
    if "VCM_ratio" not in result:
        result = result.replace(
            "supply_voltage = 1.8",
            "supply_voltage = 1.8\nVCM_ratio = 0.5\ntemperature = 27",
        )

    # Append extra sections
    result = result.rstrip() + "\n" + _EXTRA_TOML_SECTIONS

    return result


def _do_register(
    raw_netlist: str, topology_name: str, circuit_type: str
) -> Tuple[str, str, str, str]:
    """
    Core registration logic (synchronous).

    Returns: (config_path, netlist_j2_path, status, message)
    """
    circuit_dir = PROJECT_ROOT / "circuits" / circuit_type / topology_name
    config_path_rel = f"config/skywater/{circuit_type}/{topology_name}.toml"
    config_path_abs = PROJECT_ROOT / config_path_rel
    netlist_j2_path_rel = f"circuits/{circuit_type}/{topology_name}/netlist.j2"
    netlist_j2_abs = circuit_dir / "netlist.j2"
    notice_abs = circuit_dir / "notice.txt"

    # Check if already exists with same content
    if netlist_j2_abs.exists() and config_path_abs.exists():
        existing = netlist_j2_abs.read_text()
        fmt = _detect_format(raw_netlist)
        if fmt == "jinja2" and existing.strip() == raw_netlist.strip():
            return (
                config_path_rel,
                netlist_j2_path_rel,
                "already_exists",
                "Topology already registered with identical netlist",
            )
        # Different content: proceed to overwrite

    # Step 1: Convert to netlist.j2 based on format
    fmt = _detect_format(raw_netlist)
    logger.info(
        "Registering topology '%s' (format: %s)", topology_name, fmt
    )

    if fmt == "jinja2":
        # Already a Jinja2 template — use as-is
        netlist_j2_text = raw_netlist
        notice_text = _generate_notice_from_j2(raw_netlist)
    elif fmt == "mosfet_expr":
        # Has MOSFET_<n> expressions — run convert_netlist
        lines = raw_netlist.splitlines()
        rewritten, notice_groups = _convert_netlist.rewrite_lines(lines)
        netlist_j2_text = "\n".join(rewritten) + "\n"
        notice_text = _convert_netlist.format_notice(notice_groups)
    else:
        raise ValueError(
            "Netlist has literal numeric W/L/M values. "
            "Please provide a parameterized netlist with {{ Mx_L }}, {{ Mx_W }}, "
            "{{ Mx_M }} Jinja2 placeholders or MOSFET_<n>_L/W/M expressions."
        )

    # Step 2: Write netlist.j2 and notice.txt
    circuit_dir.mkdir(parents=True, exist_ok=True)
    netlist_j2_abs.write_text(netlist_j2_text)
    notice_abs.write_text(notice_text)

    # Step 3: Generate TOML from netlist.j2 + notice.txt
    mos_instances, cap_values, resistor_values = (
        _generate_toml.collect_instances(netlist_j2_abs)
    )
    prefixes = sorted(
        {inst.prefix for inst in mos_instances if inst.prefix}
    )
    notice_groups = _generate_toml.parse_notice(notice_abs)

    toml_text = _generate_toml.render_toml(
        opamp_name=topology_name,
        prefixes=prefixes,
        mos_instances=mos_instances,
        notice_groups=notice_groups,
        cap_values=cap_values,
        resistor_values=resistor_values,
    )

    # Step 4: Augment with full testbench sections
    toml_text = _augment_toml(toml_text)

    # Step 5: Write TOML
    config_path_abs.parent.mkdir(parents=True, exist_ok=True)
    config_path_abs.write_text(toml_text)

    logger.info(
        "Registered topology '%s': %s, %s",
        topology_name,
        netlist_j2_path_rel,
        config_path_rel,
    )

    return (config_path_rel, netlist_j2_path_rel, "created", None)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=RegisterCircuitResponse,
    summary="Register a new circuit topology",
)
async def register_circuit(req: RegisterCircuitRequest):
    """
    Register a new circuit topology by providing its raw netlist.

    The endpoint converts the netlist to a Jinja2 template (netlist.j2),
    generates the corresponding TOML config, and writes both to the standard
    directory layout. After registration, the topology can be simulated via
    the normal /simulate/ endpoint.
    """
    try:
        config_path, netlist_j2_path, status, message = await asyncio.to_thread(
            _do_register,
            req.raw_netlist,
            req.topology_name,
            req.circuit_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Registration failed")
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Registration failed: {e}",
                "exception_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
        )

    return RegisterCircuitResponse(
        status=status,
        config_path=config_path,
        netlist_j2_path=netlist_j2_path,
        message=message,
    )
