#!/usr/bin/env python3
"""
Circuit Simulation Command Line Tool
Automatically reads simulation strategy from config file
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from CircuitCollector.runner.simulation_runner import SimulationRunner
from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector.utils.toml import load_toml


def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Circuit Simulation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        # Run simulation based on config file strategy
        python simulate.py config/skywater/opamp/tsm.toml

        # Specify output directory
        python simulate.py config/skywater/opamp/tsm.toml --output results/my_simulation
        """,
    )

    parser.add_argument("config", type=str, help="Path to configuration file")
    parser.add_argument("--output", "-o", type=str, help="Output directory (optional)")
    parser.add_argument("--save_csv", "-s", action="store_true", help="Save results to CSV")

    return parser


def run_simulation(config_path: str, output_dir: str = None, save_csv: bool = True):
    """Run simulation based on config file"""

    config_path = Path(config_path)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return False

    # Load config to get circuit info
    config = load_toml(config_path)
    circuit_type = config["type"]["name"]
    circuit_name = config[f"{circuit_type}"]["name"]

    # Set output directory
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = PROJECT_ROOT / f"output/{circuit_type}/{circuit_name}"

    print("Circuit Collector - Simulation Tool")
    print("=" * 40)
    print(f"Config file: {config_path}")
    print(f"Output directory: {output_path}")
    print(f"Circuit: {circuit_type}/{circuit_name}")
    print("-" * 40)

    try:
        # Run simulation directly
        runner = SimulationRunner(config_path, output_path)
        results = runner.run_simulations()

        if not results:
            print("Error: Simulation failed - no results returned")
            return False

        # Handle results based on simulation type
        if isinstance(results, list):
            # Batch simulation results
            successful = len([r for r in results if r.get("status") == "completed"])
            failed = len([r for r in results if r.get("status") == "failed"])

            print(f"Batch simulations completed")
            print(f"Total: {len(results)}, Successful: {successful}, Failed: {failed}")

        else:
            # Single simulation result
            print(f"Single simulation completed successfully")
            print(f"Results: {results}")

        return True

    except Exception as e:
        print(f"Error: Simulation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main command line interface"""
    parser = create_parser()
    args = parser.parse_args()
    
    success = run_simulation(
        config_path=args.config, output_dir=args.output, save_csv=args.save_csv
    )

    if success:
        print("\nSimulation completed successfully!")
        sys.exit(0)
    else:
        print("\nSimulation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
