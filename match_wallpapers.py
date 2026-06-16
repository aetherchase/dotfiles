#!/usr/bin/env python3
"""Curate a wallpaper folder into omarchy per-theme background dirs by color
affinity. See docs/superpowers/specs/2026-06-16-wallpaper-theme-matcher-design.md."""
from __future__ import annotations


def passes_ratio(width: int, height: int, min_ratio: float) -> bool:
    """True if width/height >= min_ratio (default caller passes 1.0 to drop portrait)."""
    if height <= 0:
        return False
    return (width / height) >= min_ratio


def _linearize(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def srgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB (0-255) -> CIE Lab (D65)."""
    r, g, b = (_linearize(v) for v in rgb)
    # linear sRGB -> XYZ (D65)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    # normalize by D65 white
    x /= 0.95047
    z /= 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    L = (116 * fy) - 16
    return (L, 500 * (fx - fy), 200 * (fy - fz))
