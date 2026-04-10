import re
from pathlib import Path
from typing import List, Optional, Union


class LogChecker:
    """Log error checker for simulation logs"""

    def __init__(
        self, error_patterns: Optional[List[str]] = None, case_sensitive: bool = False
    ):
        """
        Initialize log checker

        Args:
            error_patterns: List of error patterns, defaults to ['error', 'fatal']
            case_sensitive: Whether to match case sensitively, defaults to False
        """
        self.error_patterns = error_patterns or ["error", "fatal"]
        self.case_sensitive = case_sensitive

        # Compile regex patterns
        flags = 0 if case_sensitive else re.IGNORECASE
        self.compiled_patterns = [
            re.compile(pattern, flags) for pattern in self.error_patterns
        ]

    def check_log(self, log_path: Union[str, Path]) -> bool:
        """
        Check if log file contains errors

        Args:
            log_path: Path to log file

        Returns:
            bool: True if no errors found, False if errors found
        """
        log_file = Path(log_path)

        if not log_file.exists():
            print(f"Warning: Log file does not exist: {log_file}")
            return True  # Consider non-existent file as no error

        try:
            # Try UTF-8 encoding first
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                # Try other encoding
                with open(log_file, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception as e:
                print(f"Error: Cannot read log file {log_file}: {e}")
                return True  # Consider read failure as no error

        # Check each line
        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern in self.compiled_patterns:
                if pattern.search(line):
                    print(f"Error found (line {line_num}): {line.strip()}")
                    return False

        return True

    def get_error_lines(self, log_path: Union[str, Path]) -> List[str]:
        """
        Get lines containing errors

        Args:
            log_path: Path to log file

        Returns:
            List[str]: List of lines containing errors
        """
        log_file = Path(log_path)
        error_lines = []

        if not log_file.exists():
            return error_lines

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(log_file, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception:
                return error_lines

        for line_num, line in enumerate(content.splitlines(), 1):
            for pattern in self.compiled_patterns:
                if pattern.search(line):
                    error_lines.append(f"Line {line_num}: {line.strip()}")
                    break

        return error_lines


# Convenience functions
def check_simulation_log(
    log_path: Union[str, Path], error_patterns: Optional[List[str]] = None
) -> bool:
    """
    Convenience function to check simulation log for errors

    Args:
        log_path: Path to log file
        error_patterns: List of error patterns, defaults to ['error', 'fatal']

    Returns:
        bool: True if no errors found, False if errors found
    """
    checker = LogChecker(error_patterns)
    return checker.check_log(log_path)


def check_spice_log(log_path: Union[str, Path]) -> bool:
    """
    Convenience function to check SPICE simulation log.

    Detects fatal simulation errors (convergence failures, singular matrices)
    while ignoring non-fatal ngspice measurement warnings (e.g. a .meas
    statement that fails because the waveform doesn't cross the threshold).

    Args:
        log_path: Path to log file

    Returns:
        bool: True if no fatal errors found, False if fatal errors found
    """
    # Patterns that indicate a truly fatal simulation failure
    fatal_patterns = [
        r"fatal",
        r"singular matrix",
        r"too many iterations without convergence",
        r"timestep too small",
        r"doAnalyses:.*abort",
        r"no dc convergence",
    ]
    checker = LogChecker(fatal_patterns)
    return checker.check_log(log_path)
