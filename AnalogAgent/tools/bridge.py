"""
Mapping layer between AnalogAgent sizing decisions and CircuitCollector simulation.

Responsibilities:
  1. role_target_to_params()  -- RoleTarget (gm/Id targets) -> CircuitCollector params dict
  2. sizing_result_to_params() -- SizingResult (all roles) -> CircuitCollector params dict
  3. parse_response()          -- CircuitCollector API response -> dict[str, TransistorOP]
  4. parse_specs()             -- CircuitCollector API response -> dict of circuit specs
  5. simulate_circuit()        -- convenience wrapper around api_client.simulate()

ROLE_DEVICE_MAP is topology-specific. The default below is for a 5T OTA
(SKILL.md Netlist Role Mapping: M1/M2=DIFF_PAIR, M5/M6=LOAD, M3=TAIL, M4=BIAS_REF).
If using a different circuit (e.g. tsm with M1-M8), update ROLE_DEVICE_MAP
or pass a custom map.

CircuitCollector raw output has per-device fields:
  gm_m1, gds_m1, vgs_m1, vds_m1, vth_m1, vdsat_m1, id_m1,
  cgs_m1 (negative sign, SPICE convention), cgd_m1, cdb_m1, csb_m1
Cgg = |cgs_m1| + |cgd_m1|  ->  extracted and stored in TransistorOP.cgg
"""

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Optional

from scripts.lut_lookup import lut_query
from tools.api_client import simulate, check_server


# ---------------------------------------------------------------------------
# Dataclasses (previously in scripts.op_extractor / scripts.sizing_engine)
# ---------------------------------------------------------------------------

@dataclass
class TransistorOP:
    """Operating-point snapshot for one MOSFET extracted from simulation."""
    name: str
    gm: float       # transconductance  (S)
    gds: float      # output conductance (S)
    id: float       # drain current      (A, positive)
    vgs: float      # gate-source voltage (V)
    vds: float      # drain-source voltage (V)
    vth: float      # threshold voltage   (V)
    region: str     # "saturation", "linear", "subthreshold", "unknown"
    cgg: float      # total gate capacitance Cgs+Cgd (F)


@dataclass
class SizingInputs:
    """High-level performance targets that drive the gm/Id sizing flow."""
    GBW_hz: float
    A0_linear: float
    CL_f: float
    VDD_v: float
    Ib_a: float
    PM_deg: float = 60.0
    SR_vps: Optional[float] = None
    P_max_w: Optional[float] = None


@dataclass
class RoleTarget:
    """Per-role sizing target produced by the sizing engine."""
    role: str
    inversion_region: Optional[str] = None
    gm_id_target: Optional[float] = None
    gm_required: Optional[float] = None
    id_derived: Optional[float] = None
    L_guidance_um: Optional[float] = None
    notes: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class SizingResult:
    """Aggregate output of initial gm/Id sizing for all roles."""
    roles: dict                          # role name -> RoleTarget
    P_estimate_w: float = 0.0
    SR_estimate_vps: float = 0.0
    A0_upper_linear: float = 0.0
    GBW_target_hz: float = 0.0
    feasible: bool = True
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 5T OTA role -> device mapping
# ---------------------------------------------------------------------------

# For each role: which devices it controls, device type for LUT, and which
# transistor name is the "primary" (others are matched via mosfet_pairs in TOML).
ROLE_DEVICE_MAP: dict[str, dict] = {
    "DIFF_PAIR": {
        "primary":     "M1",
        "mirrors":     ["M2"],   # TOML mosfet_pairs handles M2 = M1
        "device_type": "nfet",
    },
    "LOAD": {
        "primary":     "M5",
        "mirrors":     ["M6"],
        "device_type": "pfet",
    },
    "TAIL": {
        "primary":     "M3",
        "mirrors":     [],
        "device_type": "nfet",
    },
    "BIAS_REF": {
        "primary":     "M4",
        "mirrors":     [],
        "device_type": "nfet",
    },
}

