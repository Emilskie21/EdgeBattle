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
from game.ui.animated_background import BackgroundDrawable, GifBackground


class UIRenderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        pygame.font.init()
        font_path = repo_root() / "assets" / "font" / "DiaryOfAn8BitMage-lYDD.ttf"
        if font_path.is_file():
            self.pixel_font = pygame.font.Font(str(font_path), 28)
            self.header_font = pygame.font.Font(str(font_path), 56)
            self.countdown_font = pygame.font.Font(str(font_path), 140)
            self.small_font = pygame.font.Font(str(font_path), 22)
            self.tiny_font = pygame.font.Font(str(font_path), 16)
        else:
            self.pixel_font = pygame.font.SysFont("consolas", 28, bold=True)
            self.header_font = pygame.font.SysFont("consolas", 56, bold=True)
            self.countdown_font = pygame.font.SysFont("consolas", 140, bold=True)
            self.small_font = pygame.font.SysFont("consolas", 22)
            self.tiny_font = pygame.font.SysFont("consolas", 16)
        self.accent = (247, 199, 56)
        self.white = (238, 238, 238)
        self.muted = (120, 118, 140)
        self.hp_bad = (220, 64, 64)
        pack = game_assets.load_packaged_surfaces()

        self._edgar_sprites = pack.get("sprites_edgar") or {}
        self._edgar_current: GifBackground = self._edgar_sprites.get("idle")

        self._player_sprites = pack.get("sprites_player") or {}

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
        self.instructions = pack.get("instructions")
        self.left_hand = "left_idle"
        self.right_hand = "right_idle"
        self._punch_end_ms = 0
        self.loading_icon: GifBackground = pack.get("loading")
        gradients = pack.get("gradient") or {}
        self.side_gradient: pygame.Surface = gradients.get("side")
        self.level_gradient: pygame.Surface = gradients.get("level")
        self.gradient_current: str = None

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
        game_over_phase: int = 1,
        game_over_rank: int = 0,
        game_over_total: int = 0,
        game_over_scores: list[dict[str, str | int]] | None = None,
        leaderboard_scroll_y: float = 0.0,
        game_over_row_id: int = 0,
        show_debug: bool = False,
        debug_lines: list[str] | None = None,
    ) -> None:
        if game_state in (GameState.PLAYING, GameState.COUNTDOWN, GameState.GAME_OVER):
            if self._game_bg:
                frame = self._game_bg._frames[self._game_bg._idx]
                frame = pygame.transform.scale(frame, (1104, 621))
                r = frame.get_rect()
                r.center = (SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
                self._game_bg.update(dt_ms)
                self.screen.blit(frame, r)
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
        elif game_state == GameState.INSTRUCTIONS:
            self._draw_instructions(dt_ms)
            self.draw_loading(dt_ms)
        elif game_state == GameState.PLAYING:
            self._draw_hud(stats, high_score)
            self._draw_edgar(self._edgar_current, dt_ms)
            self._draw_arrow_prompt(
                current_arrow,
                arrow_start_ms,
                arrow_deadline_ms,
            )
            self._draw_player_hands(self.left_hand, self.right_hand)
            self._draw_punch_flash(punch_flash_until_ms)
            self.draw_gradient(self.gradient_current)
        elif game_state == GameState.GAME_OVER:
            self._draw_game_over_screen(
                stats_score=stats.score,
                game_over_name_input=game_over_name_input,
                game_over_name_saved=game_over_name_saved,
                game_over_since_ms=game_over_since_ms,
                game_over_phase=game_over_phase,
                game_over_rank=game_over_rank,
                game_over_total=game_over_total,
                game_over_scores=game_over_scores or [],
                leaderboard_scroll_y=leaderboard_scroll_y,
                game_over_row_id=game_over_row_id,
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
        hp_scaled = pygame.transform.smoothscale(hp_surf, (250, 59))
        if hp_surf:
            self.screen.blit(hp_scaled, (pad_x, y))
        # If heart images are missing, HUD simply won't show HP.

        # hi = self.small_font.render(f"HIGH  {high_score:06d}", True, self.accent)
        # self.screen.blit(hi, (SCREEN_WIDTH - hi.get_width() - pad_x, y))

        # sc = self.small_font.render(f"SCORE  {stats.score:06d}", True, self.muted)
        # self.screen.blit(sc, (pad_x, y + 36))

        hi = self.small_font.render(f"HIGH  {high_score:06d}", True, self.white)
        self.screen.blit(hi, (SCREEN_WIDTH - hi.get_width() - pad_x, y))

        sc = self.small_font.render(f"SCORE  {stats.score:06d}", True, self.accent)
        self.screen.blit(sc, (SCREEN_WIDTH - sc.get_width() - pad_x, y + 26))

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

        # Inline outline stroke that follows the arrow sprite (no box).
        if pressure > 0.02:
            try:
                mask = pygame.mask.from_surface(arr)
                outline = mask.outline()
            except Exception:
                outline = []

            if outline:
                w1 = max(1, int(1 + 3 * pressure))
                w2 = max(1, int(1 + 2 * pressure))
                pygame.draw.lines(arr, (255, 72, 48), True, outline, width=w1)
                if pressure > 0.12:
                    pygame.draw.lines(arr, (255, 210, 120), True, outline, width=w2)

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
        surface = self.countdown_font.render(str(countdown_value), True, color)
        rect = surface.get_rect(center=(SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.40)))
        self.screen.blit(surface, rect)

    def _draw_game_over_screen(
        self,
        stats_score: int,
        game_over_name_input: str,
        game_over_name_saved: bool,
        game_over_since_ms: int,
        game_over_phase: int,
        game_over_rank: int,
        game_over_total: int,
        game_over_scores: list[dict[str, str | int]],
        leaderboard_scroll_y: float,
        game_over_row_id: int,
    ) -> None:
        # Animated black filter overlay (sits on top of the GIF background).
        now = pygame.time.get_ticks()
        elapsed_ms = max(0, now - game_over_since_ms)
        # Slow fade-in tint (no harsh flicker).
        t = elapsed_ms / 1000.0
        ramp = max(0.0, min(1.0, t / 2.6))
        pulse = 0.5 + 0.5 * math.sin(t * 0.9)
        alpha = int((40 + 140 * ramp) * (0.92 + 0.08 * pulse))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, alpha))
        self.screen.blit(overlay, (0, 0))

        header = "CONGRATULATIONS" if stats_score >= 1000 else "GAME OVER"
        header_color = self.accent if stats_score >= 1000 else self.hp_bad
        self._draw_text_center(header, int(SCREEN_HEIGHT * 0.30), self.header_font, header_color)
        self._draw_text_center(f"SCORE: {stats_score}", int(SCREEN_HEIGHT * 0.48), self.small_font, self.white)

        if game_over_phase == 1:
            shown_name = game_over_name_input if game_over_name_input else ""
            self._draw_text_center(
                f"ENTER NAME (PRESS ENTER): {shown_name}",
                int(SCREEN_HEIGHT * 0.64),
                self.small_font,
                self.muted,
            )
        else:
            placed = f"You placed {game_over_rank} out of {game_over_total} completionists"
            self._draw_text_center(placed, int(SCREEN_HEIGHT * 0.56), self.small_font, self.white)

            # Layout band where your row + running list live (centered horizontally).
            start_y = int(SCREEN_HEIGHT * 0.64)
            view_h = int(SCREEN_HEIGHT * 0.20)
            line_h = 18
            x_center = SCREEN_WIDTH // 2
            # Column anchors (shared by your row and rolling list).
            left_rank_x = x_center - 260
            left_name_x = x_center - 230
            left_score_right_x = x_center - 20
            right_rank_x = x_center + 20
            right_name_x = x_center + 50
            right_score_right_x = x_center + 260

            # Your row pinned on the left, at the top of that band.
            your = None
            for r in game_over_scores:
                if int(r.get("id", 0)) == int(game_over_row_id):
                    your = r
                    break
            if your:
                rnk = int(your.get("rank", 0))
                name = str(your.get("name", ""))[:16]
                score = int(your.get("score", 0))
                y0 = start_y - line_h - 2
                rank_s = self.tiny_font.render(str(rnk), True, self.accent)
                name_s = self.tiny_font.render(name, True, self.accent)
                score_s = self.tiny_font.render(str(score), True, self.accent)
                self.screen.blit(rank_s, (left_rank_x, y0))
                self.screen.blit(name_s, (left_name_x, y0))
                self.screen.blit(score_s, (left_score_right_x - score_s.get_width(), y0))

            # Rolling list: rank, name, score on the right, vertically constrained above "Another try".
            clip = pygame.Rect(0, start_y - 4, SCREEN_WIDTH, view_h + 8)
            prev_clip = self.screen.get_clip()
            self.screen.set_clip(clip)
            total_h = max(1, (len(game_over_scores) * line_h))
            base_y = start_y - (int(leaderboard_scroll_y) % total_h)
            for idx, row in enumerate(game_over_scores):
                y = base_y + idx * line_h
                if y < start_y - line_h or y > start_y + view_h:
                    continue
                r = int(row.get("rank", 0))
                name = str(row.get("name", ""))[:16]
                score = int(row.get("score", 0))
                color = self.accent if int(row.get("id", 0)) == int(game_over_row_id) else self.muted
                rank_s = self.tiny_font.render(str(r), True, color)
                name_s = self.tiny_font.render(name, True, color)
                score_s = self.tiny_font.render(str(score), True, color)
                self.screen.blit(rank_s, (right_rank_x, y))
                self.screen.blit(name_s, (right_name_x, y))
                self.screen.blit(score_s, (right_score_right_x - score_s.get_width(), y))
            self.screen.set_clip(prev_clip)

            # End-screen controls (no restart-to-menu; no calibration screen here).
            pad = 20

            surf1 = self.small_font.render("PRESS 1: ANOTHER TRY", True, self.white)
            rect1 = surf1.get_rect(
                bottomright=(SCREEN_WIDTH - pad, SCREEN_HEIGHT - 40)
            )
            self.screen.blit(surf1, rect1)

            surf2 = self.small_font.render("PRESS 2: ANOTHER PLAYER", True, self.accent)
            rect2 = surf2.get_rect(
                bottomright=(SCREEN_WIDTH - pad, SCREEN_HEIGHT - 10)
            )
            self.screen.blit(surf2, rect2)

    def _draw_debug(self, debug_lines: list[str]) -> None:
        y = SCREEN_HEIGHT - 28 - 18 * len(debug_lines)
        for line in debug_lines:
            surface = self.tiny_font.render(line, True, (90, 180, 140))
            self.screen.blit(surface, (12, y))
            y += 18

    def _draw_instructions(self, dt_ms: float) -> None:
        if not self.instructions:
            return

        # animated GIF support
        try:
            self.instructions.update(dt_ms)
            self.instructions.draw(self.screen)
            return
        except Exception:
            pass

        # fallback if it's just a Surface
        surf = self.instructions
        w, h = surf.get_size()

        scale = min(SCREEN_WIDTH / w, SCREEN_HEIGHT / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)

        img = pygame.transform.smoothscale(surf, (nw, nh))
        rect = img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(img, rect)
    
    def _draw_player_hands(self, left_name: str, right_name: str) -> None:
        bottom = SCREEN_HEIGHT
        left = self._player_sprites.get(left_name)
        right = self._player_sprites.get(right_name)
        left = pygame.transform.scale(left, (978, 550))
        right = pygame.transform.scale(right, (978, 550))
        lower_stance = 70
        if left:
            r = left.get_rect()
            r.bottomleft = (0, bottom + lower_stance)
            self.screen.blit(left, r)
        if right:
            r = right.get_rect()
            r.bottomright = (SCREEN_WIDTH, bottom + lower_stance)
            self.screen.blit(right, r)

    def _draw_edgar(self, current_sprite: GifBackground, dt_ms: float) -> None:
        if not current_sprite:
            return

        # Get current frame
        frame = current_sprite._frames[current_sprite._idx]

        # Resize (change numbers as needed)
        frame = pygame.transform.scale(frame, (637, 900))

        # Position (example: bottom center like a character)
        r = frame.get_rect()
        r.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT)
        r.y += 380
        self.screen.blit(frame, r)
        current_sprite.update(dt_ms)

    def draw_loading(self, dt_ms):
        if self.loading_icon is None:
            return
        
        frame = self.loading_icon._frames[self.loading_icon._idx]

        pad = 20
        self.loading_icon.update(dt_ms)
        nw = int(frame.get_width() * 0.03)
        nh = int(frame.get_height() * 0.06)
        img = pygame.transform.smoothscale(frame, (nw, nh))

        rect = img.get_rect()
        rect.bottomright = (SCREEN_WIDTH - pad, SCREEN_HEIGHT - pad)

        self.screen.blit(img, rect)

    def draw_gradient(self, current_gradient):
        if not current_gradient:
            return

        side = self.side_gradient
        level = self.level_gradient

        img = None

        if current_gradient in ("left", "right") and side:
            sw, sh = side.get_size()
            scale = min(SCREEN_WIDTH / sw, SCREEN_HEIGHT / sh, 1.0)
            img = pygame.transform.smoothscale(side, (int(sw * scale), int(sh * scale)))

            if current_gradient == "right":
                img = pygame.transform.flip(img, True, False)

        elif current_gradient in ("up", "down") and level:
            lw, lh = level.get_size()
            scale = min(SCREEN_WIDTH / lw, SCREEN_HEIGHT / lh, 1.0)
            img = pygame.transform.smoothscale(level, (int(lw * scale), int(lh * scale)))

            if current_gradient == "up":
                img = pygame.transform.flip(img, False, True)
            
        if img:
            rect = img.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(img, rect)