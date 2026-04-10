from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from CircuitCollector import load_toml
from CircuitCollector.utils.path import PROJECT_ROOT, get_pdk_path


class TestbenchGenerator:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.raw_config = load_toml(config_path)

        self.tech_name = self.raw_config["tech"]["name"]
        self.pdk_path = get_pdk_path(
            self.tech_name, self.raw_config["tech_lib"]["pdk_path"]
        )
        self.netlist_name = self.raw_config[self.raw_config["type"]["name"]]["name"]

        # flatten nested structure (can be replaced with recursive flatten_dict)
        self.config = {
            "tech_name": self.tech_name,
            "circuit_type": self.raw_config["type"]["name"],
            "netlist_name": self.netlist_name,
            "pdk_path": self.pdk_path,
            "corner": self.raw_config["tech_lib"]["corner"],
            "temperature": self.raw_config.get("testbench", {})
            .get("dc", {})
            .get("temperature", 27),
            "measure_DC": self.raw_config["testbench"]["dc"]["measure_DC"],
            "supply_voltage": self.raw_config["testbench"]["dc"]["supply_voltage"],
            "VCM_ratio": self.raw_config["testbench"]["dc"]["VCM_ratio"],
            "measure_AC": self.raw_config["testbench"]["ac"]["measure_AC"],
            "PARAM_CLOAD": self.raw_config["testbench"]["ac"]["PARAM_CLOAD"],
            "ac_freq": self.raw_config["testbench"]["ac"]["ac_freq"],
            "ac_amp": self.raw_config["testbench"]["ac"]["ac_amp"],
            "use_ibias": self.raw_config.get("testbench", {})
            .get("ibias", {})
            .get("use_ibias", True),
            "use_multi_ibias": self.raw_config.get("testbench", {})
            .get("ibias", {})
            .get("multi_ibias", False),
            "num_ibias": self.raw_config.get("testbench", {})
            .get("ibias", {})
            .get("num_ibias", 1),
            "data_DC": f"{self.netlist_name}_{self.raw_config['testbench']['data']['data_DC']}",
            "data_AC": f"{self.netlist_name}_{self.raw_config['testbench']['data']['data_AC']}",
            "data_GBW_PM": f"{self.netlist_name}_{self.raw_config['testbench']['data']['data_GBW_PM']}",
            # Noise
            "measure_noise": self.raw_config.get("testbench", {})
            .get("noise", {})
            .get("measure_noise", False),
            "noise_fstart": self.raw_config.get("testbench", {})
            .get("noise", {})
            .get("noise_fstart", 0.1),
            "noise_fstop": self.raw_config.get("testbench", {})
            .get("noise", {})
            .get("noise_fstop", "1G"),
            "noise_fspot": self.raw_config.get("testbench", {})
            .get("noise", {})
            .get("noise_fspot", 10000),
            "data_NOISE": f"{self.netlist_name}_{self.raw_config.get('testbench', {}).get('data', {}).get('data_NOISE', 'NOISE')}",
            # Slew rate
            "measure_slew_rate": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("measure_slew_rate", False),
            "sr_vstep": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_vstep", 0.2),
            "sr_tdelay": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_tdelay", "10n"),
            "sr_trise": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_trise", "1n"),
            "sr_tfall": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_tfall", "1n"),
            "sr_tpw": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_tpw", "5u"),
            "sr_tperiod": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_tperiod", "10u"),
            "sr_tstep": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_tstep", "1n"),
            "sr_tstop": self.raw_config.get("testbench", {})
            .get("slew_rate", {})
            .get("sr_tstop", "20u"),
            "data_SLEW_RATE": f"{self.netlist_name}_{self.raw_config.get('testbench', {}).get('data', {}).get('data_SLEW_RATE', 'SLEW_RATE')}",
            # Output swing
            "measure_output_swing": self.raw_config.get("testbench", {})
            .get("output_swing", {})
            .get("measure_output_swing", False),
            "swing_vstep": self.raw_config.get("testbench", {})
            .get("output_swing", {})
            .get("swing_vstep", 0.001),
            "swing_transistor_dict": self.raw_config.get("circuit", {})
            .get("op_region", {})
            .get("transistor_dict", {}),
            "swing_device_prefix": self.raw_config.get("circuit", {})
            .get("op_region", {})
            .get("device_prefix", ""),
            "data_OUTPUT_SWING": f"{self.netlist_name}_{self.raw_config.get('testbench', {}).get('data', {}).get('data_OUTPUT_SWING', 'OUTPUT_SWING')}",
            "extract_op_region": self.raw_config.get("circuit", {})
            .get("op_region", {})
            .get("extract_op_region", False),
        }

        # set tech template path for Jinja2
        self.config["tech_path"] = f"tech_lib/{self.config['tech_name']}/pdk.j2"

        # set template loading path
        spec_lib_root = PROJECT_ROOT / "spec_lib"
        self.env = Environment(loader=FileSystemLoader(str(spec_lib_root)))
        self.output_path = PROJECT_ROOT / "temp"

    def circuit_params_render(self, output_path: Path = None) -> None:
        from CircuitCollector.runner.render import CircuitParamsRenderer

        config = self.config_path
        if output_path is not None:
            # Per-request: write next to the .cir file so concurrent requests don't overwrite
            output = output_path.parent / "temp_circuit_params.txt"
        else:
            output = PROJECT_ROOT / "temp/test_opamp_params.txt"
        renderer = CircuitParamsRenderer(config, output)
        self.config["circuit_params_path"] = output
        renderer.run()

    def ibias_render(self) -> None:
        """
        Bias current params are in the format of "ibias"(multi_ibias=False) or "ibias_1"(multi_ibias=True)
        """
        if self.config["use_multi_ibias"]:
            for i in range(self.config["num_ibias"]):
                self.config[f"ibias_{i}"] = self.raw_config["testbench"]["ibias"][
                    f"ibias_{i}"
                ]
        else:
            self.config["ibias"] = self.raw_config["testbench"]["ibias"]["ibias"]

    def generate(
        self,
        output_path: Path = None,
    ):
        """
        Render high-level main.j2 with pre-rendered blocks: tech_block, header_block, etc.
        """
        # first render the circuit params (same dir as .cir to avoid concurrent overwrite)
        self.circuit_params_render(output_path)

        if self.config["use_ibias"]:
            self.ibias_render()

        if not any(
            self.config[k]
            for k in ("measure_DC", "measure_AC", "measure_noise",
                       "measure_slew_rate", "measure_output_swing",
                       "extract_op_region")
        ):
            raise ValueError(
                "There is no simulation to generate, please check the config file, "
                "make sure at least one of the following is true: "
                "measure_DC, measure_AC, measure_noise, measure_slew_rate, "
                "measure_output_swing, extract_op_region"
            )


        # render the circuit op region if needed
        if self.config["extract_op_region"]:
            op_region_output_path = output_path.parent / "temp_op_region.spice"
            self.config["op_region_spice"] = op_region_output_path
            # print(f"Generated circuit op region: {op_region_output_path}")

        # blocks path
        blocks = {
            "tech_block": self.config["tech_path"],
            "header_block": "base/header.j2",
            "circuit_block": f"{self.config['circuit_type']}/circuit.j2",
            "simulation_block": f"{self.config['circuit_type']}/simulation.j2",
        }

        # render each block
        rendered_blocks = {
            block_name: self.env.get_template(block_path).render(self.config)
            for block_name, block_path in blocks.items()
        }

        # render main template
        template_name = f"{self.config['circuit_type']}/main.j2"
        template = self.env.get_template(template_name)
        rendered = template.render(**self.config, **rendered_blocks)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(rendered)
            print(f"[✓] render done: {output_path}")
        else:
            raise ValueError("output_path is required")