# Default CircuitCollector config for 5tota (5T OTA, SKY130)
DEFAULT_CONFIG_PATH = "config/skywater/opamp/5tota.toml"
DEFAULT_OUTPUT_DIR  = "output/opamp/5tota"

# Spec keys requested from CircuitCollector by default
DEFAULT_SPEC_LIST = [
    # AC
    "dcgain_",
    "gain_bandwidth_product_",
    "phase_margin",
    "cmrr",
    "dcpsrp",
    "dcpsrn",
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
    # Gain-plateau detection
    "gain_peaking_db",
    "true_gbw",
]


# ---------------------------------------------------------------------------
# 1. gm/Id targets -> CircuitCollector params
# ---------------------------------------------------------------------------

def role_target_to_params(
    role: str,
    target: RoleTarget,
) -> dict:
    """
    Convert one role's sizing target to CircuitCollector parameter names.

    Uses LUT to compute W from (gm_id_target, L_guidance, id_derived).
    W/L ratio is what CircuitCollector expects (use_width_to_length_ratio = true).

    Args:
        role:   Role name, e.g. "DIFF_PAIR"
        target: RoleTarget with sizing targets

    Returns:
        Dict like {"M1_L": 0.18, "M1_WL_ratio": 5.2, "M1_M": 1}
    """
    mapping = ROLE_DEVICE_MAP[role]
    prefix = mapping["primary"]
    device = mapping["device_type"]

    L_um = target.L_guidance_um
    gm_id = target.gm_id_target
    id_a = target.id_derived

    if L_um is None or id_a is None:
        return {}

    # BIAS_REF (M4): diode-connected, no independent gm/Id target.
    # Use the L from sizing and match WL_ratio to TAIL if gm_id == 0.
    if gm_id is None or gm_id == 0:
        # Default WL_ratio = 2.8 (5tota minimum) -- toolchain will handle current
        return {
            f"{prefix}_L":        round(L_um, 3),
            f"{prefix}_WL_ratio": 2.8,
            f"{prefix}_M":        1,
        }

    # W from LUT: Id/W (uA/um) at this gm_id and L
    try:
        id_w_ua_um = lut_query(device, "id_w", L_um, gm_id_val=gm_id)
        W_um = id_a * 1e6 / id_w_ua_um   # id_a in A -> uA, then / (uA/um) = um
        WL_ratio = W_um / L_um
    except (FileNotFoundError, ValueError):
        # LUT not available -- use gm_id heuristic (rough estimate)
        # id_w ~ 50 uA/um at gm_id=12 for SKY130 NFET 180nm (fallback)
        W_um = max(0.55, id_a * 1e6 / 50.0)
        WL_ratio = W_um / L_um

    # 5tota TOML constrains WL_ratio to [2.8, 10.0].
    # Use M (finger multiplier) to keep per-finger WL_ratio within range.
    WL_RATIO_MAX = 10.0
    M = max(1, math.ceil(WL_ratio / WL_RATIO_MAX))
    WL_ratio_per_finger = WL_ratio / M

    params = {
        f"{prefix}_L":        round(L_um, 3),
        f"{prefix}_WL_ratio": round(WL_ratio_per_finger, 2),
        f"{prefix}_M":        M,
    }

    return params


