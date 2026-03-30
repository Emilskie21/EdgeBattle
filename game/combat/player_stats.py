from dataclasses import dataclass

from game.constants import MAX_HP


@dataclass
class PlayerStats:
    hp: int = MAX_HP
    score: int = 0
    high_score: int = 0
    combo_percent: int = 0

    def damage(self, amount: int = 1) -> None:
        self.hp = max(0, self.hp - amount)

    def heal(self, amount: int = 1) -> None:
        self.hp = min(MAX_HP, self.hp + amount)

    def add_score(self, amount: int) -> None:
        self.score = max(0, self.score + amount)
        self.high_score = max(self.high_score, self.score)

    def reset_combo(self) -> None:
        self.combo_percent = 0

    def bump_combo_on_correct_step(self) -> None:
        self.combo_percent = min(100, self.combo_percent + 12)
