"""
Mapping layer between AnalogAgent sizing decisions and CircuitCollector simulation
for two-stage Miller-compensated OTA (tsm).

Responsibilities:
  1. _role_to_params()           -- RoleTarget -> CircuitCollector params for one role
  2. sizing_result_to_params()   -- all roles -> flat CircuitCollector params dict
  3. simulate_circuit()          -- send params to CircuitCollector, parse response

All formulas, design flow, and OP analysis are handled by the LLM via skills.
This module only handles the topology-specific mapping and mirror logic.

Topology (tsm netlist):
  Stage 1: M3/M4 (nfet diff pair) + M1/M2 (pfet current mirror load)
  Stage 2: M7 (pfet common-source) + M8 (nfet current source)
  Bias:    M5 (nfet diode-connected) -> M6 (tail mirror) + M8 (stage2 mirror)
  Comp:    R_Rc + C_C1 Miller cap with nulling resistor between net5 and vout

Role -> Device mapping:
  DIFF_PAIR   -> M3 (primary), M4 (mirror via TOML mosfet_pairs)
  LOAD        -> M1 (primary), M2 (mirror via TOML mosfet_pairs)
  BIAS_GEN    -> M5 (diode-connected reference)
  TAIL        -> M6 (tail current source, mirrors M5)
  OUTPUT_CS   -> M7 (stage 2 CS amplifier, pfet)
  OUTPUT_BIAS -> M8 (stage 2 current source, mirrors M5)
"""

import dataclasses
import math
from typing import Optional

from scripts.lut_lookup import lut_query
from tools.api_client import simulate, check_server
from tools.bridge import TransistorOP, SizingInputs, RoleTarget, parse_response, parse_specs


# ---------------------------------------------------------------------------
# Two-stage role -> device mapping
# ---------------------------------------------------------------------------

ROLE_DEVICE_MAP: dict[str, dict] = {
    "DIFF_PAIR": {
        "primary":     "M3",
        "mirrors":     ["M4"],   # TOML mosfet_pairs: M3 = M4
        "device_type": "nfet",
    },
    "LOAD": {
        "primary":     "M1",
        "mirrors":     ["M2"],   # TOML mosfet_pairs: M1 = M2
        "device_type": "pfet",
    },
    "BIAS_GEN": {
        "primary":     "M5",
        "mirrors":     [],
        "device_type": "nfet",
    },
    "TAIL": {
        "primary":     "M6",
        "mirrors":     [],
        "device_type": "nfet",
    },
    "OUTPUT_CS": {
        "primary":     "M7",
        "mirrors":     [],
        "device_type": "pfet",
    },
    "OUTPUT_BIAS": {
        "primary":     "M8",
        "mirrors":     [],
        "device_type": "nfet",
    },
}

DEFAULT_CONFIG_PATH = "config/skywater/opamp/tsm.toml"
DEFAULT_OUTPUT_DIR  = "output/opamp/tsm"

DEFAULT_SPEC_LIST = [
    # AC
    "dcgain_",
    "gain_bandwidth_product_",
    "phase_margin",
    "cmrr",
    "dcpsrp",
    "dcpsrn",
    # Gain-plateau detection (effective vs measured GBW)
    "gain_peaking_db",
    "true_gbw",
    # DC
    "power",
    "vos25",
    "tc",
    # Noise
    "input_noise_density_1Hz",
    "input_noise_density_spot",
    "output_noise_density_1Hz",
    "output_noise_density_spot",
    "integrated_input_noise",
    "integrated_output_noise",
    # Slew rate
    "slew_rate_pos",
    "slew_rate_neg",
    # Output swing
    "vout_low",
    "vout_high",
    "output_swing",
]

# WL_ratio constraints from tsm.toml
_WL_RATIO_RANGE = {
    "pfet": (3.7, 10.0),
    "nfet": (2.8, 10.0),
}


# ---------------------------------------------------------------------------
# 1. gm/Id targets -> CircuitCollector params
# ---------------------------------------------------------------------------

def _role_to_params(role: str, target: RoleTarget) -> dict:
    """
    Convert one role's RoleTarget to CircuitCollector param dict.

    Uses LUT to compute W from (gm_id_target, L_guidance, id_derived).
    W/L ratio is what CircuitCollector expects.

    Args:
        role:   Role name, e.g. "DIFF_PAIR"
        target: RoleTarget with sizing targets

    Returns:
        Dict like {"M3_L": 0.5, "M3_WL_ratio": 5.0, "M3_M": 1}
    """
    mapping = ROLE_DEVICE_MAP[role]
    prefix = mapping["primary"]
    device = mapping["device_type"]

    L_um = target.L_guidance_um
    gm_id = target.gm_id_target
    id_a = target.id_derived

    if L_um is None or id_a is None:
        return {}

    wl_min, wl_max = _WL_RATIO_RANGE[device]

    # Diode-connected (BIAS_GEN): use minimum WL_ratio
    if gm_id is None or gm_id == 0:
        return {
            f"{prefix}_L":        round(L_um, 3),
            f"{prefix}_WL_ratio": wl_min,
            f"{prefix}_M":        1,
        }

    # Compute W from LUT
    try:
        id_w_ua_um = lut_query(device, "id_w", L_um, gm_id_val=gm_id)
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


