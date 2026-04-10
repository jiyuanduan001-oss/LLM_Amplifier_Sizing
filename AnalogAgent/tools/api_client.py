"""
API client for CircuitCollector's local FastAPI simulation server.

CircuitCollector schema:
  POST /simulate/
    Request:  {params, base_config_path, output_dir, spec_list}
    Response: {specs, op_region, logs}

  GET /health → {"status": "ok"}
"""

import requests
from typing import Optional

BASE_URL = "http://localhost:8001"
DEFAULT_TIMEOUT = 120  # seconds — ngspice simulations can take 10-60s

# Comprehensive default spec list — ensures all measurement results are
# returned regardless of how the caller invokes simulate().  This is
# critical for parallel optimization where each call uses a unique
# output_dir: without an explicit spec_list the server may only return
# a subset of specs.
DEFAULT_SPEC_LIST = [
    # AC
    "dcgain_", "gain_bandwidth_product_", "phase_margin",
    "cmrr", "dcpsrp", "dcpsrn",
    # DC
    "power", "vos25", "tc",
    # Noise
    "input_noise_density_1Hz", "input_noise_density_spot",
    "output_noise_density_1Hz", "output_noise_density_spot",
    "integrated_input_noise", "integrated_output_noise",
    # Slew rate
    "slew_rate_pos", "slew_rate_neg",
    # Output swing
    "vout_low", "vout_high", "output_swing",
    # Gain-plateau detection
    "gain_peaking_db",
    "true_gbw",
]


def simulate(
    params: dict,
    base_config_path: str,
    spec_list: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """
    Call CircuitCollector POST /simulate/.

    Args:
        params:           Dict of sizing parameters, e.g. {"M1_L": 0.18, "M1_WL_ratio": 3.7}
        base_config_path: Relative path to TOML config inside CircuitCollector project,
                          e.g. "config/skywater/opamp/tsm.toml"
        spec_list:        Specs to extract; defaults to DEFAULT_SPEC_LIST which
                          covers all AC, DC, noise, slew, swing, and peaking specs.
        output_dir:       Optional output directory override
        timeout:          Request timeout in seconds (default 120)

    Returns:
        {
          "specs":     {spec_name: float, ...},
          "op_region": {
              "m1": {"gm": ..., "Id": ..., "gm/Id": "...", "vds": ...,
                     "vdsat": ..., "sat_margin": ..., "vgs": ..., "vov": ...},
              ...
          },
          "logs": str | None,
          "raw":  {raw_key: float, ...}   # added by bridge if needed
        }

    Raises:
        requests.HTTPError on non-2xx response.
        requests.Timeout if server does not respond within timeout.
    """
    payload: dict = {"params": params, "base_config_path": base_config_path}
    payload["spec_list"] = spec_list if spec_list is not None else DEFAULT_SPEC_LIST
    if output_dir is not None:
        payload["output_dir"] = output_dir

    resp = requests.post(f"{BASE_URL}/simulate/", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def register_circuit(
    raw_netlist: str,
    topology_name: str,
    circuit_type: str = "opamp",
    timeout: int = 30,
) -> dict:
    """
    Register a new circuit topology with CircuitCollector.

    Sends the raw netlist to CircuitCollector's /register_circuit/ endpoint,
    which converts it to a Jinja2 template (netlist.j2), generates the TOML
    config, and writes both to the standard directory layout.

    Args:
        raw_netlist:    Full .subckt text (Jinja2-parameterized or MOSFET_<n> format)
        topology_name:  Filesystem-safe identifier (e.g. 'tco', 'fc_ota')
        circuit_type:   Circuit category (default: 'opamp')
        timeout:        Request timeout in seconds

    Returns:
        {"status": "created"|"already_exists", "config_path": "...", "netlist_j2_path": "...", "message": ...}

    Raises:
        requests.HTTPError on non-2xx response.
    """
    payload = {
        "raw_netlist": raw_netlist,
        "topology_name": topology_name,
        "circuit_type": circuit_type,
    }
    resp = requests.post(
        f"{BASE_URL}/register_circuit/", json=payload, timeout=timeout
    )
    resp.raise_for_status()
    return resp.json()


def check_server() -> bool:
    """Return True if CircuitCollector server is reachable and healthy."""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
