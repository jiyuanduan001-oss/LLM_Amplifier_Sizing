from CircuitCollector.utils.log_checker import check_spice_log
from CircuitCollector.utils.path import PROJECT_ROOT


def test_log_checker():
    log_path = PROJECT_ROOT / "temp/test_opamp.log"
    is_valid = check_spice_log(log_path)
    print(f"Log is valid: {is_valid}")