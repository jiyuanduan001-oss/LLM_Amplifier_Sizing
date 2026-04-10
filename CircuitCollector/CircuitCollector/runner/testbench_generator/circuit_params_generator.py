from pathlib import Path
from typing import NoReturn
from jinja2 import Environment, FileSystemLoader
from CircuitCollector import load_toml
from CircuitCollector.utils.path import PROJECT_ROOT, get_pdk_path


class CircuitParamsGenerator:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.output_path = None
        self.raw_config = load_toml(config_path)

        # flatten nested structure (can be replaced with recursive flatten_dict)
        self.circuit_params = self.raw_config["circuit"]["params"]
        self.params_format = self.raw_config["circuit"]["params_format"]

        # set template loading path for the circuit instance
        self.circuit_type = self.raw_config["type"]["name"]
        self.netlist_name = self.raw_config[f"{self.circuit_type}"]["name"]
        self.circuit_instance_path = (
            PROJECT_ROOT / f"circuits/{self.circuit_type}/{self.netlist_name}"
        )
        self.env = Environment(loader=FileSystemLoader(str(self.circuit_instance_path)))
        self.config: dict[str, float | int] = {}

    def scan_params(self):
        """
        Scan the circuit params
        There are two types of params:
        1. params with width to length ratio
        2. params without width to length ratio
        Controlled by the params_format in the config
        Transistor params are in the format of "M1_L", "M1_W", "M1_M"
        Capacitor params are in the format of "C1_L", "C1_W"
        """
        use_width_to_length_ratio = self.params_format.get(
            "use_width_to_length_ratio", False
        )
        ration_field_suffix = self.params_format.get("ration_field_suffix", "WL_ratio")

        # get the device prefixes
        all_keys = list(self.circuit_params.keys())
        dev_prefixes = sorted(set(key.split("_")[0] for key in all_keys))

        for pref in dev_prefixes:
            # MOSFET
            if pref.upper().startswith("M"):
                L_key = f"{pref}_L"
                W_key = f"{pref}_W"
                WL_ratio_key = f"{pref}_{ration_field_suffix}"
                M_key = f"{pref}_M"

                # Length
                if L_key not in self.circuit_params:
                    raise KeyError(f"Missing {L_key} in the [circuit.params]")
                # round the length value to 2 decimal places
                L_val = round(float(self.circuit_params[L_key]), 2)

                # Multiplier, default to 1
                M_val = int(self.circuit_params.get(M_key, 1))

                # Width: if use_width_to_length_ratio is True, use the WL_ratio to calculate the width
                if use_width_to_length_ratio:
                    if WL_ratio_key not in self.circuit_params:
                        raise KeyError(
                            f"Missing {WL_ratio_key} in the [circuit.params] while use_width_to_length_ratio is True"
                        )
                    WL_ratio_val = float(self.circuit_params[WL_ratio_key])
                    # round the width value to 2 decimal places
                    W_val = round(float(L_val * WL_ratio_val), 2)
                else:
                    if W_key not in self.circuit_params:
                        raise KeyError(
                            f"Missing {W_key} in the [circuit.params] while use_width_to_length_ratio is False"
                        )
                    W_val = round(float(self.circuit_params[W_key]), 2)

                # set the values to the config
                self.config[L_key] = L_val
                self.config[W_key] = W_val
                self.config[M_key] = M_val
            # Capacitor
            elif pref.upper().startswith("C"):
                L_key = f"{pref}_L"
                W_key = f"{pref}_W"
                value_key = f"{pref}_value"

                # if value key is in the circuit params, set the value to the config and ignore the L and W keys
                if value_key in self.circuit_params:
                    self.config[value_key] = self.circuit_params[value_key]
                else:
                    # if value key is not in the circuit params, set the L and W values to the config
                    if L_key not in self.circuit_params:
                        raise KeyError(f"Missing {L_key} in the [circuit.params]")
                    L_val = int(self.circuit_params[L_key])
                    if W_key not in self.circuit_params:
                        raise KeyError(f"Missing {W_key} in the [circuit.params]")
                    W_val = int(self.circuit_params[W_key])
                    self.config[L_key] = L_val
                    self.config[W_key] = W_val
            # Resistor
            elif pref.upper().startswith("R"):
                # TODO: Once the PDK supports resistor, add the L and W keys to the config
                value_key = f"{pref}_value"
                if value_key in self.circuit_params:
                    self.config[value_key] = self.circuit_params[value_key]
                else:
                    raise KeyError(f"Missing {value_key} in the [circuit.params]")

    def generate(self, output_path: Path = None):
        """
        Render the circuit params netlist
        """
        self.output_path = (
            output_path or PROJECT_ROOT / f"temp/{self.config_path.stem}.txt"
        )
        template = self.env.get_template("netlist.j2")

        self.config["netlist_name"] = self.netlist_name

        self.scan_params()
        rendered = template.render(**self.config)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(rendered)
            print(f"[✓] render done: {output_path}")
        else:
            raise ValueError("output_path is required")
