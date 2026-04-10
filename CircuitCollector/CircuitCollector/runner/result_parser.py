from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging

import numpy as np

from CircuitCollector.utils.log_checker import check_spice_log

logger = logging.getLogger(__name__)


class SimulationResultParser:
    """Simulation result parser for collecting SPICE simulation data"""

    def parse_measurement_file(self, file_path: Union[str, Path]) -> Dict[str, float]:
        """
        Parse a measurement file and extract parameter values

        Args:
            file_path: Path to the measurement file

        Returns:
            Dict[str, float]: Dictionary of parameter names and values
        """
        file_path = Path(file_path)
        results = {}

        if not file_path.exists():
            logger.warning(f"Measurement file does not exist: {file_path}")
            return results

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return results

        # Parse lines with format: parameter_name = value
        for line in content.strip().split("\n"):
            line = line.strip()
            if "=" in line:
                try:
                    param_name, value_str = line.split("=", 1)
                    param_name = param_name.strip()
                    value_str = value_str.strip()

                    # Convert scientific notation to float
                    value = float(value_str)
                    results[param_name] = value

                except (ValueError, IndexError) as e:
                    logger.warning(f"Could not parse line '{line}': {e}")
                    continue

        return results

    def collect_opamp_results(
        self,
        dc_file: Union[str, Path],
        ac_file: Union[str, Path],
        gbw_pm_file: Union[str, Path],
        op_region_file: Union[str, Path] = None,
        noise_file: Union[str, Path] = None,
        slew_rate_file: Union[str, Path] = None,
        output_swing_file: Union[str, Path] = None,
    ) -> Dict[str, float]:
        """
        Collect OpAmp simulation results from multiple files

        Args:
            dc_file: Path to DC measurement file
            ac_file: Path to AC measurement file
            gbw_pm_file: Path to GBW/PM measurement file
            op_region_file: Path to OP region measurement file
            noise_file: Path to noise measurement file
            slew_rate_file: Path to slew rate measurement file
            output_swing_file: Path to output swing measurement file

        Returns:
            Dict[str, float]: All simulation results in one dictionary
        """
        results = {}

        # Parse and merge all measurement files
        dc_results = self.parse_measurement_file(dc_file)
        ac_results = self.parse_measurement_file(ac_file)
        freq_results = self.parse_measurement_file(gbw_pm_file)
        op_region_results = self.parse_measurement_file(op_region_file)
        noise_results = self.parse_measurement_file(noise_file) if noise_file else {}
        slew_rate_results = self.parse_measurement_file(slew_rate_file) if slew_rate_file else {}
        output_swing_results = self.parse_measurement_file(output_swing_file) if output_swing_file else {}
        # Combine all results into one dictionary
        results.update(dc_results)
        results.update(ac_results)
        results.update(freq_results)
        results.update(op_region_results)
        results.update(noise_results)
        results.update(slew_rate_results)
        results.update(output_swing_results)
        return results


# Convenience functions
def parse_opamp_simulation_results(
    dc_file: Union[str, Path],
    ac_file: Union[str, Path],
    gbw_pm_file: Union[str, Path],
    log_file: Union[str, Path],
    op_region_file: Union[str, Path] = None,
    noise_file: Union[str, Path] = None,
    slew_rate_file: Union[str, Path] = None,
    output_swing_file: Union[str, Path] = None,
) -> Dict[str, float]:
    """
    Convenience function to parse OpAmp simulation results

    Args:
        dc_file: Path to DC measurement file
        ac_file: Path to AC measurement file
        gbw_pm_file: Path to GBW/PM measurement file
        op_region_file: Path to OP region measurement file
        noise_file: Path to noise measurement file
        slew_rate_file: Path to slew rate measurement file
        output_swing_file: Path to output swing measurement file
    Returns:
        Dict[str, float]: All simulation results
    """
    parser = SimulationResultParser()
    is_valid = check_spice_log(log_file)
    if is_valid:
        return parser.collect_opamp_results(
            dc_file, ac_file, gbw_pm_file, op_region_file,
            noise_file, slew_rate_file, output_swing_file,
        )
    else:
        print(
            "Log is invalid, please check the log file, current parameters will not generate valid results"
        )
        return {}


def parse_measurement_file(file_path: Union[str, Path]) -> Dict[str, float]:
    """
    Convenience function to parse a single measurement file

    Args:
        file_path: Path to measurement file

    Returns:
        Dict[str, float]: Parameter values
    """
    parser = SimulationResultParser()
    return parser.parse_measurement_file(file_path)


def parse_mosfet_lut(
    lut_file: Union[str, Path],
) -> Tuple[np.ndarray, List[str]]:
    """
    Parse the wrdata output from a MOSFET LUT DC sweep.

    ngspice writes (with wr_singlescale + wr_vecnames):
        header row: col0  col1  col2          (e.g. "v(gate) v(drain) id")
        data rows:  float float float ...

    Without wr_vecnames the first row is numeric data. Without wr_singlescale
    the first numeric column is the inner-sweep scale (VDRAIN value), which
    duplicates v(drain)/v(gate) but is harmless — we detect and drop it.

    Returns:
        data    : np.ndarray of shape (N_points, N_cols)
        columns : list of column name strings
    """
    lut_file = Path(lut_file)
    lines = [ln.strip() for ln in lut_file.read_text().splitlines() if ln.strip()]

    columns: List[str] = []
    rows: List[List[float]] = []
    data_started = False

    for line in lines:
        tokens = line.split()
        if not tokens:
            continue

        # Try to parse as a row of floats
        try:
            float_row = [float(t) for t in tokens]
            data_started = True
            rows.append(float_row)
        except ValueError:
            if not data_started:
                # Header line with variable names
                columns = tokens
            # else: non-numeric line after data started → skip (e.g. repeated header)

    if not rows:
        logger.warning(f"No numeric data found in LUT file: {lut_file}")
        return np.empty((0, 0)), columns

    data = np.array(rows)

    # If ngspice prepended a sweep-index column (integer 0,1,2,...) drop it.
    # Heuristic: first column values are consecutive integers starting at 0.
    if data.shape[1] > len(columns) and len(columns) > 0:
        idx_col = data[:, 0]
        expected = np.arange(len(idx_col), dtype=float)
        if np.allclose(idx_col, expected, atol=0.5):
            data = data[:, 1:]

    # If no header was found, generate default names based on data width
    if not columns:
        n = data.shape[1]
        if n == 3:
            columns = ["col0", "col1", "col2"]
        else:
            columns = [f"col{i}" for i in range(n)]

    return data, columns
