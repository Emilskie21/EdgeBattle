from game.constants import (
    BASE_TURN_TIME_SECONDS,
    DIFFICULTY_SCORE_STEP,
    MIN_TURN_TIME_SECONDS,
    TURN_TIME_REDUCTION_PER_STEP,
)


class DifficultySystem:
    def get_player_turn_time(self, score: int) -> float:
        level = score // DIFFICULTY_SCORE_STEP
        turn_time = BASE_TURN_TIME_SECONDS - (level * TURN_TIME_REDUCTION_PER_STEP)
        return max(MIN_TURN_TIME_SECONDS, turn_time)
