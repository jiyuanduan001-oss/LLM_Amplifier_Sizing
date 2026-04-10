"""
Generic topology-independent bridge for AnalogAgent <-> CircuitCollector.

Replaces per-topology bridge files for dynamically registered topologies.
The role-to-device mapping is provided at call time, not hardcoded.

Core function: sizing_result_to_params(roles, role_device_map, ...)
  - Converts RoleTarget objects to flat CircuitCollector params
  - Handles mirror groups (shared per-finger W/L, scaled M)
  - Handles passives (Cc, Rc, etc.)
"""

from __future__ import annotations

import dataclasses
import math
from typing import Optional

from scripts.lut_lookup import lut_query
from tools.bridge import RoleTarget, TransistorOP, parse_response, parse_specs
from tools.api_client import simulate, DEFAULT_SPEC_LIST


# WL_ratio constraints (same as CircuitCollector conventions)
_WL_RATIO_RANGE = {
    "pfet": (3.7, 10.0),
    "nfet": (2.8, 10.0),
}


def _role_to_params(
    prefix: str,
    device_type: str,
    target: RoleTarget,
) -> dict:
    """
    Convert one role's RoleTarget to CircuitCollector params for a single device.

    Args:
        prefix:      Device prefix, e.g. "M3"
        device_type: "nfet" or "pfet"
        target:      RoleTarget with sizing targets

    Returns:
        e.g. {"M3_L": 0.5, "M3_WL_ratio": 5.0, "M3_M": 1}
    """
    L_um = target.L_guidance_um
    gm_id = target.gm_id_target
    id_a = target.id_derived

    if L_um is None or id_a is None:
        return {}

    wl_min, wl_max = _WL_RATIO_RANGE[device_type]

    # No gm/ID target (e.g. mirror — just use minimum ratio)
    if gm_id is None or gm_id == 0:
        return {
            f"{prefix}_L":        round(L_um, 3),
            f"{prefix}_WL_ratio": wl_min,
            f"{prefix}_M":        1,
        }

    # Compute W from LUT
    try:
        id_w_ua_um = lut_query(device_type, "id_w", L_um, gm_id_val=gm_id)
        W_um = id_a * 1e6 / id_w_ua_um
        WL_ratio = W_um / L_um
    except (FileNotFoundError, ValueError):
        W_um = max(0.42, id_a * 1e6 / 50.0)
        WL_ratio = W_um / L_um

    # Keep WL_ratio in range using M (finger multiplier)
    M = max(1, math.ceil(WL_ratio / wl_max))
    WL_per_finger = WL_ratio / M
    WL_per_finger = max(wl_min, WL_per_finger)

    return {
        f"{prefix}_L":        round(L_um, 3),
        f"{prefix}_WL_ratio": round(WL_per_finger, 2),
        f"{prefix}_M":        M,
    }


def _detect_mirror_groups(role_device_map: dict[str, dict]) -> list[list[str]]:
    """
    Detect groups of roles that share the same per-finger W/L (current mirrors).

    Mirror groups are roles whose primary devices share L and WL_ratio.
    Convention: roles with `"mirror_of": "<role>"` in the map form a group.
    If no explicit mirror_of, each role is independent.

    Returns:
        List of groups, each a list of role names. The first role is the reference.
    """
    # Build adjacency from mirror_of
    ref_to_group: dict[str, list[str]] = {}
    independent: list[str] = []

    for role, info in role_device_map.items():
        mirror_of = info.get("mirror_of")
        if mirror_of:
            ref_to_group.setdefault(mirror_of, [mirror_of]).append(role)
        elif role not in ref_to_group:
            # Could be a reference for others, or fully independent
            independent.append(role)

    groups = list(ref_to_group.values())
    # Add independent roles as single-element groups
    for role in independent:
        if not any(role in g for g in groups):
            groups.append([role])

    return groups


