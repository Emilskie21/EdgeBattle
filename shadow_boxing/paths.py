from pathlib import Path


def repo_root() -> Path:
    """Parent directory of the `shadow_boxing` package (project root)."""
    return Path(__file__).resolve().parent.parent
