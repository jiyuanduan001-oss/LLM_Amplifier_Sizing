from CircuitCollector.test.test_render import test_opamp_render, test_circuit_op_region_render
from CircuitCollector.test.test_simulator import test_simulator
from CircuitCollector.test.test_random_params_generator import (
    test_random_params_generator,
)
from CircuitCollector.test.test_log_checker import test_log_checker
from CircuitCollector.test.test_result_parser import test_result_parser
from CircuitCollector.utils.path import PROJECT_ROOT

if __name__ == "__main__":
    _test_netlist_render = False
    _test_simulator = False
    _test_log_checker = False
    _test_result_parser = False
    _test_random_params_generator = False
    _test_circuit_op_region_render = True

    if _test_netlist_render:
        # test_circuit_params_render()
        test_opamp_render()

    if _test_simulator:
        print(f"Simulation result is valid: {test_simulator()}")

    if _test_log_checker:
        test_log_checker()

    if _test_result_parser:
        test_result_parser()

    if _test_random_params_generator:
        test_random_params_generator()

    if _test_circuit_op_region_render:
        test_circuit_op_region_render()
