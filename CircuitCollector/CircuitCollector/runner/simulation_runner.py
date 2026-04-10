from pathlib import Path
from copy import deepcopy
import toml
from CircuitCollector.runner.result_parser import parse_opamp_simulation_results
from CircuitCollector.runner.simulator import Simulator
from CircuitCollector.runner.parameter_controller import ParameterController
from CircuitCollector.utils.enums import SimulationStrategy
from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector import (
    TestbenchRenderer,
    CircuitParamsRenderer,
    CircuitOpRegionRenderer,
)


class SimulationRunner:
    def __init__(self, base_config_path: Path, output_dir: Path = None):
        """
        Initialize Simulation Runner

        Args:
            base_config_path: Path to the base configuration file
            output_dir: Output directory for simulation files
        """
        self.base_config_path = Path(base_config_path)
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "temp"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.controller = ParameterController(base_config_path)
        self.simulator = Simulator()

        # Load base config
        with open(base_config_path, "r") as f:
            self.base_config = toml.load(f)

        self.circuit_type = self.base_config["type"]["name"]
        self.circuit_instance_name = self.base_config[f"{self.circuit_type}"]["name"]

    def run_simulations(self):
        """
        Run simulations based on configuration strategy

        Returns:
            List of simulation results
        """
        strategy = self.controller.get_simulation_strategy()
        print(f"Simulation strategy: {strategy['description']}")

        if strategy["strategy"] == SimulationStrategy.SINGLE_CONFIG:
            strategy_params = strategy["params"]
            circuit_params, API_mode = (
                strategy_params["circuit_params"],
                strategy_params["API_mode"],
            )
            return self._run_single_simulation(circuit_params, API_mode)

        elif strategy["strategy"] in [
            SimulationStrategy.GENERATE_AND_SIMULATE,
            SimulationStrategy.READ_AND_SIMULATE,
        ]:
            return self._run_batch_simulations(strategy)

    def _run_single_simulation(self, params, API_mode):
        """Run single simulation with given parameters"""
        print("Running single simulation...")
        
        # Generate config with parameters
        config = self._generate_config_with_params(params)

        # Save temporary config
        temp_config_path = self.output_dir / "temp_config.toml"
        with open(temp_config_path, "w") as f:
            toml.dump(config, f)

        # Render testbench circuit (.cir file)
        circuit_path = self.output_dir / f"{self.circuit_instance_name}_circuit.cir"
        testbench_renderer = TestbenchRenderer(temp_config_path, circuit_path)
        testbench_renderer.run()
        print(f"Generated testbench circuit: {circuit_path}")

        # Render circuit op
        op_region_path = self.output_dir / "temp_op_region.spice"
        op_region_renderer = CircuitOpRegionRenderer(temp_config_path, op_region_path)
        op_region_renderer.run()
        print(f"Generated circuit op region: {op_region_path}")

        # Render circuit parameters (sub circuit file)
        subcircuit_path = self.output_dir / "temp_circuit_params.txt"
        params_renderer = CircuitParamsRenderer(temp_config_path, subcircuit_path)
        params_renderer.run()
        print(f"Generated circuit parameters: {subcircuit_path}")

        # simulation result is valid if the simulation is successful with valid specs
        is_valid_simulation = self.simulator.run(circuit_path, "single_sim", 1)

        if is_valid_simulation:
            if self.circuit_type == "opamp":
                out = self.output_dir.resolve()
                result = parse_opamp_simulation_results(
                    dc_file=out / f"{self.circuit_instance_name}_DC.txt",
                    ac_file=out / f"{self.circuit_instance_name}_AC.txt",
                    gbw_pm_file=out / f"{self.circuit_instance_name}_GBW_PM.txt",
                    op_region_file=out / f"{self.circuit_instance_name}_OP_REGION.txt",
                    log_file=out / f"{self.circuit_instance_name}.log",
                    noise_file=out / f"{self.circuit_instance_name}_NOISE.txt",
                    slew_rate_file=out / f"{self.circuit_instance_name}_SLEW_RATE.txt",
                    output_swing_file=out / f"{self.circuit_instance_name}_OUTPUT_SWING.txt",
                )
            else:
                result = {}
        else:
            result = {}

        return result

    def _run_batch_simulations(self, strategy):
        """Run batch simulations row by row"""
        total_rows = strategy["total_rows"]
        print(f"Running {total_rows} simulations...")

        results = []

        # Use fixed file names for all simulations
        temp_config_path = self.output_dir / "temp_config.toml"
        circuit_path = self.output_dir / "temp_circuit.cir"
        subcircuit_path = self.output_dir / "temp_circuit_params.txt"

        # create a single log file for all simulations
        batch_log_path = self.output_dir / "batch_simulations.log"

        # Initialize the batch log file
        with open(batch_log_path, "w") as log_file:
            log_file.write(f"=== Batch Simulation Log ===\n")
            log_file.write(f"Total simulations: {total_rows}\n")
            log_file.write(f"Started at: {__import__('datetime').datetime.now()}\n\n")

        # Run simulations
        for row_index in range(1, total_rows + 1):
            print(f"\nProcessing simulation {row_index}/{total_rows}")

            try:
                # Get parameters for this row
                params = self.controller.get_parameters_for_row(row_index)
                print(f"Parameters: {params}")

                # log simulation start
                with open(batch_log_path, "a") as log_file:
                    log_file.write(f"--- Simulation {row_index}/{total_rows} ---\n")
                    log_file.write(f"Parameters: {params}\n")

                # Generate config (overwrite the same file)
                config = self._generate_config_with_params(params)

                # Save temporary config (overwrite)
                with open(temp_config_path, "w") as f:
                    toml.dump(config, f)

                # Render testbench circuit (.cir file) - overwrite
                testbench_renderer = TestbenchRenderer(temp_config_path, circuit_path)
                testbench_renderer.run()

                # Render circuit parameters (sub circuit file) - overwrite
                params_renderer = CircuitParamsRenderer(
                    temp_config_path, subcircuit_path
                )
                params_renderer.run()

                # simulation result is valid if the simulation is successful with valid specs
                is_valid_simulation = self.simulator.run(
                    circuit_path, f"sim_{row_index}", total_rows, batch_log_path
                )

                # Log simulation completion
                with open(batch_log_path, "a") as log_file:
                    log_file.write(f"✓ Simulation {row_index} completed successfully\n")
                    log_file.write(f"Result specs is valid: {is_valid_simulation}\n\n")

                if is_valid_simulation:
                    if self.circuit_type == "opamp":
                        result = parse_opamp_simulation_results(
                            dc_file=self.output_dir
                            / f"{self.circuit_instance_name}_DC.txt",
                            ac_file=self.output_dir
                            / f"{self.circuit_instance_name}_AC.txt",
                            gbw_pm_file=self.output_dir
                            / f"{self.circuit_instance_name}_GBW_PM.txt",
                            log_file=self.output_dir
                            / f"{self.circuit_instance_name}.log",
                            op_region_file=self.output_dir
                            / f"{self.circuit_instance_name}_OP_REGION.txt",
                            noise_file=self.output_dir
                            / f"{self.circuit_instance_name}_NOISE.txt",
                            slew_rate_file=self.output_dir
                            / f"{self.circuit_instance_name}_SLEW_RATE.txt",
                            output_swing_file=self.output_dir
                            / f"{self.circuit_instance_name}_OUTPUT_SWING.txt",
                        )
                    else:
                        result = {}
                else:
                    result = {}

                results.append(
                    {
                        "simulation_id": f"sim_{row_index}",
                        "row": row_index,
                        "params": params,
                        "result": result,
                        "status": "completed",
                        "circuit_path": str(circuit_path),
                        "subcircuit_path": str(subcircuit_path),
                        "log_path": str(batch_log_path),
                    }
                )

                print(f"✓ Simulation {row_index} completed")

            except Exception as e:
                print(f"Simulation {row_index} failed: {e}")

                # Log simulation failure
                with open(batch_log_path, "a") as log_file:
                    log_file.write(f"✗ Simulation {row_index} failed\n")
                    log_file.write(f"Error: {str(e)}\n\n")

                results.append(
                    {
                        "simulation_id": f"sim_{row_index}",
                        "row": row_index,
                        "params": {},
                        "result": None,
                        "status": "failed",
                        "error": str(e),
                        "log_path": str(batch_log_path),
                    }
                )

        # Log batch completion
        with open(batch_log_path, "a") as log_file:
            log_file.write(f"=== Batch Simulation Completed ===\n")
            log_file.write(f"Completed at: {__import__('datetime').datetime.now()}\n")
            successful = len([r for r in results if r.get("status") == "completed"])
            failed = len([r for r in results if r.get("status") == "failed"])
            log_file.write(
                f"Total: {len(results)}, Successful: {successful}, Failed: {failed}\n"
            )

        print(f"\n✓ All simulations completed. Check batch log: {batch_log_path}")
        return results

    def _generate_config_with_params(self, params):
        """Generate configuration with given parameters"""
        config = deepcopy(self.base_config)

        # Update circuit parameters
        if "circuit" not in config:
            config["circuit"] = {}
        if "params" not in config["circuit"]:
            config["circuit"]["params"] = {}

        for param, value in params.items():
            if param.startswith("ibias"):
                # Update ibias parameters
                if "testbench" not in config:
                    config["testbench"] = {}
                if "ibias" not in config["testbench"]:
                    config["testbench"]["ibias"] = {}
                config["testbench"]["ibias"][param] = value
            else:
                # Update circuit parameters
                config["circuit"]["params"][param] = value

        return config
