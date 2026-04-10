#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


MOS_LINE_RE = re.compile(r"^[xX]?[mM]\d+\b")
CAP_LINE_RE = re.compile(r"^[cC]\d+\b")
RESISTOR_LINE_RE = re.compile(r"^[rR]\d+\b")
ID_IN_MOSFET_RE = re.compile(r"MOSFET_(\d+)_")


@dataclass
class MosLine:
    raw: str
    name: str
    w_value: str
    gate: str
    tokens: List[str]


def normalize_inst_name(name: str) -> str:
    match = re.match(r"^[xX]?[mM](\d+)$", name)
    if match:
        return f"m{match.group(1)}"
    return name.lower()


def strip_quotes(val: str) -> str:
    if len(val) >= 2 and ((val[0] == val[-1]) and val[0] in {"'", '"'}):
        return val[1:-1]
    return val


def parse_param_token(token: str) -> Tuple[str, str]:
    # token like l='...' or w="..." or m=...
    key, value = token.split("=", 1)
    return key, strip_quotes(value)


def find_numeric_factors(expr: str) -> List[float]:
    factors = []
    for part in expr.split("*"):
        part = part.strip()
        if not part:
            continue
        try:
            factors.append(float(part))
        except ValueError:
            continue
    return factors


def format_multiplier(mult: float) -> str:
    if abs(mult - round(mult)) < 1e-9:
        return str(int(round(mult)))
    return str(mult)


def collect_mos_lines(lines: Iterable[str]) -> List[MosLine]:
    mos_lines: List[MosLine] = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith(("*", ";", "//", ".")):
            continue
        if not MOS_LINE_RE.match(s):
            continue
        tokens = s.split()
        name = normalize_inst_name(tokens[0])
        gate = tokens[2].lower() if len(tokens) > 2 else ""
        w_token = next((t for t in tokens if t.startswith("w=")), None)
        if not w_token:
            continue
        _, w_value = parse_param_token(w_token)
        mos_lines.append(
            MosLine(raw=raw, name=name, w_value=w_value, gate=gate, tokens=tokens)
        )
    return mos_lines


def build_group_prefix(mos_lines: List[MosLine]) -> Dict[str, int]:
    # group by exact w value; choose the minimum MOSFET_<id> as prefix
    group_min_id: Dict[str, int] = {}
    for line in mos_lines:
        match = ID_IN_MOSFET_RE.search(line.w_value)
        if not match:
            continue
        mos_id = int(match.group(1))
        current = group_min_id.get(line.w_value)
        if current is None or mos_id < current:
            group_min_id[line.w_value] = mos_id
    return group_min_id


def rewrite_mos_line(line: MosLine, group_prefix: Dict[str, int]) -> str:
    w_value = line.w_value
    if w_value not in group_prefix:
        return line.raw
    prefix = f"M{group_prefix[w_value]}"

    new_tokens = []
    for token in line.tokens:
        if token.startswith("l="):
            new_tokens.append(f"l={{{{{prefix}_L}}}}")
        elif token.startswith("w="):
            new_tokens.append(f"w={{{{{prefix}_W}}}}")
        elif token.startswith("m="):
            _, m_value = parse_param_token(token)
            factors = find_numeric_factors(m_value)
            mult = 1.0
            for f in factors:
                mult *= f
            if abs(mult - 1.0) < 1e-9:
                new_tokens.append(f"m={{{{{prefix}_M}}}}")
            else:
                new_tokens.append(f"m={{{{{prefix}_M*{format_multiplier(mult)}}}}}")
        else:
            new_tokens.append(token)
    return " ".join(new_tokens)


def rewrite_cap_line(line: str) -> str:
    tokens = line.split()
    if not tokens:
        return line
    name = tokens[0]
    match = re.match(r"^[cC](\d+)$", name)
    if match:
        cap_id = int(match.group(1))
        tokens[0] = f"C_C{cap_id}"
    # replace CAPACITOR_<n> with {{C<n>_value}}
    tokens = [
        (
            f"{{{{C{int(cap_match.group(1))}_value}}}}"
            if (cap_match := re.match(r"^CAPACITOR_(\d+)$", strip_quotes(t)))
            else t
        )
        for t in tokens
    ]
    return " ".join(tokens)


