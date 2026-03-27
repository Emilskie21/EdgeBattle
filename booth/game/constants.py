from enum import Enum, auto


SCREEN_WIDTH = 960
SCREEN_HEIGHT = 540
FPS = 60

MAX_HP = 5
MIN_SEQUENCE_LENGTH = 2
MAX_SEQUENCE_LENGTH = 8
BASE_TURN_TIME_SECONDS = 4.0
MIN_TURN_TIME_SECONDS = 1.2
DIFFICULTY_SCORE_STEP = 2500
TURN_TIME_REDUCTION_PER_STEP = 0.18

ENEMY_TELEGRAPH_SECONDS = 0.5
ENEMY_ACTION_SECONDS = 0.6

SAVE_FILE = "data/save_data.json"


class GameState(Enum):
    MENU = auto()
    OPTIONS = auto()
    PLAYING = auto()
    GAME_OVER = auto()


class TurnState(Enum):
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()


class Direction(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
