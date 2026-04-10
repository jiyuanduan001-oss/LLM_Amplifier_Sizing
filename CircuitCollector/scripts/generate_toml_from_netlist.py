#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


MOS_LINE_RE = re.compile(r"^[xX]?[mM]\d+\b")
CAP_LINE_RE = re.compile(r"^[cC]_?C?\d+\b")
RESISTOR_LINE_RE = re.compile(r"^[rR]_?[rR]?\w+\b")


@dataclass
class MosInstance:
    name: str
    model: str
    prefix: str | None


def normalize_inst_name(name: str) -> str:
    match = re.match(r"^[xX]?[mM](\d+)$", name)
    if match:
        return f"M{match.group(1)}"
    return name.upper()


def parse_notice(notice_path: Path) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    if not notice_path.exists():
        return groups
    for raw in notice_path.read_text().splitlines():
        s = raw.strip()
        if not s:
            continue
        group_name = ""
        members_str = ""
        if ":" in s:
            group_name, members_str = [part.strip() for part in s.split(":", 1)]
        elif " w=" in s:
            members_str, w_str = [part.strip() for part in s.split(" w=", 1)]
            group_name = w_str.strip()
        else:
            members_str = s
        members = [
            normalize_inst_name(m.strip()) for m in members_str.split(",") if m.strip()
        ]
        if members:
            groups[group_name] = members
    return groups


def collect_instances(
    netlist_path: Path,
) -> Tuple[List[MosInstance], List[str], List[str]]:
    mos_instances: List[MosInstance] = []
    cap_values: List[str] = []
    resistor_values: List[str] = []
    for raw in netlist_path.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith(("*", ";", "//", ".")):
            continue
        tokens = s.split()
        if MOS_LINE_RE.match(s):
            name = normalize_inst_name(tokens[0])
            model = tokens[5] if len(tokens) > 5 else ""
            prefix = None
            # Search the full line — Jinja2 spaces split l={{ M1_L }} across tokens
            pfx_match = re.search(r"l=\{\{\s*(M\d+)_L\s*\}\}", s)
            if pfx_match:
                prefix = pfx_match.group(1)
            mos_instances.append(MosInstance(name=name, model=model, prefix=prefix))
            continue
        if CAP_LINE_RE.match(s):
            cap_match = re.search(r"\{\{\s*(C\d+_value)\s*\}\}", s)
            if cap_match:
                cap_values.append(cap_match.group(1))
            continue
        if RESISTOR_LINE_RE.match(s):
            res_match = re.search(r"\{\{\s*(R\w+_value)\s*\}\}", s)
            if res_match:
                resistor_values.append(res_match.group(1))
    return (
        mos_instances,
        sorted(set(cap_values)),
        sorted(set(resistor_values)),
    )


def is_pfet(model: str) -> bool:
    return "pfet" in model.lower()


def pfet_profile(group_name: str) -> Tuple[float, float, int, float]:
    name = group_name.lower()
    if "gm" in name:
        return 0.55, 20.0, 200, 60.0
    return 0.55, 10.0, 100, 30.0


def nfet_profile(group_name: str) -> Tuple[float, float, int, float]:
    name = group_name.lower()
    if "load" in name:
        return 0.42, 10.0, 200, 60.0
    if "gm4" in name:
        return 0.42, 20.0, 200, 80.0
    if "gm3" in name or "output" in name:
        return 0.42, 20.0, 400, 80.0
    return 0.42, 10.0, 100, 30.0


def group_name_for_prefix(prefix: str, notice_groups: Dict[str, List[str]]) -> str:
    for group_name, members in notice_groups.items():
        if prefix in members:
            return group_name
    return ""


def format_mosfet_pairs(notice_groups: Dict[str, List[str]]) -> List[str]:
    lines: List[str] = []
    for group_name, members in notice_groups.items():
        if len(members) < 2:
            continue
        key = members[0]
        rest = members[1:]
        if len(rest) == 1:
            lines.append(f'{key} = "{rest[0]}"')
        else:
            joined = ", ".join(f'"{m}"' for m in rest)
            lines.append(f"{key} = [{joined}]")
    return lines


