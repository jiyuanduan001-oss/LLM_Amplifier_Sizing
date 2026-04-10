from pathlib import Path
from typing import NoReturn
from jinja2 import Environment, FileSystemLoader
from CircuitCollector import load_toml
from CircuitCollector.utils.path import PROJECT_ROOT, get_pdk_path


class CircuitOpRegionGenerator:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.output_path = None
        self.raw_config = load_toml(config_path)

        # flatten nested structure (can be replaced with recursive flatten_dict)
        self.circuit_op_region = self.raw_config["circuit"].get("op_region", {})
        self.is_extract_op_region = self.circuit_op_region.get(
            "extract_op_region", False
        )
        self.device_prefix = self.circuit_op_region.get("device_prefix", "")
        self.op_variable_list_mos = self.circuit_op_region.get(
            "op_variable_list_mos", []
        )
        self.op_variable_list_cap = self.circuit_op_region.get(
            "op_variable_list_cap", []
        )
        self.transistor_dict = self.circuit_op_region.get("transistor_dict", {})
        self.cap_dict = self.circuit_op_region.get("cap_dict", {})

        # set template loading path for the circuit instance
        self.circuit_type = self.raw_config["type"]["name"]
        self.netlist_name = self.raw_config[f"{self.circuit_type}"]["name"]
        self.circuit_instance_path = (
            PROJECT_ROOT / f"circuits/{self.circuit_type}/{self.netlist_name}"
        )
        # self.env = Environment(loader=FileSystemLoader(str(self.circuit_instance_path)))
        # self.config: dict[str, float | int] = {}

    def generate(self, output_path: Path = None):
        """
        Render the circuit params netlist
        """
        self.output_path = (
            output_path
            or PROJECT_ROOT / f"temp/{self.config_path.stem}_op_region.spice"
        )

        template_list = []
        # extract transistor variables
        for transistor_name, transistor_type in self.transistor_dict.items():
            extracted_transistor_variable = (
                f"@m.x1.X{transistor_name}.{self.device_prefix}{transistor_type}"
            )
            template_list.extend(
                f"let {attr}_{transistor_name} = {extracted_transistor_variable}[{attr}]"
                for attr in self.op_variable_list_mos
            )

        # extract capacitor variables
        if self.cap_dict:
            for cap_name, cap_type in self.cap_dict.items():
                extracted_cap_variable = f"@c.x1.X{cap_name}.{cap_name.lower()}"
                template_list.extend(
                    f"let {attr}_{cap_name} = {extracted_cap_variable}[{attr}]"
                    for attr in self.op_variable_list_cap
                )

        # combine transistor and capacitor variables
        if self.transistor_dict:
            op_transistor_variable_list = [
                f"{attr}_{transistor_name}"
                for attr in self.op_variable_list_mos
                for transistor_name in self.transistor_dict.keys()
            ]
        else:
            op_transistor_variable_list = []

        if self.cap_dict:
            op_cap_variable_list = [
                f"{attr}_{cap_name}"
                for attr in self.op_variable_list_cap
                for cap_name in self.cap_dict.keys()
            ]
        else:
            op_cap_variable_list = []

        op_variable_list = op_transistor_variable_list + op_cap_variable_list

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                op_result_path = (
                    output_path.parent / f"{self.netlist_name}_OP_REGION.txt"
                )
                template_print = (
                    f"print {', '.join(op_variable_list)} > {op_result_path}"
                )
                template_list.append(template_print)
                f.write("\n".join(template_list))
            print(f"[✓] render done: {output_path}")
        else:
            raise ValueError("output_path is required")
