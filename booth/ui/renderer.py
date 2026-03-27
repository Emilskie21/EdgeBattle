import pygame

from combat.player_stats import PlayerStats
from game.constants import Direction, GameState, MAX_HP, SCREEN_HEIGHT, SCREEN_WIDTH, TurnState
from game.turn_system import EnemyPhase


class UIRenderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        pygame.font.init()
        self.pixel_font = pygame.font.SysFont("consolas", 28, bold=True)
        self.small_font = pygame.font.SysFont("consolas", 20)
        self.bg_color = (20, 18, 32)
        self.panel_color = (42, 36, 62)
        self.accent = (247, 199, 56)
        self.hp_good = (85, 224, 106)
        self.hp_bad = (224, 75, 75)
        self.white = (238, 238, 238)

    def draw_frame(
        self,
        game_state: GameState,
        stats: PlayerStats,
        high_score: int,
        sequence: list[Direction],
        input_index: int,
        turn_state: TurnState,
        enemy_phase: EnemyPhase,
        player_time_left: float,
        show_debug: bool,
        debug_lines: list[str],
    ) -> None:
        self.screen.fill(self.bg_color)
        if game_state == GameState.MENU:
            self._draw_menu()
        elif game_state == GameState.OPTIONS:
            self._draw_options(show_debug)
        elif game_state == GameState.PLAYING:
            self._draw_hud(stats, high_score)
            self._draw_enemy_sprite()
            self._draw_turn_box(turn_state, player_time_left)
            self._draw_sequence(sequence, input_index, turn_state, enemy_phase)
        elif game_state == GameState.GAME_OVER:
            self._draw_game_over(stats.score, high_score)

        if show_debug:
            self._draw_debug(debug_lines)

        pygame.display.flip()

    def _draw_text_center(self, text: str, y: int, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(SCREEN_WIDTH // 2, y))
        self.screen.blit(surface, rect)

    def _draw_menu(self) -> None:
        self._draw_text_center("SHADOW BOXING 16-BIT", 120, self.pixel_font, self.accent)
        self._draw_text_center("START  [ENTER]", 230, self.small_font, self.white)
        self._draw_text_center("OPTIONS  [O]", 270, self.small_font, self.white)
        self._draw_text_center("QUIT  [ESC]", 310, self.small_font, self.white)

    def _draw_options(self, show_debug: bool) -> None:
        self._draw_text_center("OPTIONS", 120, self.pixel_font, self.accent)
        status = "ON" if show_debug else "OFF"
        self._draw_text_center(f"DEBUG OVERLAY: {status} [D TO TOGGLE]", 230, self.small_font, self.white)
        self._draw_text_center("BACK TO MENU [M]", 300, self.small_font, self.white)

    def _draw_hud(self, stats: PlayerStats, high_score: int) -> None:
        pygame.draw.rect(self.screen, self.panel_color, (20, 20, 320, 54), border_radius=4)
        pygame.draw.rect(self.screen, self.panel_color, (SCREEN_WIDTH - 360, 20, 340, 54), border_radius=4)

        label = self.small_font.render("HP", True, self.white)
        self.screen.blit(label, (30, 36))
        bar_w = 220
        hp_ratio = stats.hp / MAX_HP
        hp_color = self.hp_good if hp_ratio > 0.35 else self.hp_bad
        pygame.draw.rect(self.screen, (65, 55, 90), (70, 34, bar_w, 20))
        pygame.draw.rect(self.screen, hp_color, (70, 34, int(bar_w * hp_ratio), 20))
        pygame.draw.rect(self.screen, self.white, (70, 34, bar_w, 20), width=2)

        score_surface = self.small_font.render(f"SCORE {stats.score:06d}", True, self.accent)
        self.screen.blit(score_surface, (SCREEN_WIDTH - 345, 27))
        high_surface = self.small_font.render(f"HIGH {high_score:06d}", True, self.white)
        self.screen.blit(high_surface, (SCREEN_WIDTH - 345, 49))

    def _draw_enemy_sprite(self) -> None:
        body_x = SCREEN_WIDTH // 2
        body_y = SCREEN_HEIGHT // 2 - 40
        pygame.draw.circle(self.screen, (175, 115, 255), (body_x, body_y - 30), 20)
        pygame.draw.rect(self.screen, (130, 82, 212), (body_x - 18, body_y - 10, 36, 72), border_radius=6)
        pygame.draw.line(self.screen, (130, 82, 212), (body_x - 18, body_y + 10), (body_x - 55, body_y + 30), 6)
        pygame.draw.line(self.screen, (130, 82, 212), (body_x + 18, body_y + 10), (body_x + 55, body_y + 30), 6)
        pygame.draw.line(self.screen, (130, 82, 212), (body_x - 10, body_y + 62), (body_x - 25, body_y + 100), 6)
        pygame.draw.line(self.screen, (130, 82, 212), (body_x + 10, body_y + 62), (body_x + 25, body_y + 100), 6)

    def _draw_turn_box(self, turn_state: TurnState, player_time_left: float) -> None:
        turn_text = "PLAYER TURN" if turn_state == TurnState.PLAYER_TURN else "ENEMY TURN"
        surface = self.small_font.render(turn_text, True, self.white)
        self.screen.blit(surface, (SCREEN_WIDTH // 2 - 70, SCREEN_HEIGHT - 160))
        if turn_state == TurnState.PLAYER_TURN:
            t_surface = self.small_font.render(f"TIME: {max(0.0, player_time_left):.1f}s", True, self.accent)
            self.screen.blit(t_surface, (SCREEN_WIDTH // 2 - 54, SCREEN_HEIGHT - 240))

    def _draw_sequence(
        self,
        sequence: list[Direction],
        input_index: int,
        turn_state: TurnState,
        enemy_phase: EnemyPhase,
    ) -> None:
        if not sequence:
            return

        if turn_state == TurnState.ENEMY_TURN and not enemy_phase.telegraph_visible:
            return

        arrow_map = {
            Direction.UP: "UP",
            Direction.DOWN: "DN",
            Direction.LEFT: "LT",
            Direction.RIGHT: "RT",
        }

        start_x = SCREEN_WIDTH // 2 - ((len(sequence) * 64) // 2)
        y = SCREEN_HEIGHT // 2 + 120
        for index, direction in enumerate(sequence):
            x = start_x + index * 64
            color = self.accent if index >= input_index else self.hp_good
            pygame.draw.rect(self.screen, self.panel_color, (x, y, 56, 46), border_radius=4)
            pygame.draw.rect(self.screen, color, (x, y, 56, 46), width=2, border_radius=4)
            text = self.small_font.render(arrow_map[direction], True, color)
            self.screen.blit(text, (x + 12, y + 12))

    def _draw_game_over(self, score: int, high_score: int) -> None:
        self._draw_text_center("GAME OVER", 160, self.pixel_font, self.hp_bad)
        self._draw_text_center(f"SCORE: {score}", 240, self.small_font, self.white)
        self._draw_text_center(f"HIGH SCORE: {high_score}", 280, self.small_font, self.white)
        self._draw_text_center("ENTER TO RESTART", 340, self.small_font, self.accent)
        self._draw_text_center("M FOR MENU", 370, self.small_font, self.white)

    def _draw_debug(self, debug_lines: list[str]) -> None:
        y = SCREEN_HEIGHT - 92
        for line in debug_lines:
            surface = self.small_font.render(line, True, (144, 231, 195))
            self.screen.blit(surface, (20, y))
            y += 24
