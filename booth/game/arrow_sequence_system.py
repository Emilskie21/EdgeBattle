import random

from game.constants import Direction, MAX_SEQUENCE_LENGTH, MIN_SEQUENCE_LENGTH


class ArrowSequenceSystem:
    def __init__(self) -> None:
        self.sequence: list[Direction] = []
        self.input_index = 0
        self.locked = False
        self.last_result_success: bool | None = None

    def generate(self) -> None:
        length = random.randint(MIN_SEQUENCE_LENGTH, MAX_SEQUENCE_LENGTH)
        self.sequence = [random.choice(list(Direction)) for _ in range(length)]
        self.input_index = 0
        self.locked = False
        self.last_result_success = None

    def start_enemy_sequence(self, length: int = 2) -> None:
        self.sequence = [random.choice(list(Direction)) for _ in range(length)]
        self.input_index = 0
        self.locked = True
        self.last_result_success = None

    def validate_next_input(self, direction: Direction) -> bool | None:
        if self.locked or not self.sequence:
            return None

        if self.input_index >= len(self.sequence):
            return True

        expected = self.sequence[self.input_index]
        if direction != expected:
            self.last_result_success = False
            return False

        self.input_index += 1
        if self.input_index >= len(self.sequence):
            self.last_result_success = True
            return True
        return None

    def reset(self) -> None:
        self.sequence = []
        self.input_index = 0
        self.locked = False
        self.last_result_success = None
