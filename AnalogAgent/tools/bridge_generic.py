"""
Generic topology-independent bridge for AnalogAgent <-> CircuitCollector.

Replaces per-topology bridge files for dynamically registered topologies.
The role-to-device mapping is provided at call time, not hardcoded.

Core function: sizing_result_to_params(roles, role_device_map, ...)
  - Converts RoleTarget objects to flat CircuitCollector params
  - Handles mirror groups (shared per-instance W/L, scaled M)
  - Handles passives (Cc, Rc, etc.)
"""

from __future__ import annotations

import dataclasses
import math
import warnings
from typing import Optional

from scripts.lut_lookup import lut_query
from tools.bridge import RoleTarget, TransistorOP, parse_response, parse_specs
from tools.api_client import simulate, check_server, DEFAULT_SPEC_LIST


# WL_ratio upper bound — split wide devices into multiple instances (increase M).
# No lower bound on WL_ratio; PDK minimum width enforced separately.
_WL_MAX = 10.0

# Maximum width per instance (µm).  When the computed W exceeds this,
# M is increased so that each instance stays within the limit.
# This matters for long-channel devices where WL_ratio is modest but
# W = WL_ratio × L is large.
_W_PER_INST_MAX_UM = 5.0

# SKY130 PDK minimum device widths (µm).
_W_MIN_UM = {
    "pfet": 0.42,
    "nfet": 0.42,
}


def _role_to_params(
    prefix: str,
    device_type: str,
    target: RoleTarget,
    corner: str = "tt",
    temp: str = "25C",
) -> dict:
    """
    Convert one role's RoleTarget to CircuitCollector params for a single device.

    Args:
        prefix:      Device prefix, e.g. "M3"
        device_type: "nfet" or "pfet"
        target:      RoleTarget with sizing targets
        corner:      Process corner for the LUT query (default "tt")
        temp:        Temperature string for the LUT query, e.g. "27C"
                     (default "25C"). Must match the temperature at which
                     the circuit will be simulated — otherwise the LUT-
                     derived W bakes in temperature coefficients that do
                     not match the SPICE run and the OP point lands in
                     the wrong inversion region.

    Returns:
        e.g. {"M3_L": 0.5, "M3_WL_ratio": 5.0, "M3_M": 1}
    """
    L_um = target.L_guidance_um
    gm_id = target.gm_id_target
    id_a = target.id_derived

    if L_um is None or id_a is None:
        return {}

    w_min = _W_MIN_UM[device_type]
    wl_max = _WL_MAX

    # No gm/ID target (e.g. diode-connected bias device sized by mirror group).
    # Use PDK minimum width so the device is physically valid.
    if gm_id is None or gm_id == 0:
        return {
            f"{prefix}_L":        round(L_um, 3),
            f"{prefix}_WL_ratio": round(w_min / L_um, 4),
            f"{prefix}_M":        1,
        }

    # Compute W from LUT at the user-specified corner/temp.
    try:
        id_w_ua_um = lut_query(
            device_type, "id_w", L_um,
            corner=corner, temp=temp, gm_id_val=gm_id,
        )
        W_um = id_a * 1e6 / id_w_ua_um
    except (FileNotFoundError, ValueError):
        W_um = id_a * 1e6 / 50.0

    # Enforce PDK minimum width
    W_um = max(w_min, W_um)
    WL_ratio = W_um / L_um

    # Split into multiple instances if WL_ratio or W per instance exceeds bounds
    M_wl = max(1, math.ceil(WL_ratio / wl_max))
    W_per_inst = L_um * WL_ratio / M_wl
    M_w = max(1, math.ceil(W_per_inst / _W_PER_INST_MAX_UM))
    M = max(M_wl, M_w)
    WL_per_inst = WL_ratio / M

    return {
        f"{prefix}_L":        round(L_um, 3),
        f"{prefix}_WL_ratio": round(WL_per_inst, 2),
        f"{prefix}_M":        M,
    }