def sizing_result_to_params(
    roles: dict[str, RoleTarget],
    Cc_f: float,
    Ib_a: float,
    Rc_ohm: Optional[float] = None,
    l_overrides: Optional[dict[str, float]] = None,
) -> dict:
    """
    Convert a dict of RoleTargets to a flat CircuitCollector params dict.

    Handles all 6 roles + Cc + ibias. M2/M4 are handled by TOML mosfet_pairs.

    Mirror logic:
      - BIAS_GEN (M5) + TAIL (M6): share per-finger W/L, ratio via M count
      - OUTPUT_BIAS (M8): mirrors M5, same per-finger W/L if same L

    Args:
        roles:        Dict of role name -> RoleTarget
        Cc_f:         Compensation capacitor value in Farads
        Ib_a:         Bias current in Amperes (for ibias param)
        Rc_ohm:       Nulling resistor value in Ohms (= 1/gm7); None to skip
        l_overrides:  Optional {role: L_um} overrides

    Returns:
        Flat params dict, e.g.:
        {
          "M3_L": 0.5, "M3_WL_ratio": 5.0, "M3_M": 1,
          "M1_L": 0.5, "M1_WL_ratio": 4.0, "M1_M": 1,
          "M5_L": 1.0, "M5_WL_ratio": 2.8, "M5_M": 1,
          "M6_L": 1.0, "M6_WL_ratio": 2.8, "M6_M": 3,
          "M7_L": 0.5, "M7_WL_ratio": 5.0, "M7_M": 2,
          "M8_L": 1.0, "M8_WL_ratio": 3.5, "M8_M": 4,
          "C1_value": 2.5e-12,
          "ibias": 2e-5,
        }
    """
    params = {}

    # Independent roles: DIFF_PAIR, LOAD, OUTPUT_CS
    for role in ("DIFF_PAIR", "LOAD", "OUTPUT_CS"):
        if role not in roles:
            continue
        target = roles[role]
        if l_overrides and role in l_overrides:
            target = dataclasses.replace(target, L_guidance_um=l_overrides[role])
        params.update(_role_to_params(role, target))

    # BIAS_GEN (M5) + TAIL (M6): current mirror pair (share per-finger W/L)
    bias_gen = roles.get("BIAS_GEN")
    tail = roles.get("TAIL")
    if bias_gen and tail and bias_gen.id_derived and tail.id_derived:
        L_um = bias_gen.L_guidance_um or 1.0
        if l_overrides:
            L_um = l_overrides.get("TAIL", l_overrides.get("BIAS_GEN", L_um))

        gm_id_ref = 12.0
        id_ref = bias_gen.id_derived     # Ib (M5 unit cell)
        id_tail = tail.id_derived        # I_tail (M6)

        wl_min, wl_max = _WL_RATIO_RANGE["nfet"]
        try:
            id_w = lut_query("nfet", "id_w", L_um, gm_id_val=gm_id_ref)
            W_unit = id_ref * 1e6 / id_w
            WL_unit = W_unit / L_um
        except (FileNotFoundError, ValueError):
            WL_unit = wl_min

        M5 = max(1, math.ceil(WL_unit / wl_max))
        WL_per_finger = max(wl_min, WL_unit / M5)

        mirror_ratio = id_tail / id_ref
        M6 = max(1, round(mirror_ratio * M5))

        params.update({
            "M5_L":        round(L_um, 3),
            "M5_WL_ratio": round(WL_per_finger, 2),
            "M5_M":        M5,
            "M6_L":        round(L_um, 3),
            "M6_WL_ratio": round(WL_per_finger, 2),
            "M6_M":        M6,
        })

    # OUTPUT_BIAS (M8): mirrors from M5, same per-finger W/L
    output_bias = roles.get("OUTPUT_BIAS")
    if output_bias and bias_gen and output_bias.id_derived and bias_gen.id_derived:
        mirror_ratio_s2 = output_bias.id_derived / bias_gen.id_derived
        L_ob = output_bias.L_guidance_um or 1.0
        if l_overrides and "OUTPUT_BIAS" in l_overrides:
            L_ob = l_overrides["OUTPUT_BIAS"]

        # If L matches M5, use same WL_per_finger and scale M
        if abs(L_ob - (bias_gen.L_guidance_um or 1.0)) < 0.01:
            M8_wl = params.get("M5_WL_ratio", wl_min)
            M8 = max(1, round(mirror_ratio_s2 * params.get("M5_M", 1)))
            params.update({
                "M8_L":        round(L_ob, 3),
                "M8_WL_ratio": M8_wl,
                "M8_M":        M8,
            })
        else:
            # Different L: size independently
            params.update(_role_to_params("OUTPUT_BIAS", output_bias))

    # Compensation cap, nulling resistor, and bias current
    params["C1_value"] = Cc_f
    if Rc_ohm is not None:
        params["Rc_value"] = Rc_ohm
    params["ibias"] = Ib_a

    return params


