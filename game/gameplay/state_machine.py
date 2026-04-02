from dataclasses import dataclass

from game.constants import GameState


VALID_TRANSITIONS = {
    GameState.MENU: {GameState.COUNTDOWN, GameState.OPTIONS},
    GameState.OPTIONS: {GameState.MENU},
    GameState.COUNTDOWN: {GameState.PLAYING, GameState.MENU},
    GameState.PLAYING: {GameState.GAME_OVER, GameState.MENU},
    GameState.GAME_OVER: {GameState.MENU, GameState.PLAYING},
    GameState.INSTRUCTIONS: {GameState.MENU, GameState.COUNTDOWN}
}


@dataclass
class StateMachine:
    state: GameState = GameState.INSTRUCTIONS

    def transition_to(self, next_state: GameState) -> bool:
        if next_state in VALID_TRANSITIONS.get(self.state, set()):
            self.state = next_state
            return True
        return False
