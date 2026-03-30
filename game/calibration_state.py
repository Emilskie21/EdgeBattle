"""Whether head-pose calibration file exists and is marked valid."""

import json
from pathlib import Path

from game.paths import repo_root


def calibration_file() -> Path:
    return repo_root() / "data" / "head_pose_calibration.json"


def is_calibrated() -> bool:
    path = calibration_file()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("calibrated", False))
    except (json.JSONDecodeError, OSError, TypeError):
        return False