# ---------------------------------------------------------------------------
# 2. Simulation convenience wrapper
# ---------------------------------------------------------------------------

def simulate_circuit(
    params: dict,
    config_path: str = DEFAULT_CONFIG_PATH,
    spec_list: Optional[list[str]] = None,
    corner: Optional[str] = None,
    temperature: Optional[float] = None,
    supply_voltage: Optional[float] = None,
    CL: Optional[float] = None,
    output_dir: Optional[str] = None,
) -> dict:
    """
    Call CircuitCollector and return parsed results (specs + transistor OPs).

    Args:
        params:         Device parameter dict (e.g. from sizing_result_to_params).
        config_path:    CircuitCollector TOML config path.
        spec_list:      Spec keys to request; defaults to DEFAULT_SPEC_LIST.
        corner:         Process corner override: 'tt', 'ff', 'ss', 'fs', 'sf'.
        temperature:    Simulation temperature in °C (default: 27).
        supply_voltage: Supply voltage override in V (default: from TOML).
        CL:             Load capacitance override in pF (default: from TOML).
        output_dir:     Unique output directory for this simulation run.
                        Required for parallel execution — each concurrent call
                        must use a separate directory (e.g. tempfile.mkdtemp())
                        to avoid file-path conflicts between ngspice processes.

    Returns:
        {
          "specs":        dict of circuit performance metrics,
          "transistors":  dict[str, TransistorOP],
          "raw_response": full CircuitCollector response,
        }

    Raises:
        RuntimeError: if CircuitCollector server is not reachable.
    """
    if not check_server():
        raise RuntimeError("CircuitCollector not reachable at http://localhost:8001")

    # Merge PVT overrides into the params dict
    # CircuitCollector sim_api routes these to the correct TOML sections
    merged_params = dict(params)
    if corner is not None:
        merged_params["corner"] = corner
    if temperature is not None:
        merged_params["temperature"] = temperature
    if supply_voltage is not None:
        merged_params["supply_voltage"] = supply_voltage
    if CL is not None:
        merged_params["CL"] = CL

    response = simulate(
        params=merged_params,
        base_config_path=config_path,
        spec_list=spec_list or DEFAULT_SPEC_LIST,
        output_dir=output_dir,
    )

    return {
        "specs": parse_specs(response),
        "transistors": parse_response(response),
        "raw_response": response,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli_main():
    """Minimal CLI: send params JSON to CircuitCollector and print results."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Simulate a two-stage Miller OTA via CircuitCollector."
    )
    parser.add_argument(
        "--params", required=True,
        help='JSON dict of device params, e.g. \'{"M3_L":0.5,"M3_WL_ratio":5.0,...}\'',
    )
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG_PATH,
        help="CircuitCollector TOML config path",
    )
    parser.add_argument(
        "--specs", default=None,
        help='JSON list of spec keys, e.g. \'["dcgain_","phase_margin"]\'',
    )
    args = parser.parse_args()

    params = json.loads(args.params)
    spec_list = json.loads(args.specs) if args.specs else None

    try:
        result = simulate_circuit(params, config_path=args.config, spec_list=spec_list)
    except RuntimeError as e:
        print(json.dumps({"status": "error", "message": str(e)}, indent=2))
        return

    # Serialize transistor OPs
    transistors_out = {}
    for name, t in result["transistors"].items():
        transistors_out[name] = {
            "gm_uS": t.gm * 1e6,
            "gds_uS": t.gds * 1e6,
            "id_uA": t.id * 1e6,
            "gm_id": t.gm / t.id if t.id > 0 else None,
            "gm_gds": t.gm / t.gds if t.gds > 0 else None,
            "region": t.region,
            "vgs": t.vgs,
            "vds": t.vds,
            "vth": t.vth,
        }

    out = {
        "status": "ok",
        "specs": result["specs"],
        "transistors": transistors_out,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    _cli_main()
