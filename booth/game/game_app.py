import random
from typing import Any

import pygame

from combat.combat_system import CombatSystem
from combat.player_stats import PlayerStats
from data.save_system import SaveSystem
from game.arrow_sequence_system import ArrowSequenceSystem
from game.constants import FPS, GameState, SCREEN_HEIGHT, SCREEN_WIDTH, TurnState
from game.difficulty_system import DifficultySystem
from game.state_machine import StateMachine
from game.turn_system import TurnSystem
from tracking.movement_detector import MovementDetector
from tracking.pose_tracker import PoseTracker
from ui.renderer import UIRenderer


class ShadowBoxingGame:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Shadow Boxing 16-Bit")
        self.clock = pygame.time.Clock()
        self.running = True

        self.state_machine = StateMachine()
        self.save_system = SaveSystem()
        self.save_data = self.save_system.load()

        self.stats = PlayerStats(high_score=int(self.save_data.get("high_score", 0)))
        self.combat = CombatSystem()
        self.turn_system = TurnSystem()
        self.sequence_system = ArrowSequenceSystem()
        self.difficulty = DifficultySystem()
        self.pose_tracker = PoseTracker()
        self.movement_detector = MovementDetector()
        self.ui = UIRenderer(self.screen)

        self.show_debug = bool(self.save_data.get("show_debug", False))
        self.player_turn_time_remaining = 0.0
        self.enemy_will_hit = False
        self.last_detected_direction = "NONE"
        self.last_sequence_state = "IDLE"

    def run(self) -> None:
        while self.running:
            dt_seconds = self.clock.tick(FPS) / 1000.0
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
            elif self.state_machine.state == GameState.GAME_OVER:
                self._handle_game_over_input(key_name)
            elif self.state_machine.state == GameState.PLAYING:
                self._handle_playing_input(key_name)

    def _handle_menu_input(self, key_name: str) -> None:
        if key_name == "return":
            self._start_new_game()
            return
        if key_name == "o":
            self.state_machine.transition_to(GameState.OPTIONS)

    def _handle_options_input(self, key_name: str) -> None:
        if key_name == "d":
            self.show_debug = not self.show_debug
            return
        if key_name == "m":
            self.state_machine.transition_to(GameState.MENU)

    def _handle_game_over_input(self, key_name: str) -> None:
        if key_name == "return":
            self._start_new_game()
            return
        if key_name == "m":
            self.state_machine.transition_to(GameState.MENU)

    def _handle_playing_input(self, key_name: str) -> None:
        # During gameplay, player input comes from head pose direction detection.
        # Keyboard arrows are intentionally ignored.
        if self.turn_system.current_turn != TurnState.PLAYER_TURN:
            return
        if key_name in {"up", "down", "left", "right"}:
            return

    def _update(self, dt_seconds: float) -> None:
        if self.state_machine.state != GameState.PLAYING:
            return

        pose_result = self.pose_tracker.update()
        if not pose_result.camera_ok:
            # Camera failure pauses action progression.
            return

        if self.turn_system.current_turn == TurnState.PLAYER_TURN:
            # Convert head pose direction into sequence input.
            if pose_result.direction is not None:
                self.last_detected_direction = pose_result.direction.name
                outcome = self.sequence_system.validate_next_input(pose_result.direction)
                if outcome is False:
                    self.combat.on_player_sequence_fail(self.stats)
                    self.last_sequence_state = "FAIL"
                    self._on_turn_end()
                elif outcome is True:
                    self.combat.on_player_sequence_success(self.stats)
                    self.last_sequence_state = "SUCCESS"
                    self._on_turn_end()
                else:
                    self.last_sequence_state = "PROGRESS"

        if self.turn_system.current_turn == TurnState.PLAYER_TURN:
            self.player_turn_time_remaining -= dt_seconds
            if self.player_turn_time_remaining <= 0:
                self.combat.on_player_sequence_fail(self.stats)
                self.last_sequence_state = "TIMEOUT"
                self._on_turn_end()
        else:
            enemy_phase = self.turn_system.update_enemy_phase(dt_seconds)
            if enemy_phase.resolved:
                if self.enemy_will_hit:
                    self.combat.on_enemy_hit(self.stats)
                else:
                    self.combat.on_enemy_dodged(self.stats)
                self.turn_system.set_player_turn()
                self._start_player_turn()

        if self.stats.hp <= 0:
            self._to_game_over()

    def _start_new_game(self) -> None:
        if not self.state_machine.transition_to(GameState.PLAYING):
            self.state_machine.state = GameState.PLAYING
        self.stats.hp = 5
        self.stats.score = 0
        self.turn_system.set_player_turn()
        self._start_player_turn()

    def _start_player_turn(self) -> None:
        self.sequence_system.generate()
        self.player_turn_time_remaining = self.difficulty.get_player_turn_time(self.stats.score)
        self.last_sequence_state = "NEW_SEQUENCE"

    def _on_turn_end(self) -> None:
        if self.stats.hp <= 0:
            self._to_game_over()
            return

        self.turn_system.set_enemy_turn()
        enemy_len = random.randint(2, 4)
        self.sequence_system.start_enemy_sequence(length=enemy_len)
        self.enemy_will_hit = random.random() < 0.65

    def _to_game_over(self) -> None:
        self.stats.high_score = max(self.stats.high_score, self.stats.score)
        self.state_machine.transition_to(GameState.GAME_OVER)

    def _render(self) -> None:
        high_score = max(self.stats.high_score, self.stats.score)
        debug_lines = [
            f"FPS: {int(self.clock.get_fps())}",
            f"TURN: {self.turn_system.current_turn.name}",
            f"DIR: {self.last_detected_direction}",
            f"SEQ: {self.last_sequence_state}",
        ]
        self.ui.draw_frame(
            game_state=self.state_machine.state,
            stats=self.stats,
            high_score=high_score,
            sequence=self.sequence_system.sequence,
            input_index=self.sequence_system.input_index,
            turn_state=self.turn_system.current_turn,
            enemy_phase=self.turn_system.enemy_phase,
            player_time_left=self.player_turn_time_remaining,
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
            "turn": self.turn_system.current_turn.name,
            "hp": self.stats.hp,
            "score": self.stats.score,
        }
