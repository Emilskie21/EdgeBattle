import math
from typing import Optional

import pygame

from game.combat.player_stats import PlayerStats
from game.constants import (
    ARROW_CENTER_Y_RATIO,
    FP_SPRITE_BOTTOM_PAD,
    FP_SPRITE_MAX_HEIGHT_RATIO,
    GameState,
    PUNCH_FLASH_MS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from game.constants import Direction
from game.paths import repo_root
from game.ui import game_assets
from game.ui.animated_background import BackgroundDrawable


class UIRenderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        pygame.font.init()
        font_path = repo_root() / "assets" / "font" / "DiaryOfAn8BitMage-lYDD.ttf"
        if font_path.is_file():
            self.pixel_font = pygame.font.Font(str(font_path), 28)
            self.small_font = pygame.font.Font(str(font_path), 18)
            self.tiny_font = pygame.font.Font(str(font_path), 16)
        else:
            self.pixel_font = pygame.font.SysFont("consolas", 28, bold=True)
            self.small_font = pygame.font.SysFont("consolas", 18)
            self.tiny_font = pygame.font.SysFont("consolas", 16)
        self.accent = (247, 199, 56)
        self.white = (238, 238, 238)
        self.muted = (120, 118, 140)
        self.hp_bad = (220, 64, 64)
        pack = game_assets.load_packaged_surfaces()
        self._menu_static = pack.get("menu_static")
        self._game_bg: BackgroundDrawable | None = pack.get("game_bg")
        ab = pack.get("arrow_base")
        self._arrow_scaled_base = game_assets.scale_arrow_base(ab) if ab else None
        self._punch_sprite = pack.get("punch")
        self._hp_by_value: dict[int, pygame.Surface] = pack.get("hp_by_value") or {}

        sp = pack.get("sprites_fp") or {}
        self._sprite_left = sp.get("left")
        self._sprite_right = sp.get("right")
        self._sprite_left_scaled: pygame.Surface | None = None
        self._sprite_right_scaled: pygame.Surface | None = None
        if self._sprite_left or self._sprite_right:
            max_h = int(SCREEN_HEIGHT * FP_SPRITE_MAX_HEIGHT_RATIO)
            if self._sprite_left:
                self._sprite_left_scaled = game_assets.scale_fp_sprite(self._sprite_left, max_h)
            if self._sprite_right:
                self._sprite_right_scaled = game_assets.scale_fp_sprite(self._sprite_right, max_h)

        if self._menu_static:
            self._menu_scaled = pygame.transform.smoothscale(
                self._menu_static, (SCREEN_WIDTH, SCREEN_HEIGHT)
            )
        else:
            self._menu_scaled = None

    def draw_frame(
        self,
        game_state: GameState,
        stats: PlayerStats,
        high_score: int,
        current_arrow: Optional[Direction],
        arrow_start_ms: int,
        arrow_deadline_ms: int,
        punch_flash_until_ms: int,
        dt_ms: float,
        calibrated: bool,
        countdown_value: int | None = None,
        game_over_name_input: str = "",
        game_over_name_saved: bool = False,
        game_over_since_ms: int = 0,
        show_debug: bool = False,
        debug_lines: list[str] | None = None,
    ) -> None:
        if game_state in (GameState.PLAYING, GameState.COUNTDOWN, GameState.GAME_OVER):
            if self._game_bg:
                self._game_bg.update(dt_ms)
                self._game_bg.draw(self.screen)
            else:
                self.screen.fill((24, 22, 38))
        else:
            if game_state == GameState.OPTIONS and self._menu_scaled:
                self.screen.blit(self._menu_scaled, (0, 0))
            else:
                self.screen.fill((20, 18, 32))

        if game_state == GameState.MENU:
            # No traditional menu UI; this state is effectively just a transition.
            if not calibrated:
                self._draw_text_center("NEED CALIBRATION", 120, self.pixel_font, self.muted)
        elif game_state == GameState.OPTIONS:
            self._draw_options(show_debug)
        elif game_state == GameState.COUNTDOWN:
            self._draw_countdown(countdown_value)
        elif game_state == GameState.PLAYING:
            self._draw_hud(stats, high_score)
            self._draw_fp_sprites()
            self._draw_arrow_prompt(
                current_arrow,
                arrow_start_ms,
                arrow_deadline_ms,
            )
            self._draw_punch_flash(punch_flash_until_ms)
        elif game_state == GameState.GAME_OVER:
            self._draw_game_over_screen(
                stats_score=stats.score,
                game_over_name_input=game_over_name_input,
                game_over_name_saved=game_over_name_saved,
                game_over_since_ms=game_over_since_ms,
            )

        if show_debug:
            self._draw_debug(debug_lines or [])

        pygame.display.flip()

    def _draw_text_center(self, text: str, y: int, font: pygame.font.Font, color: tuple[int, int, int]) -> None:
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(SCREEN_WIDTH // 2, y))
        self.screen.blit(surface, rect)

    def _draw_menu(self, calibrated: bool) -> None:
        self._draw_text_center("SHADOW BOXING", 120, self.pixel_font, self.accent)
        if calibrated:
            self._draw_text_center("START  [ENTER]", 260, self.small_font, self.white)
        else:
            self._draw_text_center("START (need calibration)", 260, self.small_font, self.muted)
        self._draw_text_center("CALIBRATE  [C]", 300, self.small_font, self.white)
        self._draw_text_center("OPTIONS  [O]", 340, self.small_font, self.white)
        self._draw_text_center("QUIT  [ESC]", 380, self.small_font, self.white)

    def _draw_options(self, show_debug: bool) -> None:
        self._draw_text_center("OPTIONS", 140, self.pixel_font, self.accent)
        status = "ON" if show_debug else "OFF"
        self._draw_text_center(f"DEBUG OVERLAY: {status}  [D]", 280, self.small_font, self.white)
        self._draw_text_center("BACK  [M]", 330, self.small_font, self.white)

    def _draw_hud(self, stats: PlayerStats, high_score: int) -> None:
        pad_x = 16
        y = 12
        hp_surf = self._hp_by_value.get(stats.hp)
        if hp_surf:
            self.screen.blit(hp_surf, (pad_x, y))
        # If heart images are missing, HUD simply won't show HP.

        # hi = self.small_font.render(f"HIGH  {high_score:06d}", True, self.accent)
        # self.screen.blit(hi, (SCREEN_WIDTH - hi.get_width() - pad_x, y))

        # sc = self.small_font.render(f"SCORE  {stats.score:06d}", True, self.muted)
        # self.screen.blit(sc, (pad_x, y + 36))

        sc = self.small_font.render(f"SCORE  {stats.score:06d}", True, self.muted)
        sc_pos = (SCREEN_WIDTH - sc.get_width() - pad_x, y)
        self.screen.blit(sc, sc_pos)

    def _draw_fp_sprites(self) -> None:
        bottom = SCREEN_HEIGHT - FP_SPRITE_BOTTOM_PAD
        if self._sprite_left_scaled:
            r = self._sprite_left_scaled.get_rect()
            r.bottomleft = (FP_SPRITE_BOTTOM_PAD, bottom)
            self.screen.blit(self._sprite_left_scaled, r)
        if self._sprite_right_scaled:
            r = self._sprite_right_scaled.get_rect()
            r.bottomright = (SCREEN_WIDTH - FP_SPRITE_BOTTOM_PAD, bottom)
            self.screen.blit(self._sprite_right_scaled, r)

    def _arrow_alpha(self, now_ms: int, start_ms: int, end_ms: int) -> int:
        if end_ms <= start_ms:
            return 255
        t = (now_ms - start_ms) / float(end_ms - start_ms)
        t = max(0.0, min(1.0, t))
        lo = int(0.08 * 255)
        return int(lo + (255 - lo) * t)

    def _arrow_pressure(self, now_ms: int, start_ms: int, end_ms: int) -> float:
        """0 = window start, 1 = deadline — matches opacity ramp toward commitment."""
        if end_ms <= start_ms:
            return 1.0
        t = (now_ms - start_ms) / float(end_ms - start_ms)
        return max(0.0, min(1.0, t))

    def _draw_arrow_prompt(
        self,
        direction: Optional[Direction],
        arrow_start_ms: int,
        arrow_deadline_ms: int,
    ) -> None:
        if direction is None or self._arrow_scaled_base is None:
            return
        now_ms = pygame.time.get_ticks()
        arr = game_assets.arrow_for_direction(self._arrow_scaled_base, direction)
        alpha = self._arrow_alpha(now_ms, arrow_start_ms, arrow_deadline_ms)
        pressure = self._arrow_pressure(now_ms, arrow_start_ms, arrow_deadline_ms)
        arr = arr.copy()
        arr.set_alpha(alpha)
        cx = SCREEN_WIDTH // 2
        cy = int(SCREEN_HEIGHT * ARROW_CENTER_Y_RATIO)
        rect = arr.get_rect(center=(cx, cy))

        # Inline border/highlight drawn onto the arrow image surface.
        if pressure > 0.02:
            pad = int(2 + 6 * pressure)
            bw = max(2, int(2 + 5 * pressure))
            radius = min(10, 4 + int(6 * pressure))
            w = max(1, arr.get_width() - 2 * pad)
            h = max(1, arr.get_height() - 2 * pad)
            border_rect = pygame.Rect(pad, pad, w, h)
            pygame.draw.rect(arr, (255, 72, 48), border_rect, width=bw, border_radius=radius)

        if pressure > 0.06:
            inner_pad = int(3 + 7 * pressure)
            iw = max(1, int(1 + 2 * pressure))
            w = max(1, arr.get_width() - 2 * inner_pad)
            h = max(1, arr.get_height() - 2 * inner_pad)
            inner_rect = pygame.Rect(inner_pad, inner_pad, w, h)
            pygame.draw.rect(arr, (255, 210, 120), inner_rect, width=iw, border_radius=4)

        self.screen.blit(arr, rect)

    def _draw_punch_flash(self, until_ms: int) -> None:
        now = pygame.time.get_ticks()
        if until_ms <= now:
            return
        t = (until_ms - now) / float(PUNCH_FLASH_MS)
        t = max(0.0, min(1.0, t))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((45, 20, 28, int(120 * t)))
        self.screen.blit(overlay, (0, 0))

        if self._punch_sprite:
            ps = self._punch_sprite
            scale = 0.55 + 0.35 * t
            nw = max(1, int(ps.get_width() * scale))
            nh = max(1, int(ps.get_height() * scale))
            img = pygame.transform.smoothscale(ps, (nw, nh))
            img.set_alpha(int(255 * min(1.0, t * 1.2)))
            r = img.get_rect(center=(SCREEN_WIDTH // 2 + int(60 * (1.0 - t)), SCREEN_HEIGHT // 2))
            self.screen.blit(img, r)

    def _draw_countdown(self, countdown_value: int | None) -> None:
        if countdown_value is None or countdown_value <= 0:
            return
        color = self.accent if countdown_value == 3 else self.white
        self._draw_text_center(str(countdown_value), int(SCREEN_HEIGHT * 0.42), self.pixel_font, color)

    def _draw_game_over_screen(
        self,
        stats_score: int,
        game_over_name_input: str,
        game_over_name_saved: bool,
        game_over_since_ms: int,
    ) -> None:
        # Animated black filter overlay (sits on top of the GIF background).
        now = pygame.time.get_ticks()
        elapsed_ms = max(0, now - game_over_since_ms)
        # Flicker faster near the end to make the filter feel alive.
        t = elapsed_ms / 1000.0
        pulse = 0.5 + 0.5 * math.sin(t * 5.5)
        alpha = int(110 + 90 * pulse)

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

        header = "CONGRATULATIONS" if stats_score >= 1000 else "GAME OVER"
        header_color = self.accent if stats_score >= 1000 else self.hp_bad
        self._draw_text_center(header, int(SCREEN_HEIGHT * 0.36), self.pixel_font, header_color)
        self._draw_text_center(f"SCORE: {stats_score}", int(SCREEN_HEIGHT * 0.52), self.small_font, self.white)

        # Name prompt for leaderboard storage.
        shown_name = game_over_name_input if game_over_name_input else ""
        self._draw_text_center(
            f"ENTER NAME (PRESS ENTER): {shown_name}",
            int(SCREEN_HEIGHT * 0.66),
            self.small_font,
            self.muted,
        )

        # Return option.
        self._draw_text_center("PRESS M TO RETURN", int(SCREEN_HEIGHT * 0.78), self.small_font, self.white)

    def _draw_debug(self, debug_lines: list[str]) -> None:
        y = SCREEN_HEIGHT - 28 - 18 * len(debug_lines)
        for line in debug_lines:
            surface = self.tiny_font.render(line, True, (90, 180, 140))
            self.screen.blit(surface, (12, y))
            y += 18
