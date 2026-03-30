import random
from typing import Any, Optional

import pygame

from game.calibration_state import is_calibrated
from game.combat.combat_system import CombatSystem
from game.combat.player_stats import PlayerStats
from game.constants import (
    ARROW_DISPLAY_MS,
    Direction,
    FPS,
    GameState,
    MAX_HP,
    PUNCH_FLASH_MS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SCORE_PER_DODGE_TICK,
)
from game.gameplay.state_machine import StateMachine
from game.persistence.save_system import SaveSystem
from game.persistence.leaderboard_db import LeaderboardDB, ScoreEntry, now_manila
from game.tracking.pose_tracker import PoseTracker
from game.ui.renderer import UIRenderer


class ShadowBoxingGame:
    def __init__(self) -> None:
        pygame.init()
        try:
            self.screen = pygame.display.set_mode(
                (SCREEN_WIDTH, SCREEN_HEIGHT),
                pygame.FULLSCREEN | pygame.SCALED,
            )
        except (TypeError, pygame.error):
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Shadow Boxing")
        self.clock = pygame.time.Clock()
        self.running = True
        self._last_dt_ms = 1000.0 / float(FPS)

        self.state_machine = StateMachine()
        # Start immediately with the countdown; no traditional menu UI.
        self.state_machine.state = GameState.COUNTDOWN
        self.save_system = SaveSystem()
        self.leaderboard_db = LeaderboardDB()
        self.save_data = self.save_system.load()

        self.stats = PlayerStats(high_score=int(self.save_data.get("high_score", 0)))
        self.combat = CombatSystem()
        self.pose_tracker = PoseTracker()
        self.ui = UIRenderer(self.screen)

        self.show_debug = bool(self.save_data.get("show_debug", False))
        self.last_detected_direction = "NONE"
        self.pose_pitch = 0.0
        self.pose_yaw = 0.0
        self.pose_visual_dir: Optional[Direction] = None

        self.current_arrow: Optional[Direction] = None
        self.arrow_start_ms: int = 0
        self.arrow_deadline_ms: int = 0
        self.punch_flash_until_ms: int = 0
        # True once player tilts head off neutral (forward) during current prompt
        self._dodge_head_moved: bool = False

        # Countdown before gameplay begins (seconds).
        self._countdown_start_ms: int = pygame.time.get_ticks()
        self._countdown_value: int = 3

        # Game-over UI state.
        self._game_over_since_ms: int = 0
        self._game_over_name_input: str = ""
        self._game_over_name_saved: bool = False

    def run(self) -> None:
        while self.running:
            dt_seconds = self.clock.tick(FPS) / 1000.0
            self._last_dt_ms = dt_seconds * 1000.0
            self._handle_events()
            self._update(dt_seconds)
            self._render()
        self._persist()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type != pygame.KEYDOWN:
                continue

            key_name = pygame.key.name(event.key)
            event_unicode = getattr(event, "unicode", "") or ""
            if key_name == "escape":
                if self.state_machine.state == GameState.MENU:
                    self.running = False
                else:
                    self.state_machine.transition_to(GameState.MENU)
                continue

            if self.state_machine.state == GameState.MENU:
                self._handle_menu_input(key_name)
            elif self.state_machine.state == GameState.OPTIONS:
                self._handle_options_input(key_name)
            elif self.state_machine.state == GameState.COUNTDOWN:
                self._handle_countdown_input(key_name, event_unicode)
            elif self.state_machine.state == GameState.GAME_OVER:
                self._handle_game_over_input(key_name, event_unicode)
            elif self.state_machine.state == GameState.PLAYING:
                self._handle_playing_input(key_name)

    def _handle_menu_input(self, key_name: str) -> None:
        if key_name == "c":
            self._run_calibration()
            return
        if key_name == "return":
            if not is_calibrated():
                return
            self._start_new_game()
            return
        if key_name == "o":
            self.state_machine.transition_to(GameState.OPTIONS)

    def _run_calibration(self) -> None:
        self._persist()
        pygame.display.quit()
        pygame.quit()
        try:
            from calibration.head_pose_app import run as cal_run

            cal_run()
        finally:
            pygame.init()
            try:
                self.screen = pygame.display.set_mode(
                    (SCREEN_WIDTH, SCREEN_HEIGHT),
                    pygame.FULLSCREEN | pygame.SCALED,
                )
            except (TypeError, pygame.error):
                self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            pygame.display.set_caption("Shadow Boxing")
            self.clock = pygame.time.Clock()
            self.ui = UIRenderer(self.screen)
            self.pose_tracker = PoseTracker()

    def _handle_options_input(self, key_name: str) -> None:
        if key_name == "d":
            self.show_debug = not self.show_debug
            return
        if key_name == "m":
            self.state_machine.transition_to(GameState.MENU)

    def _handle_countdown_input(self, key_name: str, _event_unicode: str) -> None:
        if key_name == "escape":
            self.state_machine.transition_to(GameState.MENU)
            return
        if key_name == "return":
            # Skip countdown.
            self._start_new_game()
            return

    def _handle_game_over_input(self, key_name: str, event_unicode: str) -> None:
        if key_name == "m":
            self.state_machine.transition_to(GameState.MENU)
            return
        if key_name == "escape":
            self.state_machine.transition_to(GameState.MENU)
            return

        if key_name == "backspace":
            self._game_over_name_input = self._game_over_name_input[:-1]
            self._game_over_name_saved = False
            return

        if key_name == "return":
            if self._game_over_name_saved:
                return
            name = self._game_over_name_input.strip()
            if not name:
                name = "Anonymous"
            entry = ScoreEntry(
                name=name,
                hp_remaining=self.stats.hp,
                score=self.stats.score,
                timestamp=now_manila(),
            )
            self.leaderboard_db.insert_score(entry)
            self._game_over_name_saved = True
            return

        # Normal character input.
        if event_unicode and len(event_unicode) == 1 and len(self._game_over_name_input) < 16:
            # Filter out control chars.
            if event_unicode.isprintable() and event_unicode not in ("\r", "\n", "\t"):
                self._game_over_name_input += event_unicode

    def _handle_playing_input(self, key_name: str) -> None:
        if key_name == "o":
            self.state_machine.transition_to(GameState.OPTIONS)

    def _spawn_arrow(self) -> None:
        now = pygame.time.get_ticks()
        self.current_arrow = random.choice(list(Direction))
        self.arrow_start_ms = now
        self.arrow_deadline_ms = now + ARROW_DISPLAY_MS
        self._dodge_head_moved = False

    def _update(self, dt_seconds: float) -> None:
        _ = dt_seconds
        state = self.state_machine.state
        now = pygame.time.get_ticks()

        if state == GameState.COUNTDOWN:
            elapsed = now - self._countdown_start_ms
            # 3..2..1..0 progression (1 second per step).
            self._countdown_value = max(0, 3 - int(elapsed / 1000))
            if elapsed >= 3000:
                self._start_new_game()
            return

        if state == GameState.MENU:
            # No menu UI: once calibrated, immediately begin countdown.
            if is_calibrated():
                self.state_machine.transition_to(GameState.COUNTDOWN)
                self._countdown_start_ms = now
                self._countdown_value = 3
            return

        if state != GameState.PLAYING:
            return

        if self.punch_flash_until_ms > now:
            return

        pose_result = self.pose_tracker.update()
        if not pose_result.camera_ok:
            self.pose_visual_dir = None
            return

        if pose_result.detection_ok:
            self.pose_pitch = pose_result.pitch
            self.pose_yaw = pose_result.yaw
            self.pose_visual_dir = pose_result.visual_direction
        else:
            self.pose_visual_dir = None

        if self.current_arrow is None:
            self._spawn_arrow()

        gated = pose_result.direction
        if gated is not None:
            self.last_detected_direction = gated.name

        # Any non-forward tilt counts as "trying to dodge" (anti-abuse: neutral whole window = fail).
        if (
            self.current_arrow is not None
            and pose_result.detection_ok
            and pose_result.visual_direction is not None
        ):
            self._dodge_head_moved = True

        if self.current_arrow is not None and gated is not None and gated == self.current_arrow:
            self.combat.on_matched_shown_arrow(self.stats)
            self.punch_flash_until_ms = now + PUNCH_FLASH_MS
            self.current_arrow = None
            if self.stats.hp <= 0:
                self._to_game_over()
            return

        if self.current_arrow is not None and now >= self.arrow_deadline_ms:
            if not self._dodge_head_moved:
                self.combat.on_matched_shown_arrow(self.stats)
                self.punch_flash_until_ms = now + PUNCH_FLASH_MS
                self.current_arrow = None
                if self.stats.hp <= 0:
                    self._to_game_over()
                return
            self.stats.add_score(SCORE_PER_DODGE_TICK)
            self._spawn_arrow()

        if self.stats.hp <= 0:
            self._to_game_over()

    def _start_new_game(self) -> None:
        if not is_calibrated():
            return
        if not self.state_machine.transition_to(GameState.PLAYING):
            self.state_machine.state = GameState.PLAYING
        self.stats.hp = MAX_HP
        self.stats.score = 0
        self.punch_flash_until_ms = 0
        self._game_over_since_ms = 0
        self._game_over_name_input = ""
        self._game_over_name_saved = False
        self.current_arrow = None
        self.arrow_start_ms = 0
        self.arrow_deadline_ms = 0
        self._spawn_arrow()

    def _to_game_over(self) -> None:
        self.stats.high_score = max(self.stats.high_score, self.stats.score)
        self.current_arrow = None
        self.arrow_start_ms = 0
        self.arrow_deadline_ms = 0
        self._game_over_since_ms = pygame.time.get_ticks()
        self._game_over_name_input = ""
        self._game_over_name_saved = False
        self.state_machine.transition_to(GameState.GAME_OVER)

    def _render(self) -> None:
        high_score = max(self.stats.high_score, self.stats.score)
        debug_lines = [
            f"FPS: {int(self.clock.get_fps())}",
            f"DIR: {self.last_detected_direction}",
            f"ARROW: {self.current_arrow.name if self.current_arrow else '-'}",
        ]
        self.ui.draw_frame(
            game_state=self.state_machine.state,
            stats=self.stats,
            high_score=high_score,
            current_arrow=self.current_arrow,
            arrow_start_ms=self.arrow_start_ms if self.current_arrow else 0,
            arrow_deadline_ms=self.arrow_deadline_ms if self.current_arrow else 0,
            punch_flash_until_ms=self.punch_flash_until_ms,
            dt_ms=self._last_dt_ms,
            calibrated=is_calibrated(),
            countdown_value=self._countdown_value if self.state_machine.state == GameState.COUNTDOWN else None,
            game_over_name_input=self._game_over_name_input,
            game_over_name_saved=self._game_over_name_saved,
            game_over_since_ms=self._game_over_since_ms,
            show_debug=self.show_debug,
            debug_lines=debug_lines,
        )

    def _persist(self) -> None:
        self.save_system.save(
            {
                "high_score": max(self.stats.high_score, self.stats.score),
                "show_debug": self.show_debug,
            }
        )

    def debug_state(self) -> dict[str, Any]:
        return {
            "state": self.state_machine.state.name,
            "hp": self.stats.hp,
            "score": self.stats.score,
        }
