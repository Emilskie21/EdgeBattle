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
    def __init__(self, path: Path) -> None:
        from PIL import Image, ImageSequence

        self._frames: list[pygame.Surface] = []
        self._durations_ms: list[int] = []
        im = Image.open(path)
        for frame in ImageSequence.Iterator(im):
            rgba = frame.convert("RGBA")
            data = rgba.tobytes()
            # surf = pygame.image.frombytes(rgba.size, data, "RGBA").convert_alpha()
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
        if not self._frames:
            return
        self._elapsed += dt_ms
        d = float(self._durations_ms[self._idx])
        while self._elapsed >= d:
            self._elapsed -= d
            self._idx = (self._idx + 1) % len(self._frames)
            d = float(self._durations_ms[self._idx])

    def draw(self, screen: pygame.Surface) -> None:
        if self._frames:
            screen.blit(self._frames[self._idx], (0, 0))


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
