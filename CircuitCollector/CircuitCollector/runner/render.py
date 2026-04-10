from pathlib import Path
from .testbench_generator import (
    TestbenchGenerator,
    CircuitParamsGenerator,
    CircuitOpRegionGenerator,
)
from CircuitCollector.utils.path import PROJECT_ROOT


class TestbenchRenderer:
    def __init__(self, config_path: Path, output_path: Path = None):
        self.config_path = config_path
        self.output_path = output_path or PROJECT_ROOT / "temp/default.spice"

    def run(self):
        generator = TestbenchGenerator(self.config_path)
        generator.generate(output_path=self.output_path)


class CircuitParamsRenderer:
    def __init__(self, config_path: Path, output_path: Path = None):
        self.config_path = config_path
        self.output_path = output_path or PROJECT_ROOT / "temp/default.txt"

    def run(self):
        generator = CircuitParamsGenerator(self.config_path)
        generator.generate(output_path=self.output_path)

class CircuitOpRegionRenderer:
    def __init__(self, config_path: Path, output_path: Path = None):
        self.config_path = config_path
        self.output_path = output_path or PROJECT_ROOT / "temp/default_op_region.txt"

    def run(self):
        generator = CircuitOpRegionGenerator(self.config_path)
        generator.generate(output_path=self.output_path)
