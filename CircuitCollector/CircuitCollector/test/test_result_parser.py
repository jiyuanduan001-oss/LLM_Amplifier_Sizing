from CircuitCollector.runner.result_parser import parse_opamp_simulation_results
from CircuitCollector.utils.path import PROJECT_ROOT


def test_result_parser():
    results_dir = PROJECT_ROOT / "temp/"
    results = parse_opamp_simulation_results(
        dc_file=results_dir / "5tota_DC.txt",
        ac_file=results_dir / "5tota_AC.txt",
        gbw_pm_file=results_dir / "5tota_GBW_PM.txt",
        log_file=results_dir / "test_opamp.log",
    )
    print(results if results else "No results, error occurred")
