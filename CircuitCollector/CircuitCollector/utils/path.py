from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# default pdk root
DEFAULT_PDK_ROOT = PROJECT_ROOT / "PDK"


def get_pdk_path(tech_name=None, config_pdk_path=None):
    """
    Get the absolute path of the PDK

    Args:
        tech_name: the name of the technology, e.g. 'skywater'
        config_pdk_path: the PDK path specified in the config file (if any)

    Returns:
        the absolute path of the PDK
    """
    # first check if the path is specified in the config file
    if config_pdk_path:
        path = Path(config_pdk_path)
        # if the path is relative, resolve it relative to PROJECT_ROOT
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    # otherwise use the default path
    if tech_name:
        return DEFAULT_PDK_ROOT / f"{tech_name}_pdk"
    else:
        return DEFAULT_PDK_ROOT


def resolve_path(path_str, base_path=None):
    """
    Resolve the path to an absolute path

    Args:
        path_str: the path string
        base_path: the base path, default is PROJECT_ROOT

    Returns:
        the resolved absolute path
    """
    if not base_path:
        base_path = PROJECT_ROOT

    path = Path(path_str)
    if not path.is_absolute():
        path = base_path / path

    return path
