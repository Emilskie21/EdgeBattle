from enum import Enum, auto

from shadow_boxing.paths import repo_root

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 540
FPS = 60

MAX_HP = 3

# Single-arrow dodge: show one direction at a time (ms)
ARROW_DISPLAY_MS = 1500
PUNCH_FLASH_MS = 750

# Score per arrow interval survived without matching the prompt
SCORE_PER_DODGE_TICK = 25

# Layout: arrow above first-person sprite zone (ratios of screen height, top-down)
ARROW_CENTER_Y_RATIO = 0.28
FP_SPRITE_MAX_HEIGHT_RATIO = 0.38
FP_SPRITE_BOTTOM_PAD = 12

SAVE_FILE = str(repo_root() / "data" / "save_data.json")


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
