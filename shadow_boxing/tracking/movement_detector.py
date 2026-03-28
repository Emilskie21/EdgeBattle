from shadow_boxing.constants import Direction


KEY_TO_DIRECTION = {
    "up": Direction.UP,
    "down": Direction.DOWN,
    "left": Direction.LEFT,
    "right": Direction.RIGHT,
}


class MovementDetector:
    """
    Maps stable movement events to directions.
    For prototype, keyboard arrows emulate motion input.
    """

    def __init__(self) -> None:
        self._cooldown_frames = 0

    def update(self, key_event: str | None) -> Direction | None:
        if self._cooldown_frames > 0:
            self._cooldown_frames -= 1
            return None

        if not key_event:
            return None

        direction = KEY_TO_DIRECTION.get(key_event)
        if direction is None:
            return None

        # Cooldown suppresses noisy spam, but still allows legitimate repeats.
        self._cooldown_frames = 5
        return direction