def sizing_result_to_params(
    sizing_result: SizingResult,
    l_overrides: Optional[dict[str, float]] = None,
) -> dict:
    """
    Convert a full SizingResult to a flat CircuitCollector params dict.

    All roles are merged into one dict. Mirrors (M2, M6) are handled by
    mosfet_pairs in the TOML config -- we only set the primary device params.

    Args:
        sizing_result: SizingResult with role targets
        l_overrides:  Optional dict of role -> L (um) to override L selection,
                      e.g. {"DIFF_PAIR": 2.0, "LOAD": 2.0}.
                      Roles not listed keep their original L.

    Returns:
        Flat params dict for CircuitCollector, e.g.:
        {
          "M1_L": 0.18, "M1_WL_ratio": 5.2, "M1_M": 1,
          "M5_L": 0.18, "M5_WL_ratio": 4.8, "M5_M": 1,
          "M3_L": 0.5,  "M3_WL_ratio": 6.1, "M3_M": 1,
          "M4_L": 0.5,  "M4_WL_ratio": 6.1, "M4_M": 1,
        }
    """
    params = {}

    # DIFF_PAIR and LOAD: size independently
    for role in ("DIFF_PAIR", "LOAD"):
        if role not in sizing_result.roles:
            continue
        target = sizing_result.roles[role]
        if l_overrides and role in l_overrides:
            target = dataclasses.replace(target, L_guidance_um=l_overrides[role])
        params.update(role_target_to_params(role, target))

    # TAIL (M3) + BIAS_REF (M4): size as a current mirror pair.
    # M3 and M4 must share identical per-finger W/L so that the mirrored VGS
    # maps to the correct I_tail.  The ratio is implemented via M (finger count).
    tail   = sizing_result.roles.get("TAIL")
    bias   = sizing_result.roles.get("BIAS_REF")
    if tail and bias and tail.id_derived and bias.id_derived:
        L_um = tail.L_guidance_um or 1.0
        if l_overrides:
            L_um = l_overrides.get("TAIL", l_overrides.get("BIAS_REF", L_um))

        gm_id  = tail.gm_id_target or 11.0
        id_ref = bias.id_derived    # Ib  -- unit cell current (M4 carries this)
        id_main = tail.id_derived   # I_tail -- M3 carries this

        # Compute unit-cell W from LUT at (gm_id, L): both M3 and M4 share this
        WL_RATIO_MAX = 10.0
        try:
            id_w_ua_um = lut_query("nfet", "id_w", L_um, gm_id_val=gm_id)
            W_unit = id_ref * 1e6 / id_w_ua_um   # um, for one unit cell
            WL_unit = W_unit / L_um
        except (FileNotFoundError, ValueError):
            WL_unit = 2.8

        # Scale into allowed WL_ratio range using M for M4
        M4 = max(1, math.ceil(WL_unit / WL_RATIO_MAX))
        WL_per_finger = max(2.8, WL_unit / M4)

        # M3 finger count = round(I_tail / Ib) x M4 fingers
        mirror_ratio = id_main / id_ref
        M3 = max(1, round(mirror_ratio * M4))

        params.update({
            "M4_L":        round(L_um, 3),
            "M4_WL_ratio": round(WL_per_finger, 2),
            "M4_M":        M4,
            "M3_L":        round(L_um, 3),
            "M3_WL_ratio": round(WL_per_finger, 2),  # identical to M4
            "M3_M":        M3,
        })
    elif tail:
        # Fallback: process individually if BIAS_REF missing
        target = tail
        if l_overrides and "TAIL" in l_overrides:
            target = dataclasses.replace(target, L_guidance_um=l_overrides["TAIL"])
        params.update(role_target_to_params("TAIL", target))

    return params


# ---------------------------------------------------------------------------
# 2. CircuitCollector response -> TransistorOP dict
# ---------------------------------------------------------------------------

def _infer_region(vov: Optional[float], sat_margin: Optional[float]) -> str:
    """
    Infer operating region from vov (= vgs - vth) and sat_margin (= vds - vdsat).

    Convention:
      NFET: vov > 0 when on, sat_margin > 0 in saturation
      PFET: vov < 0 when on, sat_margin < 0 in saturation
      Both: |vov| < 0.05 V -> subthreshold
    """
    if vov is None:
        return "unknown"

    if abs(vov) < 0.05:
        return "subthreshold"

    if sat_margin is None:
        return "saturation"   # default if sat_margin not available

    # NFET: positive vov, sat_margin > 0 = saturation
    if vov > 0:
        return "saturation" if sat_margin >= -0.05 else "linear"
    # PFET: negative vov, sat_margin < 0 = saturation
    else:
        return "saturation" if sat_margin <= 0.05 else "linear"


