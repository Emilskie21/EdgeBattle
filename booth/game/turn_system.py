from dataclasses import dataclass

from game.constants import ENEMY_ACTION_SECONDS, ENEMY_TELEGRAPH_SECONDS, TurnState


@dataclass
class EnemyPhase:
    telegraph_time_remaining: float = ENEMY_TELEGRAPH_SECONDS
    action_time_remaining: float = ENEMY_ACTION_SECONDS
    telegraph_visible: bool = True
    resolved: bool = False


class TurnSystem:
    def __init__(self) -> None:
        self.current_turn = TurnState.PLAYER_TURN
        self.enemy_phase = EnemyPhase()

    def set_player_turn(self) -> None:
        self.current_turn = TurnState.PLAYER_TURN
        self.enemy_phase = EnemyPhase()

    def set_enemy_turn(self) -> None:
        self.current_turn = TurnState.ENEMY_TURN
        self.enemy_phase = EnemyPhase()

    def update_enemy_phase(self, dt_seconds: float) -> EnemyPhase:
        if self.current_turn != TurnState.ENEMY_TURN:
            return self.enemy_phase

        if self.enemy_phase.telegraph_time_remaining > 0:
            self.enemy_phase.telegraph_time_remaining -= dt_seconds
            self.enemy_phase.telegraph_visible = self.enemy_phase.telegraph_time_remaining > 0
            return self.enemy_phase

        if self.enemy_phase.action_time_remaining > 0:
            self.enemy_phase.action_time_remaining -= dt_seconds
            return self.enemy_phase

        self.enemy_phase.resolved = True
        return self.enemy_phase
