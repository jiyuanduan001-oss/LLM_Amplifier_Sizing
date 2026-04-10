# CircuitCollector/test/sim_api.py
from __future__ import annotations
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
import toml

from CircuitCollector.runner.simulation_runner import SimulationRunner
from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector.utils.toml import load_toml
from CircuitCollector.cache import CacheManager

logger = logging.getLogger(__name__)


class SimulationAPI:
    """
    A thin wrapper to run one-shot simulations with param overrides, and
    return (1) selected specs, (2) formatted device OP-region metrics and (3) raw simulator result.

    Usage:
        api = SimulationAPI()
        out = api.run({"M1_L": 0.2, "M1_W": 0.55})
        print(out["specs"], out["op_region"], out["raw"])
    """

    DEFAULT_ALL_SPEC_KEYS = [
        "tc",
        "power",
        "vos25",
        "cmrrdc",
        "dcpsrp",
        "dcpsrn",
        "dcgain_",
        "gain_bandwidth_product_",
        "phase_margin",
    ]

    def __init__(
        self,
        base_config_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        spec_list: Optional[List[str]] = None,
        cache_manager: Optional[CacheManager] = None,
    ) -> None:
        # paths
        self.base_config_path: Path = (
            (PROJECT_ROOT / base_config_path)
            if base_config_path
            else (PROJECT_ROOT / "config/skywater/opamp/tsm.toml")
        )
        base_config = load_toml(self.base_config_path)
        circuit_type = base_config["type"]["name"]
        circuit_name = base_config[circuit_type]["name"]

        self.output_dir: Path = (
            (PROJECT_ROOT / output_dir)
            if output_dir
            else (PROJECT_ROOT / f"output/{circuit_type}/{circuit_name}")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # which specs to extract
        self.spec_list = spec_list or [
            "dcgain_",
            "gain_bandwidth_product_",
            "phase_margin",
        ]

        # cache
        self._base_config_cache: Dict[str, Any] = base_config
        self.cache_manager = cache_manager

    # ---------------------- Public API ----------------------

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single simulation with param overrides.
        Uses cache if available: Redis → SQLite → Simulation.
        Returns dict:
        {
            "specs": {...},          # selected specs
            "op_region": {...},      # per-device gm/Id, sat_margin, etc.
            "raw": {...}             # full simulator result dict (optional)
        }
        """
        # Get relative path for cache key (circuit identifier)
        circuit_key = str(self.base_config_path.relative_to(PROJECT_ROOT))
        
        # Try cache with distributed lock
        if self.cache_manager is not None:
            cached, lock = self.cache_manager.get_with_lock(circuit_key, params)
            if cached is not None and self._is_valid_cached_result(cached):
                # Cache hit: return cached result
                return {
                    "specs": cached.get("specs", {}),
                    "op_region": cached.get("op_region", {}),
                    "raw": cached.get("raw", {}),
                }
            
            # Cache miss: run simulation while holding lock
            try:
                results = self._run_simulation(params)
                formatted_result = {
                    "specs": self._select_specs(results, self.spec_list),
                    "op_region": self._format_op_region(results),
                    "raw": results,
                }
                
                # Store in cache (with circuit identifier) only if valid
                if self._is_valid_result(formatted_result):
                    cache_value = {
                        "circuit": circuit_key,
                        "params": params,
                        "specs": formatted_result["specs"],
                        "op_region": formatted_result["op_region"],
                        "raw": formatted_result["raw"],
                    }
                    try:
                        self.cache_manager.set(circuit_key, params, cache_value)
                    except sqlite3.DatabaseError as e:
                        # e.g. "database disk image is malformed" - still return result
                        logger.warning("Cache write failed (SQLite): %s", e)
                
                return formatted_result
            finally:
                # Release lock safely
                if lock is not None:
                    try:
                        lock.release()
                    except Exception:
                        # Lock might have been released or expired, ignore
                        pass
        else:
            # No cache: run simulation directly
            results = self._run_simulation(params)
            return {
                "specs": self._select_specs(results, self.spec_list),
                "op_region": self._format_op_region(results),
                "raw": results,
            }

    # ---------------------- Internals -----------------------

    # Keys that map to specific TOML sections instead of [circuit.params]
    _TESTBENCH_OVERRIDES = {
        "corner": ("tech_lib", "corner"),
        "supply_voltage": ("testbench", "dc", "supply_voltage"),
        "temperature": ("testbench", "dc", "temperature"),
        "PARAM_CLOAD": ("testbench", "ac", "PARAM_CLOAD"),
        "CL": ("testbench", "ac", "PARAM_CLOAD"),  # alias used by AnalogAgent
    }

    def _run_simulation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a temp config with param overrides and run the simulator.
        """
        # load fresh copy to avoid in-place mutation issues
        config = load_toml(self.base_config_path)

        # flip to API mode, disable params_file
        config["circuit"]["params_file"]["use_params_file"] = False
        config["circuit"]["params_file"]["API_mode"] = True

        # separate testbench overrides from circuit sizing params
        sizing_params = {}
        for key, value in params.items():
            if key in self._TESTBENCH_OVERRIDES:
                # route to the correct TOML section
                path = self._TESTBENCH_OVERRIDES[key]
                section = config
                for part in path[:-1]:
                    section = section.setdefault(part, {})
                section[path[-1]] = value
            elif key.startswith("ibias"):
                # ibias params go to [testbench.ibias]
                config.setdefault("testbench", {}).setdefault("ibias", {})[key] = value
            else:
                sizing_params[key] = value

        # merge/override circuit sizing params
        circuit_params = config["circuit"]["params"]
        circuit_params.update(sizing_params)
        config["circuit"]["params"] = circuit_params

        # dump to temp file
        temp_config_path = self.output_dir / "test_API_mode.toml"
        with open(temp_config_path, "w") as f:
            toml.dump(config, f)

        # run
        runner = SimulationRunner(temp_config_path, self.output_dir)
        results = runner.run_simulations()
        if not isinstance(results, dict):
            raise RuntimeError("SimulationRunner returned invalid results.")
        return results

    def _is_valid_cached_result(self, cached: Dict[str, Any]) -> bool:
        """
        Treat empty cached results as invalid to avoid serving bad data.
        """
        if not isinstance(cached, dict):
            return False
        specs = cached.get("specs") or {}
        raw = cached.get("raw") or {}
        op_region = cached.get("op_region") or {}
        return (
            self._has_non_null_value(specs)
            or self._has_non_null_value(raw)
            or self._has_non_null_value(op_region)
        )

    def _is_valid_result(self, result: Dict[str, Any]) -> bool:
        """
        Decide whether a fresh simulation result is cache-worthy.
        """
        if not isinstance(result, dict):
            return False
        specs = result.get("specs") or {}
        raw = result.get("raw") or {}
        op_region = result.get("op_region") or {}
        return (
            self._has_non_null_value(specs)
            or self._has_non_null_value(raw)
            or self._has_non_null_value(op_region)
        )

    def _has_non_null_value(self, value: Any) -> bool:
        """
        Recursively check for any non-None value in nested structures.
        """
        if value is None:
            return False
        if isinstance(value, dict):
            return any(self._has_non_null_value(v) for v in value.values())
        if isinstance(value, list):
            return any(self._has_non_null_value(v) for v in value)
        return True

    def _select_specs(
        self, results: Dict[str, Any], spec_list: List[str]
    ) -> Dict[str, Any]:
        return {k: results.get(k) for k in spec_list}

    def _format_op_region(self, results: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Assemble per-device metrics (gm/Id, sat margin, etc.)
        """
        all_spec_keys = set[str](self.DEFAULT_ALL_SPEC_KEYS)
        device_data: Dict[str, Dict[str, Any]] = {}
        device_capacitor_data: Dict[str, Dict[str, Any]] = {}

        for key, val in results.items():
            # keys like gm_m1, id_m1, vdsat_m3 ...
            if "_" not in key or key in all_spec_keys:
                continue
            prefix, dev = key.split("_", 1)  # e.g., "gm", "m1"
            dev = dev.lower()

            # skip capacitor
            if dev.startswith("c"):
                device_capacitor_data.setdefault(dev, {})[prefix] = val
                continue

            device_data.setdefault(dev, {})[prefix] = val

        formatted: Dict[str, Dict[str, Any]] = {}
        formatted_capacitor: Dict[str, Dict[str, Any]] = {}

        for dev, vals in device_data.items():
            gm = vals.get("gm")
            Id = vals.get("id")
            vds = vals.get("vds")
            vdsat = vals.get("vdsat")
            vgs = vals.get("vgs")
            vth = vals.get("vth")

            gm_over_Id = (
                (gm / abs(Id)) if (gm is not None and Id not in (None, 0)) else None
            )

            sat_margin = (
                (vds - vdsat) if (vds is not None and vdsat is not None) else None
            )

            vov = (vgs - vth) if (vgs is not None and vth is not None) else None

            formatted[dev] = {
                "gm": gm,
                "gds": vals.get("gds"),
                "Id": Id,
                "gm/Id": f"{gm_over_Id:.2f}" if gm_over_Id is not None else None,
                "vds": vds,
                "vdsat": vdsat,
                "sat_margin": sat_margin,
                "vgs": vgs,
                "vth": vth,
                "vov": vov,
                "cgs": vals.get("cgs"),
                "cgd": vals.get("cgd"),
                "cdb": vals.get("cdb"),
                "csb": vals.get("csb"),
            }

        for dev, vals in device_capacitor_data.items():
            capacitance = vals.get("capacitance")
            formatted_capacitor[dev] = {
                "capacitance": capacitance,
            }

        combined = {**formatted, **formatted_capacitor}

        return combined