def parse_response(response: dict) -> dict[str, TransistorOP]:
    """
    Convert CircuitCollector API response to a dict[str, TransistorOP].

    CircuitCollector op_region format (from _format_op_region in sim_api.py):
      - Keys: lowercase device names  e.g. "m1", "m3"
      - Fields: gm, Id (capital I), gm/Id (str), vds, vdsat, sat_margin, vgs, vov
      - NOT included: gds, vth (must be pulled from "raw")

    CircuitCollector raw format:
      - Keys like "gm_m1", "gds_m1", "vth_m1", "id_m1", ...

    Args:
        response: Full CircuitCollector response dict {specs, op_region, raw}

    Returns:
        dict[str, TransistorOP] keyed by uppercase device name e.g. "M1"
    """
    op_region = response.get("op_region", {})
    raw = response.get("raw", {})

    transistors: dict[str, TransistorOP] = {}

    for dev_lower, data in op_region.items():
        # Skip capacitors (C*) and resistors
        if dev_lower.startswith("c") or dev_lower.startswith("r"):
            continue

        name = dev_lower.upper()   # m1 -> M1

        gm       = data.get("gm") or 0.0
        id_val   = data.get("Id") or data.get("id") or 0.0
        vgs      = data.get("vgs") or 0.0
        vds      = data.get("vds") or 0.0
        vdsat    = data.get("vdsat") or 0.0
        vov      = data.get("vov")
        sat_margin = data.get("sat_margin")

        # gds: now returned directly in op_region (after sim_api.py fix)
        # Fall back to raw dict for backwards compatibility
        gds = data.get("gds") or raw.get(f"gds_{dev_lower}") or 0.0

        # vth: now returned directly in op_region; fallback: derive from vov = vgs - vth
        vth = data.get("vth") or raw.get(f"vth_{dev_lower}")
        if vth is None and vov is not None:
            vth = vgs - vov
        vth = vth or 0.0

        # Cgg = |Cgs| + |Cgd|. ngspice reports Cgs negative (SPICE convention).
        # op_region now includes cgs/cgd directly; fallback to raw dict.
        cgs = abs(data.get("cgs") or raw.get(f"cgs_{dev_lower}") or 0.0)
        cgd = abs(data.get("cgd") or raw.get(f"cgd_{dev_lower}") or 0.0)
        cgg = cgs + cgd

        region = _infer_region(vov, sat_margin)

        transistors[name] = TransistorOP(
            name=name,
            gm=float(gm),
            gds=float(gds),
            id=abs(float(id_val)),   # ensure positive
            vgs=float(vgs),
            vds=float(vds),
            vth=float(vth),
            region=region,
            cgg=float(cgg),
        )

    return transistors


def parse_specs(response: dict) -> dict:
    """Extract and normalize specs from CircuitCollector response."""
    specs = response.get("specs", {})
    # Normalize: drop None values
    normalized = {}
    for k, v in specs.items():
        if v is None:
            continue
        normalized[k] = v
    return normalized


# ---------------------------------------------------------------------------
# 3. Simulation convenience wrapper
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
          "specs":       dict of circuit performance metrics,
          "transistors": dict[str, TransistorOP],
          "raw_response": full CircuitCollector response,
        }

    Raises:
        RuntimeError: if CircuitCollector server is not reachable.
    """
    if not check_server():
        raise RuntimeError("CircuitCollector server not reachable at http://localhost:8001")

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
    """Minimal CLI: convert params JSON -> simulate -> print results."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Simulate a circuit via CircuitCollector and print parsed results."
    )
    parser.add_argument(
        "--params", required=True,
        help='JSON dict of device params, e.g. \'{"M1_L":0.18,"M1_WL_ratio":5.2,"M1_M":1}\'',
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

    # Serialize transistor OPs to human-readable format
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
