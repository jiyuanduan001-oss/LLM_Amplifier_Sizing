"""
Dynamic topology registration and management.

Orchestrates the flow:
  1. Check if topology exists in TOPOLOGY_REGISTRY
  2. If not, call CircuitCollector /register_circuit/ to create netlist.j2 + TOML
  3. Register the topology in TOPOLOGY_REGISTRY for the current session

Usage from the LLM:
    from tools.topology_manager import ensure_topology_registered

    result = ensure_topology_registered(
        topology_name="tco",
        raw_netlist="...",
        role_device_map={...},
    )
    # result["config_path"] can now be used with convert_sizing()
"""

from __future__ import annotations

from typing import Optional

from tools.api_client import register_circuit
from tools.param_converter import TOPOLOGY_REGISTRY


def ensure_topology_registered(
    topology_name: str,
    raw_netlist: str,
    role_device_map: dict[str, dict],
    roles: Optional[list[str]] = None,
    requires_Cc: bool = False,
    passive_params: Optional[list[str]] = None,
    circuit_type: str = "opamp",
) -> dict:
    """
    Ensure a topology is registered and ready for simulation.

    If the topology already exists in TOPOLOGY_REGISTRY, returns its config_path.
    Otherwise, registers it with CircuitCollector and adds it to the registry.

    Args:
        topology_name:   Filesystem-safe identifier (e.g. 'tco', 'fc_ota')
        raw_netlist:     Full .subckt text (Jinja2-parameterized)
        role_device_map: Dict of role -> {"primary": "M3", "device_type": "nfet",
                         "mirrors": ["M4"], "mirror_of": "BIAS_GEN" (optional)}
        roles:           List of role names (derived from role_device_map if None)
        requires_Cc:     Whether the topology needs a compensation capacitor
        passive_params:  List of passive param names (e.g. ["C1_value", "Rc_value"])
        circuit_type:    Circuit category (default: "opamp")

    Returns:
        {"status": "ok", "config_path": "config/skywater/opamp/<name>.toml",
         "registered": True/False}
    """
    # Already registered?
    if topology_name in TOPOLOGY_REGISTRY:
        info = TOPOLOGY_REGISTRY[topology_name]
        return {
            "status": "ok",
            "config_path": info["config_path"],
            "registered": False,
        }

    # Register with CircuitCollector (creates netlist.j2 + TOML)
    resp = register_circuit(
        raw_netlist=raw_netlist,
        topology_name=topology_name,
        circuit_type=circuit_type,
    )

    config_path = resp["config_path"]

    # Add to runtime registry
    if roles is None:
        roles = list(role_device_map.keys())

    TOPOLOGY_REGISTRY[topology_name] = {
        "bridge_module":  "tools.bridge_generic",
        "config_path":    config_path,
        "requires_Cc":    requires_Cc,
        "roles":          roles,
        "role_device_map": role_device_map,
        "passive_params": passive_params or [],
    }

    return {
        "status": "ok",
        "config_path": config_path,
        "registered": True,
    }
