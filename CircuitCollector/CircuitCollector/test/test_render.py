from CircuitCollector.utils.path import PROJECT_ROOT
from CircuitCollector import TestbenchRenderer, CircuitParamsRenderer, CircuitOpRegionRenderer


def test_opamp_render():
    config = PROJECT_ROOT / "config/skywater/opamp/5tota.toml"
    output = PROJECT_ROOT / "temp/test_opamp.cir"
    renderer = TestbenchRenderer(config, output)
    renderer.run()


def test_circuit_params_render():
    config = PROJECT_ROOT / "config/skywater/opamp/5tota.toml"
    output = PROJECT_ROOT / "temp/test_opamp_params.txt"
    renderer = CircuitParamsRenderer(config, output)
    renderer.run()
    
def test_circuit_op_region_render():
    config = PROJECT_ROOT / "config/skywater/opamp/tsm.toml"
    output = PROJECT_ROOT / "temp/tsm_op_region.spice"
    renderer = CircuitOpRegionRenderer(config, output)
    renderer.run()