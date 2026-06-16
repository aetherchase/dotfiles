#!/usr/bin/env python3
"""Curate a wallpaper folder into omarchy per-theme background dirs by color
affinity. See docs/superpowers/specs/2026-06-16-wallpaper-theme-matcher-design.md."""
from __future__ import annotations

import math
import os
import shutil
import tomllib

from PIL import Image

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


def dominant_colors(path: str, k: int = 5, resize: int = 256
                    ) -> list[tuple[tuple[int, int, int], float]]:
    """Top-k dominant colors as [(rgb, weight)], weight = pixel fraction, desc."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((resize, resize))
    q = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    palette = q.getpalette()
    counts = q.getcolors()  # [(count, index), ...]
    total = sum(c for c, _ in counts) or 1
    out = []
    for count, idx in counts:
        rgb = tuple(palette[idx * 3: idx * 3 + 3])
        out.append((rgb, count / total))
    out.sort(key=lambda t: -t[1])
    return out


def score_image(dominants: list[tuple[tuple[int, int, int], float]],
                theme_labs: list[tuple[float, float, float]]) -> float:
    """Weighted mean of each dominant color's nearest-theme-color CIEDE2000."""
    if not theme_labs:
        return float("inf")
    score = 0.0
    for rgb, weight in dominants:
        lab = srgb_to_lab(rgb)
        score += weight * min(ciede2000(lab, t) for t in theme_labs)
    return score


def load_themes(stock_dir: str, user_dir: str
                ) -> dict[str, list[tuple[float, float, float]]]:
    """Map theme slug -> Lab palette, from stock then user dirs (user wins on clash)."""
    themes: dict[str, list[tuple[float, float, float]]] = {}
    for base in (stock_dir, user_dir):
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            toml_path = os.path.join(base, slug, "colors.toml")
            if not os.path.isfile(toml_path):
                continue
            rgbs = parse_palette(toml_path)
            if rgbs:
                themes[slug] = [srgb_to_lab(c) for c in rgbs]
    return themes


def write_matches(repo_bg_dir: str, assignments: dict[str, list[str]]) -> None:
    """Rebuild repo per-theme dirs: clear all existing theme dirs (keep .gitkeep),
    then symlink each assigned wallpaper (absolute source path) into its theme dir."""
    os.makedirs(repo_bg_dir, exist_ok=True)
    for name in os.listdir(repo_bg_dir):
        if name == ".gitkeep":
            continue
        path = os.path.join(repo_bg_dir, name)
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)
    for slug, images in assignments.items():
        if not images:
            continue
        theme_dir = os.path.join(repo_bg_dir, slug)
        os.makedirs(theme_dir, exist_ok=True)
        for img in images:
            link = os.path.join(theme_dir, os.path.basename(img))
            src = os.path.abspath(img)
            if os.path.lexists(link):
                os.unlink(link)
            os.symlink(src, link)


def _populated_slugs(repo_bg_dir: str) -> list[str]:
    if not os.path.isdir(repo_bg_dir):
        return []
    out = []
    for name in sorted(os.listdir(repo_bg_dir)):
        d = os.path.join(repo_bg_dir, name)
        if name != ".gitkeep" and os.path.isdir(d) and os.listdir(d):
            out.append(name)
    return out


def relink(repo_bg_dir: str, config_bg_dir: str) -> int:
    """Create config/<slug> -> repo/<slug> dir-symlinks for populated themes;
    prune our stale symlinks for themes that no longer qualify. Returns link count."""
    os.makedirs(config_bg_dir, exist_ok=True)
    populated = set(_populated_slugs(repo_bg_dir))
    # prune stale symlinks we own (point into repo_bg_dir) but no longer populated
    for name in os.listdir(config_bg_dir):
        link = os.path.join(config_bg_dir, name)
        if os.path.islink(link):
            target = os.path.realpath(link)
            if target.startswith(os.path.realpath(repo_bg_dir)) and name not in populated:
                os.unlink(link)
    for slug in populated:
        link = os.path.join(config_bg_dir, slug)
        target = os.path.join(repo_bg_dir, slug)
        if os.path.lexists(link):
            if os.path.islink(link):
                os.unlink(link)
            else:
                continue  # real dir owned by something else; don't clobber
        os.symlink(target, link)
    return len(populated)


def unlink(repo_bg_dir: str, config_bg_dir: str) -> int:
    """Remove config/<slug> symlinks that point into repo_bg_dir. Returns count."""
    if not os.path.isdir(config_bg_dir):
        return 0
    n = 0
    repo_real = os.path.realpath(repo_bg_dir)
    for name in os.listdir(config_bg_dir):
        link = os.path.join(config_bg_dir, name)
        if os.path.islink(link) and os.path.realpath(link).startswith(repo_real):
            os.unlink(link)
            n += 1
    return n