def rewrite_resistor_line(line: str) -> str:
    tokens = line.split()
    if not tokens:
        return line
    name = tokens[0]
    match = re.match(r"^[rR](\d+)$", name)
    if match:
        res_id = int(match.group(1))
        tokens[0] = f"R_R{res_id}"
    # replace RESISTOR_<n> with {{R<n>_value}}
    tokens = [
        (
            f"{{{{R{int(res_match.group(1))}_value}}}}"
            if (res_match := re.match(r"^RESISTOR_(\d+)$", strip_quotes(t)))
            else t
        )
        for t in tokens
    ]
    return " ".join(tokens)


def rewrite_lines(lines: List[str]) -> Tuple[List[str], Dict[str, List[MosLine]]]:
    mos_lines = collect_mos_lines(lines)
    group_prefix = build_group_prefix(mos_lines)

    # build notice groups: map w -> list of mos lines
    notice_groups: Dict[str, List[MosLine]] = {}
    for line in mos_lines:
        notice_groups.setdefault(line.w_value, []).append(line)

    rewritten: List[str] = []
    for raw in lines:
        s = raw.strip()
        if s.startswith(".subckt"):
            tokens = s.split()
            if "Ib" not in tokens:
                tokens.append("Ib")
            rewritten.append(" ".join(tokens))
            continue

        if MOS_LINE_RE.match(s):
            mos_line = next((ml for ml in mos_lines if ml.raw == raw), None)
            rewritten.append(
                rewrite_mos_line(mos_line, group_prefix) if mos_line else raw
            )
            continue

        if CAP_LINE_RE.match(s):
            rewritten.append(rewrite_cap_line(s))
            continue

        if RESISTOR_LINE_RE.match(s):
            rewritten.append(rewrite_resistor_line(s))
            continue

        if s.startswith("I0") and "CURRENT_0_BIAS" in s:
            rewritten.append(
                s.replace("'CURRENT_0_BIAS'", "Ib").replace("CURRENT_0_BIAS", "Ib")
            )
            continue

        rewritten.append(raw.rstrip())

    return rewritten, notice_groups


def normalize_w_label(w_value: str) -> str:
    label = w_value.replace("*1", "")
    if "{{" in label and "}}" in label:
        label = label.replace("{{", "").replace("}}", "").strip()
    return label


def group_name_for_w(w_value: str, mos_group: List[MosLine]) -> str:
    if any(mos.gate in {"vinn", "vinp"} for mos in mos_group):
        return "differential pair"

    label = normalize_w_label(w_value)
    mosfet_id = None
    mosfet_match = re.search(r"MOSFET_(\d+(?:_\d+)?)_", label)
    if mosfet_match:
        mosfet_id = mosfet_match.group(1)
    if "W_" in label:
        label = label.split("W_", 1)[1]
    elif label.endswith("_W") and label[0] in {"M", "m"}:
        label = label[:-2]
    base_name = label.lower().replace("_", " ")
    if mosfet_id:
        return f"{base_name} {mosfet_id}"
    return base_name


def format_notice(notice_groups: Dict[str, List[MosLine]]) -> str:
    lines: List[str] = []
    for w_value, mos_group in sorted(notice_groups.items(), key=lambda kv: kv[0]):
        # sort instance names by numeric suffix if present
        def sort_key(n: str) -> Tuple[int, str]:
            m = re.search(r"(\d+)$", n)
            return (int(m.group(1)) if m else 0, n)

        group_name = group_name_for_w(w_value, mos_group)
        sorted_names = sorted((mos.name for mos in mos_group), key=sort_key)
        joined = ", ".join(sorted_names)
        lines.append(f"{group_name}: {joined}")
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert opamp netlist.j2 by W-grouping."
    )
    parser.add_argument("--netlist-in", required=True, type=Path)
    parser.add_argument("--netlist-out", required=True, type=Path)
    parser.add_argument("--notice-out", required=True, type=Path)
    args = parser.parse_args()

    lines = args.netlist_in.read_text().splitlines()
    rewritten, notice_groups = rewrite_lines(lines)

    args.netlist_out.parent.mkdir(parents=True, exist_ok=True)
    args.netlist_out.write_text("\n".join(rewritten) + "\n")

    args.notice_out.parent.mkdir(parents=True, exist_ok=True)
    args.notice_out.write_text(format_notice(notice_groups))


if __name__ == "__main__":
    main()
