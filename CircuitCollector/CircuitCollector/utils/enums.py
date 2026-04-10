from enum import Enum


class SimulationStrategy(Enum):
    """Simulation strategy enumeration"""

    SINGLE_CONFIG = "single_config"
    GENERATE_AND_SIMULATE = "generate_and_simulate"
    READ_AND_SIMULATE = "read_and_simulate"


class ParameterType(Enum):
    """Parameter type enumeration"""

    MULTIPLIER = "M"  # _M parameters
    LENGTH = "L"  # _L parameters
    WIDTH = "W"  # _W parameters
    IBIAS = "ibias"  # ibias parameters


class SimulationStatus(Enum):
    """Simulation status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfigSection(Enum):
    """Configuration file section enumeration"""

    TECH = "tech"
    TYPE = "type"
    CIRCUIT = "circuit"
    TESTBENCH = "testbench"
    PARAMS = "params"
    PARAMS_RANGE = "params_range"
    PARAMS_FILE = "params_file"
