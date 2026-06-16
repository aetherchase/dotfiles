#!/usr/bin/env python3
"""Curate a wallpaper folder into omarchy per-theme background dirs by color
affinity. See docs/superpowers/specs/2026-06-16-wallpaper-theme-matcher-design.md."""
from __future__ import annotations

import math
import tomllib

# Hue-bearing palette keys; color0/7/8/15 (near black/white) are skipped.
PALETTE_KEYS = (
    "background", "accent",
    "color1", "color2", "color3", "color4", "color5", "color6",
    "color9", "color10", "color11", "color12", "color13", "color14",
)


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


def ciede2000(lab1: tuple[float, float, float],
              lab2: tuple[float, float, float]) -> float:
    """CIEDE2000 color-difference (kL=kC=kH=1)."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    avg_Lp = (L1 + L2) / 2.0
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    avg_C = (C1 + C2) / 2.0
    G = 0.5 * (1 - math.sqrt(avg_C ** 7 / (avg_C ** 7 + 25 ** 7)))
    a1p = (1 + G) * a1
    a2p = (1 + G) * a2
    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)
    avg_Cp = (C1p + C2p) / 2.0
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)
    if C1p * C2p == 0:
        avg_hp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        avg_hp = (h1p + h2p) / 2.0
    elif h1p + h2p < 360:
        avg_hp = (h1p + h2p + 360) / 2.0
    else:
        avg_hp = (h1p + h2p - 360) / 2.0
    T = (1 - 0.17 * math.cos(math.radians(avg_hp - 30))
         + 0.24 * math.cos(math.radians(2 * avg_hp))
         + 0.32 * math.cos(math.radians(3 * avg_hp + 6))
         - 0.20 * math.cos(math.radians(4 * avg_hp - 63)))
    d_ro = 30 * math.exp(-(((avg_hp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(avg_Cp ** 7 / (avg_Cp ** 7 + 25 ** 7))
    Sl = 1 + (0.015 * (avg_Lp - 50) ** 2) / math.sqrt(20 + (avg_Lp - 50) ** 2)
    Sc = 1 + 0.045 * avg_Cp
    Sh = 1 + 0.015 * avg_Cp * T
    Rt = -math.sin(math.radians(2 * d_ro)) * Rc
    return math.sqrt(
        (dLp / Sl) ** 2
        + (dCp / Sc) ** 2
        + (dHp / Sh) ** 2
        + Rt * (dCp / Sc) * (dHp / Sh)
    )


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def parse_palette(colors_toml_path: str) -> list[tuple[int, int, int]]:
    """Return the hue-bearing RGB colors from a theme's colors.toml."""
    with open(colors_toml_path, "rb") as f:
        data = tomllib.load(f)
    out = []
    for key in PALETTE_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val.startswith("#") and len(val) >= 7:
            out.append(hex_to_rgb(val))
    return out
