import toml
from pathlib import Path

def load_toml(path: Path):
    try:
        with open(path, 'r') as f:
            return toml.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except Exception as e:
        raise Exception(f"Error loading {path}: {e}")
