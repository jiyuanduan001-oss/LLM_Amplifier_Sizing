# CircuitCollector/test/test_simulation_runner.py
from pathlib import Path
from CircuitCollector.runner.result_store import ResultStore
from CircuitCollector.runner.simulation_runner import SimulationRunner
from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector.utils.toml import load_toml

# Setup paths
base_config_path = PROJECT_ROOT / "config/skywater/opamp/tsm.toml"
config = load_toml(base_config_path)
base_config = load_toml(base_config_path)
circuit_type = base_config["type"]["name"]
circuit_name = base_config[f"{circuit_type}"]["name"]
output_dir = PROJECT_ROOT / f"output/{circuit_type}/{circuit_name}"


def test_single_config_strategy():
    """
    Test Strategy 1: Single config from circuit.params
    use_params_file = false
    """
    print("=== Testing Single Config Strategy ===\n")

    try:
        # Modify config to use single config strategy
        import toml

        with open(base_config_path, "r") as f:
            config = toml.load(f)

        # Temporarily modify config for testing
        config["circuit"]["params_file"]["use_params_file"] = False

        # Save temporary config
        temp_config_path = output_dir / "test_single_config.toml"
        temp_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config_path, "w") as f:
            toml.dump(config, f)

        # Run simulation
        runner = SimulationRunner(temp_config_path, output_dir)
        results = runner.run_simulations()

        # Verify results
        print(f"Results: {len(results)} spec(s)")
        for spec, val in results.items():
            print(f"{spec}: {val}")

        print("✓ Single config strategy test completed\n")
        return results

    except Exception as e:
        print(f"✗ Single config strategy test failed: {e}")
        import traceback

        traceback.print_exc()
        return []


def test_generate_and_simulate_strategy():
    """
    Test Strategy 2: Generate CSV and simulate
    use_params_file = true, generate_params_file = true
    """
    print("=== Testing Generate and Simulate Strategy ===\n")

    try:
        import toml

        # Modify config to use generate and simulate strategy
        # Set strategy parameters
        config["circuit"]["params_file"]["use_params_file"] = True
        config["circuit"]["params_file"]["generate_params_file"] = True
        config["circuit"]["params_file"][
            "generate_num_params"
        ] = 2  # Small number for testing

        # Save temporary config
        temp_config_path = output_dir / "test_generate_config.toml"
        temp_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config_path, "w") as f:
            toml.dump(config, f)

        # Run simulation
        runner = SimulationRunner(temp_config_path, output_dir)
        results = runner.run_simulations()

        # Verify results
        print(f"Results: {len(results)} simulation(s)")
        for result in results:
            print(f"  - Simulation ID: {result['simulation_id']}")
            print(f"  - Status: {result['status']}")
            print(f"  - Row: {result.get('row', 'N/A')}")
            print(f"  - Parameters: {result['params']}")
            if result["status"] == "completed":
                print(f"  - Circuit path: {result['circuit_path']}")
                print(f"  - Subcircuit path: {result['subcircuit_path']}")
            print()

        print("✓ Generate and simulate strategy test completed\n")
        return results

    except Exception as e:
        print(f"✗ Generate and simulate strategy test failed: {e}")
        import traceback

        traceback.print_exc()
        return []


def test_both_strategies():
    """
    Test both simulation strategies
    """
    print("=== Testing Simulation Strategies ===\n")

    all_results = {}

    # Test Strategy 1: Single Config
    all_results["single_config"] = test_single_config_strategy()

    # Test Strategy 2: Generate and Simulate
    all_results["generate_and_simulate"] = test_generate_and_simulate_strategy()

    # Summary
    print("=== Test Summary ===")
    for strategy, results in all_results.items():
        if isinstance(results, list):
            successful = len([r for r in results if r.get("status") == "completed"])
            failed = len([r for r in results if r.get("status") == "failed"])
            print(f"{strategy}:")
            print(f"  Total: {len(results)}")
            print(f"  Successful: {successful}")
            print(f"  Failed: {failed}")
            if strategy == "generate_and_simulate":
                store = ResultStore(output_dir)
                store.save_batch_results_csv(results)
        elif isinstance(results, dict):
            print(f"{strategy}:")
            print(f"  Specs: {len(results)}")

    return all_results


def test_API_mode():
    """
    Test API mode, which belongs to Single Config Strategy
    In the config file, API_mode=true to set this mode
    If no this config, default it false for API_mode
    """
    print("=== Testing API Mode ===\n")
    
    try:
        # Modify config to use single config strategy
        import toml

        with open(base_config_path, "r") as f:
            config = toml.load(f)

        # Temporarily modify config for testing
        config["circuit"]["params_file"]["use_params_file"] = False
        config["circuit"]["params_file"]["API_mode"] = True

        # Save temporary config
        temp_config_path = output_dir / "test_API_mode.toml"
        temp_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_config_path, "w") as f:
            toml.dump(config, f)

        # Run simulation
        runner = SimulationRunner(temp_config_path, output_dir)
        results = runner.run_simulations()

        # Verify results
        print(f"Results: {len(results)} spec(s)")
        for spec, val in results.items():
            print(f"{spec}: {val}")

        print("✓ Single config strategy test completed\n")
        return results

    except Exception as e:
        print(f"✗ Single config strategy test failed: {e}")
        import traceback

        traceback.print_exc()
        return []


if __name__ == "__main__":
    # Run individual tests
    test_single_config_strategy()
    # test_generate_and_simulate_strategy()

    # Or run both tests
    # test_both_strategies()
