"""Load art using only ``assets/assets.json`` paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from game.ui.animated_background import load_background_from_path
from game.ui.assets_manifest import load_manifest, resolve_asset


def _load_raster(path: Path) -> pygame.Surface | None:
    if not path.is_file():
        return None
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, OSError):
        return None


def load_packaged_surfaces() -> dict[str, Any]:
    """Returns keys: menu_static, game_bg, arrow_base, punch, hp_by_value, sprites_fp."""
    m = load_manifest()
    out: dict[str, Any] = {
        "menu_static": None,
        "game_bg": None,
        "arrow_base": None,
        "punch": None,
        "hp_by_value": {},
        "sprites_fp": {},
    }
    if not m:
        return out

    menu_rel = m.get("menu_background")
    if isinstance(menu_rel, str):
        out["menu_static"] = _load_raster(resolve_asset(menu_rel))

    game_rel = m.get("game_background")
    if isinstance(game_rel, str):
        bg = load_background_from_path(resolve_asset(game_rel))
        out["game_bg"] = bg
    else:
        out["game_bg"] = None

    arrow_rel = m.get("arrow")
    if isinstance(arrow_rel, str):
        out["arrow_base"] = _load_raster(resolve_asset(arrow_rel))

    punch_rel = m.get("punch")
    if isinstance(punch_rel, str):
        out["punch"] = _load_raster(resolve_asset(punch_rel))

    health = m.get("health")
    if isinstance(health, dict):
        for key in ("3", "2", "1"):
            rel = health.get(key)
            if isinstance(rel, str):
                surf = _load_raster(resolve_asset(rel))
                if surf is not None:
                    out["hp_by_value"][int(key)] = surf

    sp = m.get("sprites_firstperson")
    if isinstance(sp, dict):
        for side in ("left", "right"):
            rel = sp.get(side)
            if isinstance(rel, str):
                surf = _load_raster(resolve_asset(rel))
                if surf is not None:
                    out["sprites_fp"][side] = surf

    return out


def scale_arrow_base(base: pygame.Surface) -> pygame.Surface:
    max_side = min(SCREEN_WIDTH, SCREEN_HEIGHT) // 3
    w, h = base.get_size()
    scale = min(max_side / max(w, h), 1.0)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return pygame.transform.smoothscale(base, (nw, nh))


def scale_fp_sprite(surf: pygame.Surface, max_h: int) -> pygame.Surface:
    w, h = surf.get_size()
    if h <= max_h:
        return surf
    scale = max_h / float(h)
    return pygame.transform.smoothscale(surf, (max(1, int(w * scale)), max_h))


def arrow_for_direction(base: pygame.Surface, direction: object) -> pygame.Surface:
    from game.constants import Direction

    deg = {
        Direction.RIGHT: 0,
        Direction.UP: 90,
        Direction.LEFT: 180,
        Direction.DOWN: -90,
    }
    return pygame.transform.rotate(base, deg[direction])
