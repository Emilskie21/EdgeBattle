import json
from pathlib import Path
from typing import Any

from game.constants import SAVE_FILE


DEFAULT_SAVE = {"high_score": 0, "show_debug": False}


class SaveSystem:
    def __init__(self, save_path: str = SAVE_FILE) -> None:
        self.save_path = Path(save_path)

    def load(self) -> dict[str, Any]:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.save_path.exists():
            return DEFAULT_SAVE.copy()

        try:
            with self.save_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            if not isinstance(data, dict):
                return DEFAULT_SAVE.copy()
            merged = DEFAULT_SAVE.copy()
            merged.update(data)
            return merged
        except (OSError, json.JSONDecodeError):
            return DEFAULT_SAVE.copy()

    def save(self, data: dict[str, Any]) -> None:
        payload = DEFAULT_SAVE.copy()
        payload.update(data)
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.save_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
        except OSError:
            # Fails silently by design so gameplay is unaffected.
            return
