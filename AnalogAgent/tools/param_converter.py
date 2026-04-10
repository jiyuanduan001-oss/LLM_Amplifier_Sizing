"""
Topology-aware parameter converter.

Translates per-role gm/Id sizing targets into CircuitCollector parameter dicts.
Each supported topology has its own bridge module with the mapping logic.
This module dispatches to the correct bridge based on topology name.

To add a new topology:
  1. Create tools/bridge_<name>.py with sizing_result_to_params() and ROLE_DEVICE_MAP
  2. Register it in TOPOLOGY_REGISTRY below
"""

from typing import Optional

from tools.bridge import RoleTarget


# ---------------------------------------------------------------------------
# Topology registry
# ---------------------------------------------------------------------------

# Each entry: topology_name -> {
#   "bridge_module":  module path for lazy import
#   "config_path":    default CircuitCollector TOML config
#   "requires_Cc":    whether Cc_f is a required parameter
#   "roles":          list of expected role names (for documentation)
# }

TOPOLOGY_REGISTRY: dict[str, dict] = {
    "5t_ota": {
        "bridge_module": "tools.bridge",
        "config_path":   "config/skywater/opamp/5tota.toml",
        "requires_Cc":   False,
        "roles":         ["DIFF_PAIR", "LOAD", "TAIL", "BIAS_REF"],
    },
    "twostage": {
        "bridge_module": "tools.bridge_twostage",
        "config_path":   "config/skywater/opamp/tsm.toml",
        "requires_Cc":   True,
        "roles":         ["DIFF_PAIR", "LOAD", "BIAS_GEN", "TAIL", "OUTPUT_CS", "OUTPUT_BIAS"],
    },
}


def list_topologies() -> list[dict]:
    """Return info about all registered topologies."""
    return [
        {"name": name, "roles": info["roles"], "config_path": info["config_path"]}
        for name, info in TOPOLOGY_REGISTRY.items()
    ]


def convert_sizing(
    topology: str,
    roles_raw: dict[str, dict],
    Ib_a: float,
    Cc_f: Optional[float] = None,
    Rc_ohm: Optional[float] = None,
    l_overrides: Optional[dict[str, float]] = None,
) -> dict:
    """
    Convert per-role sizing targets into a CircuitCollector params dict.

    Args:
        topology:    Registered topology name (e.g. '5t_ota', 'twostage').
        roles_raw:   Dict of role_name -> {gm_id_target, L_guidance_um, id_derived}.
        Ib_a:        Bias current in Amperes.
        Cc_f:        Compensation capacitor in Farads (required for some topologies).
        Rc_ohm:      Nulling resistor in Ohms (twostage only; = 1/gm7).
        l_overrides: Optional per-role L (µm) overrides.

    Returns:
        {"status": "ok", "params": {...}, "config_path": "..."}
        or {"status": "error", "message": "..."}
    """
    if topology not in TOPOLOGY_REGISTRY:
        available = list(TOPOLOGY_REGISTRY.keys())
        return {
            "status": "error",
            "message": f"Unknown topology: '{topology}'. Available: {available}",
        }

    info = TOPOLOGY_REGISTRY[topology]

    # Check Cc requirement
    if info["requires_Cc"] and Cc_f is None:
        return {
            "status": "error",
            "message": f"Cc_f is required for topology '{topology}'.",
        }

    # Build RoleTarget objects
    role_targets = {}
    for role_name, vals in roles_raw.items():
        role_targets[role_name] = RoleTarget(
            role=role_name,
            gm_id_target=vals.get("gm_id_target"),
            L_guidance_um=vals.get("L_guidance_um"),
            id_derived=vals.get("id_derived"),
            inversion_region=vals.get("inversion_region"),
        )

    # Dispatch to the correct bridge
    try:
        if topology == "5t_ota":
            from tools.bridge import SizingResult, sizing_result_to_params
            sizing = SizingResult(roles=role_targets)
            params = sizing_result_to_params(sizing, l_overrides=l_overrides)
            params["ibias"] = Ib_a

        elif topology == "twostage":
            from tools.bridge_twostage import sizing_result_to_params as ts_convert
            params = ts_convert(role_targets, Cc_f=Cc_f, Ib_a=Ib_a, Rc_ohm=Rc_ohm, l_overrides=l_overrides)

        elif info.get("bridge_module") == "tools.bridge_generic":
            from tools.bridge_generic import sizing_result_to_params as generic_convert
            params = generic_convert(
                role_targets,
                role_device_map=info["role_device_map"],
                Ib_a=Ib_a,
                Cc_f=Cc_f,
                Rc_ohm=Rc_ohm,
                passive_params=info.get("passive_params"),
                l_overrides=l_overrides,
            )

        else:
            return {"status": "error", "message": f"No converter implemented for '{topology}'."}

        return {
            "status": "ok",
            "params": params,
            "config_path": info["config_path"],
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
