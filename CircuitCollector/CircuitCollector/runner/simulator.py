import os
from pathlib import Path
from datetime import datetime
from CircuitCollector.utils.log_checker import check_spice_log
from CircuitCollector.utils.path import PROJECT_ROOT
import time


class Simulator:
    def __init__(self, output_dir=None):
        # set output directory, default to jobs
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "jobs"
        # ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        netlist_path=None,
        simulation_id="default",
        total_simulations=1,
        batch_log_path=None,
    ):
        """
        Run ngspice simulation

        Args:
            netlist_path: netlist file path, if None, use self.output_dir
            simulation_id: simulation ID, for logging
            total_simulations: total simulations, for logging
            batch_log_path: optional batch log file path to append results

        Returns:
            log file path
        """
        # use provided path or default path (resolve to absolute so shell redirects go to correct file)
        sim_path = Path(netlist_path).resolve() if netlist_path else self.output_dir.resolve()

        # get netlist file name (without extension)
        if sim_path.exists() and sim_path.is_file():
            # if input is file path instead of directory
            netlist_file = sim_path
            sim_dir = netlist_file.parent
            base_name = netlist_file.stem
        else:
            sim_dir = sim_path
            sim_dir.mkdir(parents=True, exist_ok=True)
            # assume directory contains .cir or .spice files
            cir_files = list(sim_dir.glob("*.cir")) + list(sim_dir.glob("*.spice"))
            if not cir_files:
                raise FileNotFoundError(f"No .cir or .spice files found in {sim_dir}")
            netlist_file = cir_files[0]  # use the first found file
            base_name = netlist_file.stem

        sim_dir = sim_dir.resolve()
        sim_dir.mkdir(parents=True, exist_ok=True)
        # create timestamp and log file paths
        # Log name must match simulation_runner expectation: {circuit_instance_name}.log
        # Netlist is typically "{circuit_instance_name}_circuit.cir"; "_circuit" is 8 chars
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        circuit_instance_name = (
            base_name[:-8] if base_name.endswith("_circuit") else base_name
        )
        log_file_name = f"{circuit_instance_name}.log"
        single_log_file = (sim_dir / log_file_name).resolve()

        # build command (use absolute paths and quoted paths so redirect works regardless of cwd)
        sim_dir_s = str(sim_dir)
        single_log_s = str(single_log_file)
        batch_log_s = str(batch_log_path) if batch_log_path else None
        if batch_log_path:
            # If batch log is provided, immediately append ngspice output to batch log
            command = (
                f"cd '{sim_dir_s}' && "
                f"echo '\n--- Simulation {simulation_id} Started at {timestamp} ---' > '{single_log_s}' && "
                f"echo 'Total Simulations: {total_simulations}' >> '{single_log_s}' && "
                f"echo '-------------------------------------------' >> '{single_log_s}' && "
                f"echo '\n--- Simulation {simulation_id} NGSpice Output ---' >> '{batch_log_s}' && "
                f"echo 'Started at: {timestamp}' >> '{batch_log_s}' && "
                f"echo 'Netlist: {netlist_file.name}' >> '{batch_log_s}' && "
                f"echo '-------------------------------------------' >> '{batch_log_s}' && "
                f"ngspice -b {netlist_file.name} 2>&1 | tee -a '{single_log_s}' | tee -a '{batch_log_s}' && "
                f"echo '\n--- End of Simulation {simulation_id} NGSpice Output ---\n' >> '{batch_log_s}'"
            )
        else:
            # Original single simulation command
            command = (
                f"cd '{sim_dir_s}' && "
                f"echo '\n\n--- New Simulation Started at {timestamp} ---' > '{single_log_s}' && "
                f"echo 'Simulation ID: {simulation_id}' >> '{single_log_s}' && "
                f"echo 'Total Simulations: {total_simulations}' >> '{single_log_s}' && "
                f"echo '-------------------------------------------\n' >> '{single_log_s}' && "
                f"ngspice -b {netlist_file.name} >> '{single_log_s}' 2>&1"
            )

        # execute command
        print(f"[⚡] Running simulation: {netlist_file.name}")
        t0 = time.time()
        os.system(command)
        t1 = time.time()
        print(f"Time taken: {t1 - t0} seconds")
        print(f"[✓] Simulation completed: {single_log_file} (exists: {single_log_file.exists()})")

        # check if simulation is successful with valid specs
        is_valid_simulation = check_spice_log(single_log_file)

        return is_valid_simulation
