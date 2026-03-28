"""Load ``assets/assets.json`` (explicit paths only — no guessed filenames)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shadow_boxing.paths import repo_root


def manifest_path() -> Path:
    return repo_root() / "assets" / "assets.json"


def load_manifest() -> dict[str, Any]:
    path = manifest_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_asset(relative: str) -> Path:
    return repo_root() / "assets" / relative.replace("\\", "/")
