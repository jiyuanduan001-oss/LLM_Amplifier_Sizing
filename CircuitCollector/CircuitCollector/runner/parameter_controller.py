from pathlib import Path
import csv
from CircuitCollector.utils.toml import load_toml
from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector.utils.enums import SimulationStrategy


class ParameterController:
    def __init__(self, base_config_path: Path):
        self.base_config_path = Path(base_config_path)
        self.base_config = load_toml(base_config_path)

        params_file_cfg = self.base_config.get("circuit", {}).get("params_file", {})
        self.use_params_file = params_file_cfg.get("use_params_file", False)
        self.generate_params_file = params_file_cfg.get("generate_params_file", False)

        circuit_type = self.base_config["type"]["name"]
        netlist_name = self.base_config[circuit_type]["name"]
        self.csv_path = (
            PROJECT_ROOT / f"circuits/{circuit_type}/{netlist_name}/params.csv"
        )

    def get_simulation_strategy(self):
        if not self.use_params_file:
            return {
                "strategy": SimulationStrategy.SINGLE_CONFIG,
                "description": "Use parameters from circuit.params section",
                "params": {
                    "circuit_params": self.base_config.get("circuit", {}).get(
                        "params", {}
                    ),
                    "API_mode": self.base_config.get("circuit", {})
                    .get("params_file", {})
                    .get("API_mode", False),
                },
            }

        elif self.use_params_file and self.generate_params_file:
            return {
                "strategy": SimulationStrategy.GENERATE_AND_SIMULATE,
                "description": "Generate CSV file and simulate row by row",
                "csv_path": self.csv_path,
                "total_rows": self._get_csv_row_count(),
            }

        elif self.use_params_file and not self.generate_params_file:
            if not self.csv_path.exists():
                raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
            return {
                "strategy": SimulationStrategy.READ_AND_SIMULATE,
                "description": "Read existing CSV file and simulate row by row",
                "csv_path": self.csv_path,
                "total_rows": self._get_csv_row_count(),
            }

        else:
            raise ValueError("Invalid simulation strategy configuration")

    def get_parameters_for_row(self, row_index: int):
        if not self.use_params_file:
            return self.base_config.get("circuit", {}).get("params", {})
        return self._read_csv_row(row_index)

    def _get_csv_row_count(self):
        if not self.csv_path.exists():
            return 0
        with open(self.csv_path, "r") as f:
            return sum(1 for _ in csv.reader(f)) - 1

    def _read_csv_row(self, row_index: int):
        with open(self.csv_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            for current_row, row in enumerate(reader, 1):
                if current_row == row_index:
                    params = {}
                    for i, value in enumerate(row):
                        if i < len(header):
                            param = header[i]
                            if param.endswith("_M"):
                                value = int(value)
                            elif param.startswith("ibias"):
                                value = float(value)
                            else:
                                value = round(float(value), 2)
                            params[param] = value
                    return params
        raise IndexError(f"Row {row_index} not found")