def _detect_mirror_groups(role_device_map: dict[str, dict]) -> list[list[str]]:
    """
    Detect groups of roles that share the same per-instance W/L (current mirrors).

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
    corner: str = "tt",
    temp: str = "25C",
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
        corner:           Process corner for LUT queries (default "tt").
        temp:             Temperature string for LUT queries, e.g. "27C"
                          (default "25C"). Should match the temperature
                          at which the circuit will be simulated, so that
                          the LUT-derived W and the SPICE OP point agree.

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
                mapping["primary"], mapping["device_type"], target,
                corner=corner, temp=temp,
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
            w_min = _W_MIN_UM[device_type]
            wl_max = _WL_MAX

            # Size the reference device
            gm_id_ref = ref_target.gm_id_target or 12.0
            id_ref = ref_target.id_derived

            try:
                id_w = lut_query(
                    device_type, "id_w", L_um,
                    corner=corner, temp=temp, gm_id_val=gm_id_ref,
                )
                W_unit = max(w_min, id_ref * 1e6 / id_w)
                WL_unit = W_unit / L_um
            except (FileNotFoundError, ValueError):
                WL_unit = w_min / L_um

            M_ref_wl = max(1, math.ceil(WL_unit / wl_max))
            W_per_inst = L_um * WL_unit / M_ref_wl
            M_ref_w = max(1, math.ceil(W_per_inst / _W_PER_INST_MAX_UM))
            M_ref = max(M_ref_wl, M_ref_w)
            WL_per_inst = WL_unit / M_ref

            # Set reference device params
            ref_prefix = ref_mapping["primary"]
            params.update({
                f"{ref_prefix}_L":        round(L_um, 3),
                f"{ref_prefix}_WL_ratio": round(WL_per_inst, 2),
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

                # Sanity check: if mirror ratio ≈ 1.0, the caller may have
                # passed per-instance current instead of the total current the
                # mirror role should carry.  E.g. TAIL mirrors BIAS_GEN and
                # should carry M× more current; passing I_bias for both gives
                # ratio = 1 and M_mirror = M_ref = 1 (wrong).
                if (
                    abs(mirror_ratio - 1.0) < 0.15
                    and M_mirror == M_ref
                    and M_ref <= 2
                ):
                    warnings.warn(
                        f"Mirror ratio for '{mirror_role}' (mirrors '{ref_role}') "
                        f"is ~1.0 (id_derived={mirror_target.id_derived:.2e} vs "
                        f"ref={id_ref:.2e}) → M_{mirror_prefix} = {M_mirror}. "
                        f"If '{mirror_role}' should carry more current than "
                        f"'{ref_role}', ensure id_derived is the TOTAL current "
                        f"for the role, not the per-instance current.",
                        stacklevel=3,
                    )

                params.update({
                    f"{mirror_prefix}_L":        round(L_mirror, 3),
                    f"{mirror_prefix}_WL_ratio": round(WL_per_inst, 2),
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
    extra_ports: Optional[dict] = None,
    measure_mismatch: Optional[bool] = None,
    save_waveforms: Optional[bool] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Send params to CircuitCollector and parse the response.

    Generic version — works with any topology given the config_path.

    Args:
        extra_ports: Optional {port_name: DC voltage} dict. Overrides the
            [testbench.extra_ports] values baked into the TOML at
            registration time. Use this to update LV-cascode bias
            voltages (Vbias_cas_p / Vbias_cas_n) per-simulation as the
            sizing changes their underlying vdsat/vth values, without
            re-registering the topology.
    """
    if not check_server():
        raise RuntimeError("CircuitCollector not reachable at http://localhost:8001")

    merged = dict(params)
    if corner is not None:
        merged["corner"] = corner
    if temperature is not None:
        merged["temperature"] = temperature
    if supply_voltage is not None:
        merged["supply_voltage"] = supply_voltage
    if CL is not None:
        # CircuitCollector expects PARAM_CLOAD in picoFarads (the SPICE
        # template appends a "p" suffix).  The public API of this function
        # accepts CL in Farads (SI), so convert here.
        merged["CL"] = CL * 1e12  # F → pF
    if extra_ports is not None:
        if not isinstance(extra_ports, dict):
            raise TypeError(
                f"extra_ports must be dict of {{port: voltage}}, "
                f"got {type(extra_ports).__name__}"
            )
        merged["extra_ports"] = dict(extra_ports)
    if measure_mismatch is not None:
        merged["measure_mismatch"] = bool(measure_mismatch)
    if save_waveforms is not None:
        merged["save_waveforms"] = bool(save_waveforms)

    response = simulate(
        params=merged,
        base_config_path=config_path,
        spec_list=spec_list or DEFAULT_SPEC_LIST,
        output_dir=output_dir,
    )

    return {
        "specs": parse_specs(response),
        "transistors": parse_response(response),
        "raw_response": response,
    }