def render_toml(
    opamp_name: str,
    prefixes: List[str],
    mos_instances: List[MosInstance],
    notice_groups: Dict[str, List[str]],
    cap_values: List[str],
    resistor_values: List[str],
) -> str:
    pfet_prefixes = set()
    nfet_prefixes = set()
    for inst in mos_instances:
        if inst.prefix is None:
            continue
        if is_pfet(inst.model):
            pfet_prefixes.add(inst.prefix)
        else:
            nfet_prefixes.add(inst.prefix)

    ranges: List[str] = []
    params: List[str] = []

    for pref in prefixes:
        group_name = group_name_for_prefix(pref, notice_groups)
        if pref in pfet_prefixes:
            w_min, w_max, m_max, wl_max = pfet_profile(group_name)
        else:
            w_min, w_max, m_max, wl_max = nfet_profile(group_name)
        ranges.extend(
            [
                f"{pref}_L_range = [0.15, 5.0, 0.01]",
                f"{pref}_W_range = [{w_min}, {w_max}, 0.1]",
                f"{pref}_M_range = [1, {m_max}, 1]",
                f"{pref}_WL_ratio_range = [{round(w_min/0.15, 1)}, {wl_max}, 0.1]",
                "",
            ]
        )
        params.extend(
            [
                f"{pref}_L = 0.15",
                f"{pref}_WL_ratio = {round(w_min/0.15, 1)}",
                f"{pref}_M = 1",
                "",
            ]
        )

    cap_ranges = [f"{cap}_range = [1e-15, 1e-12, 1e-15]" for cap in cap_values]
    cap_params = [f"{cap} = 1e-12" for cap in cap_values]

    res_ranges = [
        f"{res}_range = [1e3, 1e6, 1e3]" for res in resistor_values
    ]
    res_params = [f"{res} = 1e4" for res in resistor_values]

    pairs = format_mosfet_pairs(notice_groups)

    op_region_lines: List[str] = []
    for inst in mos_instances:
        if is_pfet(inst.model):
            op_region_lines.append(f'{inst.name} = "pfet_01v8"')
        else:
            op_region_lines.append(f'{inst.name} = "nfet_01v8"')

    return "\n".join(
        [
            "[tech]",
            'name = "skywater"',
            "",
            "[type]",
            'name = "opamp"',
            "",
            "[opamp]",
            f'name = "{opamp_name}"',
            "",
            "[tech_lib]",
            'pdk_path = "PDK/sky130_pdk"',
            'corner = "tt"',
            "",
            "[testbench.dc]",
            "measure_DC = true",
            "supply_voltage = 1.8",
            "VCM_ratio = 0.4",
            "",
            "[testbench.ac]",
            "measure_AC = true",
            "ac_freq = 100",
            "ac_amp = 500",
            "PARAM_CLOAD = 10.00",
            "",
            "[testbench.ibias]",
            "use_ibias = true",
            "multi_ibias = false",
            "ibias = 3e-5",
            "",
            "[testbench.data]",
            'data_DC = "DC"',
            'data_AC = "AC"',
            'data_GBW_PM = "GBW_PM"',
            "",
            "[circuit.params_file]",
            "use_params_file = true",
            "generate_params_file = true",
            "API_mode = false",
            "generate_num_params = 10",
            "",
            "[circuit.params_format]",
            "use_width_to_length_ratio = true",
            'ration_field_suffix = "WL_ratio"',
            "",
            "[circuit.params_range]",
            *ranges,
            *cap_ranges,
            *res_ranges,
            "",
            "ibias_range = [1e-6, 1e-4, 1e-6]",
            "",
            "[circuit.params]",
            *params,
            *cap_params,
            *res_params,
            "",
            "[circuit.mosfet_pairs]",
            *pairs,
            "",
            "[circuit.op_region]",
            "extract_op_region = true",
            'device_prefix = "msky130_fd_pr__"',
            "op_variable_list_mos = [",
            '    "gm", "gds", "gmbs",',
            '    "vgs", "vds", "vbs", "vth", "vdsat", "id",',
            '    "cgs", "cgd", "cdb", "csb",',
            "]",
            "",
            "[circuit.op_region.transistor_dict]",
            *op_region_lines,
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate opamp TOML from netlist.j2 and notice.txt."
    )
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--notice", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--opamp-name", required=True)
    args = parser.parse_args()

    mos_instances, cap_values, resistor_values = collect_instances(args.netlist)
    prefixes = sorted({inst.prefix for inst in mos_instances if inst.prefix})
    notice_groups = parse_notice(args.notice)

    toml_text = render_toml(
        args.opamp_name,
        prefixes,
        mos_instances,
        notice_groups,
        cap_values,
        resistor_values,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(toml_text)


if __name__ == "__main__":
    main()
