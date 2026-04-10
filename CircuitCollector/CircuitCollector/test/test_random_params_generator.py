from pathlib import Path
from CircuitCollector import RandomParamsGenerator
from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector.utils.toml import load_toml


def test_random_params_generator():
    """
    Test CSV template generation from existing config file
    """
    print("=== Testing CSV Template Generation ===\n")

    # Setup paths
    base_config_path = PROJECT_ROOT / "config/skywater/opamp/tsm.toml"
    base_config = load_toml(base_config_path)
    circuit_type = base_config["type"]["name"]
    circuit_name = base_config[f"{circuit_type}"]["name"]
    test_output_dir = PROJECT_ROOT / f"output/{circuit_type}/{circuit_name}"

    try:
        # Initialize generator
        print("1. Initializing RandomParamsGenerator...")
        generator = RandomParamsGenerator(base_config_path)
        print("✓ Generator initialized successfully\n")

        # Test default CSV template generation
        print("2. Testing generate_csv_template with default path...")
        try:
            csv_path = generator.generate_csv_template()
            print(f"   Generated CSV template at: {csv_path}")
            print(f"   File exists: {csv_path.exists()}")

            # Read and display the generated CSV content
            if csv_path.exists():
                with open(csv_path, "r") as f:
                    content = f.read()
                    print(f"   CSV content:\n{content}")
        except Exception as e:
            print(f"   ✗ Failed to generate default CSV template: {e}")
        print("✓ Default CSV template generation test completed\n")

        # Test custom output path
        print("3. Testing generate_csv_template with custom path...")
        try:
            custom_csv_path = test_output_dir / "custom_params.csv"
            csv_path = generator.generate_csv_template(custom_csv_path)
            print(f"   Generated CSV template at: {csv_path}")
            print(f"   File exists: {csv_path.exists()}")

            # Read and display the generated CSV content
            if csv_path.exists():
                with open(csv_path, "r") as f:
                    content = f.read()
                    print(f"   CSV content:\n{content}")
        except Exception as e:
            print(f"   ✗ Failed to generate custom CSV template: {e}")
        print("✓ Custom CSV template generation test completed\n")

        # Test reading config parameters
        print("4. Testing parameter extraction from config...")
        try:
            circuit_params_range = generator.base_config.get("circuit", {}).get(
                "params_range", {}
            )
            print(f"   Found {len(circuit_params_range)} parameter ranges in config:")
            for param_range_name, range_values in circuit_params_range.items():
                param_name = param_range_name.replace("_range", "")
                print(f"     - {param_name}: {range_values}")
        except Exception as e:
            print(f"   ✗ Failed to extract parameters: {e}")
        print("✓ Parameter extraction test completed\n")

        # Test config file validation
        print("5. Testing config file validation...")
        try:
            # Check if required sections exist
            required_sections = ["circuit", "type"]
            for section in required_sections:
                if section in generator.base_config:
                    print(f"   ✓ Found required section: {section}")
                else:
                    print(f"   ✗ Missing required section: {section}")

            # Check circuit type and netlist name
            circuit_type = generator.base_config.get("type", {}).get("name")
            if circuit_type:
                netlist_name = generator.base_config.get(circuit_type, {}).get("name")
                print(f"   Circuit type: {circuit_type}")
                print(f"   Netlist name: {netlist_name}")
                print(f"   Circuit path: {generator.circuit_instance_path}")
                print(
                    f"   Circuit path exists: {generator.circuit_instance_path.exists()}"
                )

        except Exception as e:
            print(f"   ✗ Config validation failed: {e}")
        print("✓ Config validation test completed\n")

        print("=== All CSV template generation tests completed! ===")

    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
