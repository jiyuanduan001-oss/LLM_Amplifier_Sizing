from CircuitCollector.runner.simulator import Simulator
from CircuitCollector.utils.path import PROJECT_ROOT

def test_simulator():
    # create simulator instance
    simulator = Simulator()

    # # run simulation for directory
    # simulator.run(PROJECT_ROOT / "temp")

    # run simulation for file
    # simulator.run(PROJECT_ROOT / "temp/two_stages_op_amp_ACDC.cir")
    return simulator.run(PROJECT_ROOT / "temp/test_opamp.cir")

    # # run simulation for file with ID and total simulations
    # simulator.run(PROJECT_ROOT / "temp/test_opamp.cir", simulation_id="sim_1", total_simulations=10)