def sizing_result_to_params(
    roles: dict[str, RoleTarget],
    role_device_map: dict[str, dict],
    Ib_a: float,
    Cc_f: Optional[float] = None,
    Rc_ohm: Optional[float] = None,
    passive_params: Optional[list[str]] = None,
    l_overrides: Optional[dict[str, float]] = None,
) -> dict:
    """
    Convert a dict of RoleTargets to a flat CircuitCollector params dict.

    Generic version — works with any topology given a role_device_map.

    Args:
        roles:            Dict of role name -> RoleTarget
        role_device_map:  Dict of role name -> {"primary": "M3", "device_type": "nfet",
                          "mirrors": ["M4"], "mirror_of": "BIAS_GEN" (optional)}
        Ib_a:             Bias current in Amperes
        Cc_f:             Compensation capacitor in Farads (optional)
        Rc_ohm:           Nulling resistor in Ohms (optional)
        passive_params:   List of passive param names from netlist (e.g. ["C1_value", "Rc_value"])
        l_overrides:      Optional {role: L_um} overrides

    Returns:
        Flat params dict for CircuitCollector
    """
    params = {}

    # Detect mirror groups
    mirror_groups = _detect_mirror_groups(role_device_map)

    for group in mirror_groups:
        if len(group) == 1:
            # Independent role — size directly
            role = group[0]
            if role not in roles:
                continue
            target = roles[role]
            if l_overrides and role in l_overrides:
                target = dataclasses.replace(target, L_guidance_um=l_overrides[role])
            mapping = role_device_map[role]
            params.update(_role_to_params(
                mapping["primary"], mapping["device_type"], target
            ))
        else:
            # Mirror group: first role is reference, others scale M
            ref_role = group[0]
            ref_target = roles.get(ref_role)
            if not ref_target or not ref_target.id_derived:
                continue

            ref_mapping = role_device_map[ref_role]
            L_um = ref_target.L_guidance_um or 1.0
            if l_overrides:
                L_um = l_overrides.get(ref_role, L_um)

            device_type = ref_mapping["device_type"]
            wl_min, wl_max = _WL_RATIO_RANGE[device_type]

            # Size the reference device
            gm_id_ref = ref_target.gm_id_target or 12.0
            id_ref = ref_target.id_derived

            try:
                id_w = lut_query(device_type, "id_w", L_um, gm_id_val=gm_id_ref)
                W_unit = id_ref * 1e6 / id_w
                WL_unit = W_unit / L_um
            except (FileNotFoundError, ValueError):
                WL_unit = wl_min

            M_ref = max(1, math.ceil(WL_unit / wl_max))
            WL_per_finger = max(wl_min, WL_unit / M_ref)

            # Set reference device params
            ref_prefix = ref_mapping["primary"]
            params.update({
                f"{ref_prefix}_L":        round(L_um, 3),
                f"{ref_prefix}_WL_ratio": round(WL_per_finger, 2),
                f"{ref_prefix}_M":        M_ref,
            })

            # Set mirror devices — share W/L, scale M by current ratio
            for mirror_role in group[1:]:
                mirror_target = roles.get(mirror_role)
                if not mirror_target or not mirror_target.id_derived:
                    continue
                mirror_mapping = role_device_map[mirror_role]
                mirror_prefix = mirror_mapping["primary"]

                L_mirror = L_um
                if l_overrides and mirror_role in l_overrides:
                    L_mirror = l_overrides[mirror_role]

                mirror_ratio = mirror_target.id_derived / id_ref
                M_mirror = max(1, round(mirror_ratio * M_ref))

                params.update({
                    f"{mirror_prefix}_L":        round(L_mirror, 3),
                    f"{mirror_prefix}_WL_ratio": round(WL_per_finger, 2),
                    f"{mirror_prefix}_M":        M_mirror,
                })

    # Passives
    if Cc_f is not None:
        params["C1_value"] = Cc_f
    if Rc_ohm is not None:
        params["Rc_value"] = Rc_ohm
    params["ibias"] = Ib_a

    return params


def simulate_circuit(
    params: dict,
    config_path: str,
    spec_list: Optional[list[str]] = None,
    corner: Optional[str] = None,
    temperature: Optional[float] = None,
    supply_voltage: Optional[float] = None,
    CL: Optional[float] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Send params to CircuitCollector and parse the response.

    Generic version — works with any topology given the config_path.
    """
    merged = dict(params)
    if corner is not None:
        merged["__corner__"] = corner
    if temperature is not None:
        merged["__temperature__"] = temperature
    if supply_voltage is not None:
        merged["__supply_voltage__"] = supply_voltage
    if CL is not None:
        merged["__CL__"] = CL

    raw = simulate(
        params=merged,
        base_config_path=config_path,
        spec_list=spec_list or DEFAULT_SPEC_LIST,
        output_dir=output_dir,
    )
    return parse_response(raw)
