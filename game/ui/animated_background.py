"""Fullscreen background: animated GIF or static raster."""

from __future__ import annotations
from pathlib import Path
from typing import Protocol

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH


class BackgroundDrawable(Protocol):
    def update(self, dt_ms: float) -> None: ...
    def draw(self, screen: pygame.Surface) -> None: ...


class StaticBackground:
    def __init__(self, surface: pygame.Surface) -> None:
        self._surf = pygame.transform.smoothscale(surface, (SCREEN_WIDTH, SCREEN_HEIGHT))

    def update(self, dt_ms: float) -> None:
        _ = dt_ms

    def draw(self, screen: pygame.Surface) -> None:
        screen.blit(self._surf, (0, 0))

class GifBackground:
    def __init__(self, path: Path, play_once: bool = False) -> None:
        from PIL import Image, ImageSequence

        self._frames: list[pygame.Surface] = []
        self._durations_ms: list[int] = []

        self._play_once = play_once
        self._finished = False
        self._on_finish = None

        im = Image.open(path)
        for frame in ImageSequence.Iterator(im):
            rgba = frame.convert("RGBA")
            data = rgba.tobytes()
            surf = pygame.image.frombytes(data, rgba.size, "RGBA").convert_alpha()
            self._frames.append(
                pygame.transform.smoothscale(surf, (SCREEN_WIDTH, SCREEN_HEIGHT))
            )

            finfo = getattr(frame, "info", {}) or {}
            dur = finfo.get("duration")
            if dur is None:
                dur = im.info.get("duration", 100)
            if dur is None:
                dur = 100
            self._durations_ms.append(max(1, int(dur)))

        if not self._frames:
            raise ValueError("empty gif")

        self._idx = 0
        self._elapsed = 0.0

    def update(self, dt_ms: float) -> None:
        if not self._frames or self._finished:
            return

        self._elapsed += dt_ms
        d = float(self._durations_ms[self._idx])

        while self._elapsed >= d:
            self._elapsed -= d

            if self._idx == len(self._frames) - 1:
                if self._play_once:
                    self._finished = True
                    if self._on_finish:
                        self._on_finish()
                    return
                else:
                    self._idx = 0
            else:
                self._idx += 1

            d = float(self._durations_ms[self._idx])

    def draw(self, screen: pygame.Surface) -> None:
        if self._frames:
            screen.blit(self._frames[self._idx], (0, 0))

    def reset(self) -> None:
        self._idx = 0
        self._elapsed = 0.0
        self._finished = False


    def set_on_finish(self, fn) -> None:
        self._on_finish = fn


    def finished(self) -> bool:
        return self._finished


class GifSpriteAnimation:
    """
    Lightweight GIF animation for in-game sprites (not fullscreen).

    - frames are scaled once to a target height (aspect ratio preserved)
    - supports one-shot (play_once) + on-finish callback for punch animations
    """

    def __init__(self, path: Path, target_h: int) -> None:
        from PIL import Image, ImageSequence

        self._frames: list[pygame.Surface] = []
        self._durations_ms: list[int] = []

        self._target_h = max(1, int(target_h))
        self._play_once = False
        self._finished = False
        self._on_finish = None

        im = Image.open(path)
        for frame in ImageSequence.Iterator(im):
            rgba = frame.convert("RGBA")
            data = rgba.tobytes()
            surf = pygame.image.frombytes(data, rgba.size, "RGBA").convert_alpha()

            w, h = surf.get_size()
            if h <= 0:
                continue
            scale = self._target_h / float(h)
            sw = max(1, int(w * scale))
            sh = self._target_h
            self._frames.append(pygame.transform.smoothscale(surf, (sw, sh)))

            finfo = getattr(frame, "info", {}) or {}
            dur = finfo.get("duration")
            if dur is None:
                dur = im.info.get("duration", 100)
            if dur is None:
                dur = 100
            self._durations_ms.append(max(1, int(dur)))

        if not self._frames:
            raise ValueError("empty gif")

        self._idx = 0
        self._elapsed = 0.0

    @property
    def frame_size(self) -> tuple[int, int]:
        f = self._frames[0]
        return f.get_width(), f.get_height()

    def update(self, dt_ms: float) -> None:
        if not self._frames or self._finished:
            return

        self._elapsed += dt_ms
        d = float(self._durations_ms[self._idx])
        while self._elapsed >= d:
            self._elapsed -= d

            if self._idx == len(self._frames) - 1:
                if self._play_once:
                    self._finished = True
                    if self._on_finish:
                        self._on_finish()
                    return
                self._idx = 0
            else:
                self._idx += 1
            d = float(self._durations_ms[self._idx])

    def draw(self, screen: pygame.Surface) -> None:
        # Sprites draw at (0,0) so caller can position/crop using blit.
        screen.blit(self._frames[self._idx], (0, 0))

    def current_frame(self) -> pygame.Surface:
        return self._frames[self._idx]

    def reset(self) -> None:
        self._idx = 0
        self._elapsed = 0.0
        self._finished = False

    def set_on_finish(self, fn) -> None:
        self._on_finish = fn


def load_sprite_gif(path: Path, target_h: int) -> GifSpriteAnimation | None:
    if not path.is_file():
        return None
    try:
        return GifSpriteAnimation(path, target_h=target_h)
    except Exception:
        return None


def load_background_from_path(path: Path) -> BackgroundDrawable | None:
    if not path.is_file():
        return None
    suf = path.suffix.lower()
    if suf == ".gif":
        try:
            return GifBackground(path)
        except Exception:
            return None
    if suf in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        try:
            surf = pygame.image.load(str(path)).convert_alpha()
            return StaticBackground(surf)
        except (pygame.error, OSError):
            return None
    return None
