#!/usr/bin/env python3
"""Curate a wallpaper folder into omarchy per-theme background dirs by color
affinity. See docs/superpowers/specs/2026-06-16-wallpaper-theme-matcher-design.md."""
from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
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
    """Weighted mean of each dominant color's nearest-theme-color CIEDE2000.

    Lenient (averages a bad color away); kept as a building block. The curator
    uses score_image_strict instead — see that function."""
    if not theme_labs:
        return float("inf")
    score = 0.0
    for rgb, weight in dominants:
        lab = srgb_to_lab(rgb)
        score += weight * min(ciede2000(lab, t) for t in theme_labs)
    return score


def lab_chroma(lab: tuple[float, float, float]) -> float:
    """Colorfulness of a Lab color (0 = neutral gray)."""
    return math.hypot(lab[1], lab[2])


def lab_hue(lab: tuple[float, float, float]) -> float:
    """Hue angle of a Lab color in degrees [0, 360)."""
    return math.degrees(math.atan2(lab[2], lab[1])) % 360.0


def hue_sectors(dominants: list[tuple[tuple[int, int, int], float]],
                chroma_floor: float = 12.0, min_weight: float = 0.06,
                sector_deg: float = 30.0) -> int:
    """Count distinct hue sectors carrying significant *chromatic* weight.

    Near-neutral dominants (chroma < chroma_floor) are ignored — they carry no
    hue. A sector counts only if its accumulated weight >= min_weight."""
    acc: dict[int, float] = {}
    for rgb, weight in dominants:
        lab = srgb_to_lab(rgb)
        if lab_chroma(lab) >= chroma_floor:
            sector = int(lab_hue(lab) // sector_deg)
            acc[sector] = acc.get(sector, 0.0) + weight
    return sum(1 for w in acc.values() if w >= min_weight)


def is_polychrome(dominants: list[tuple[tuple[int, int, int], float]],
                  max_hues: int = 4, chroma_floor: float = 12.0,
                  min_weight: float = 0.06, sector_deg: float = 30.0) -> bool:
    """True if the image spreads across more than max_hues distinct hue sectors.

    Such an image (rainbow, neon signage) contains a near match for almost any
    palette, so it belongs to no single theme — reject it outright."""
    return hue_sectors(dominants, chroma_floor, min_weight, sector_deg) > max_hues


def score_image_strict(dominants: list[tuple[tuple[int, int, int], float]],
                       theme_labs: list[tuple[float, float, float]],
                       top_n: int = 3) -> float:
    """Worst nearest-theme CIEDE2000 among the image's top_n most prominent
    colors. The theme must *cover* every prominent color closely — a single
    uncovered dominant color sinks the score (unlike the lenient mean)."""
    if not theme_labs:
        return float("inf")
    top = sorted(dominants, key=lambda t: -t[1])[:top_n]
    return max(min(ciede2000(srgb_to_lab(rgb), t) for t in theme_labs)
               for rgb, _ in top)


def image_mean_chroma(dominants: list[tuple[tuple[int, int, int], float]]) -> float:
    """Weight-averaged colorfulness of an image's dominant colors."""
    total = sum(weight for _, weight in dominants)
    if total <= 0:
        return 0.0
    return sum(weight * lab_chroma(srgb_to_lab(rgb))
               for rgb, weight in dominants) / total


def image_is_neutral(dominants: list[tuple[tuple[int, int, int], float]],
                     chroma_floor: float = 12.0) -> bool:
    """True if the image is essentially grayscale (mean chroma below the floor).

    Grays carry no hue, so CIEDE2000 between them is driven by lightness alone —
    chromatic theme matching is meaningless for such images, so they are routed
    to grayscale themes by neutrality instead of color distance."""
    return image_mean_chroma(dominants) < chroma_floor


def theme_is_neutral(theme_labs: list[tuple[float, float, float]],
                     chroma_floor: float = 12.0) -> bool:
    """True if every palette color is near-neutral (a grayscale theme).

    Empty palette is not neutral — there is nothing to match."""
    return bool(theme_labs) and all(lab_chroma(lab) < chroma_floor for lab in theme_labs)


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


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
DEFAULT_STOCK = os.path.expanduser("~/.local/share/omarchy/themes")
DEFAULT_USER = os.path.expanduser("~/.config/omarchy/themes")
DEFAULT_SOURCE = os.path.expanduser("~/Wallpapers")
REPO_BG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "features/wallpapers/.config/omarchy/backgrounds")
CONFIG_BG = os.path.expanduser("~/.config/omarchy/backgrounds")


def _list_images(source: str) -> list[str]:
    return [os.path.join(source, f) for f in sorted(os.listdir(source))
            if f.lower().endswith(IMAGE_EXTS)]


def curate(source, stock_dir, user_dir, repo_bg_dir, config_bg_dir,
           min_ratio=1.0, threshold=12.0, k=8, assume_yes=False,
           max_hues=4, top_colors=3) -> dict[str, list[str]]:
    if not os.path.isdir(source):
        print(f"ERROR: source folder not found: {source}", file=sys.stderr)
        sys.exit(1)
    themes = load_themes(stock_dir, user_dir)
    if not themes:
        print("ERROR: no theme palettes found", file=sys.stderr)
        sys.exit(1)

    assignments: dict[str, list[str]] = {slug: [] for slug in themes}
    dropped = filtered = polychrome = 0
    for img in _list_images(source):
        try:
            with Image.open(img) as im:
                w, h = im.size
            if not passes_ratio(w, h, min_ratio):
                filtered += 1
                continue
            doms = dominant_colors(img, k=k)
        except Exception as e:  # unreadable / truncated image
            print(f"WARN: skipping {img}: {e}", file=sys.stderr)
            continue
        # Reject "matches everything" images (rainbow, neon) before scoring.
        if is_polychrome(doms, max_hues=max_hues):
            polychrome += 1
            continue
        img_neutral = image_is_neutral(doms)
        matched = False
        for slug, labs in themes.items():
            # Grayscale images go only to grayscale themes (and vice versa);
            # color distance between two near-grays is meaningless lightness noise.
            if theme_is_neutral(labs) != img_neutral:
                continue
            if img_neutral:
                assignments[slug].append(img)
                matched = True
            elif score_image_strict(doms, labs, top_n=top_colors) <= threshold:
                assignments[slug].append(img)
                matched = True
        if not matched:
            dropped += 1

    print(f"\nFiltered (ratio < {min_ratio}): {filtered}")
    print(f"Polychrome (>{max_hues} hue sectors): {polychrome}")
    print(f"Dropped (no theme <= {threshold}): {dropped}\n")
    for slug in sorted(assignments):
        print(f"  {slug:<18} {len(assignments[slug])}")
    if not assume_yes:
        if input("\nWrite these symlinks? [y/N] ").strip().lower() != "y":
            print("Aborted.")
            return assignments

    write_matches(repo_bg_dir, assignments)
    n = relink(repo_bg_dir, config_bg_dir)
    print(f"Done: {n} theme(s) linked into {config_bg_dir}")
    return assignments


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Match wallpapers to omarchy themes by color.")
    ap.add_argument("--relink", action="store_true", help="recreate ~/.config dir-symlinks only")
    ap.add_argument("--unlink", action="store_true", help="remove ~/.config dir-symlinks")
    ap.add_argument("--source", help="wallpaper folder (default ~/Wallpapers or prompt)")
    ap.add_argument("--min-ratio", type=float, default=1.0)
    ap.add_argument("--threshold", type=float, default=12.0,
                    help="max CIEDE2000 a theme may be from any top color (lower = stricter)")
    ap.add_argument("--colors", type=int, default=8, help="dominant colors to extract per image")
    ap.add_argument("--top-colors", type=int, default=3,
                    help="how many of the most prominent colors the theme must cover")
    ap.add_argument("--max-hues", type=int, default=4,
                    help="reject images spread across more than this many hue sectors")
    ap.add_argument("--yes", action="store_true", help="skip the dry-run confirmation")
    args = ap.parse_args(argv)

    if args.relink:
        n = relink(REPO_BG, CONFIG_BG)
        print(f"Relinked {n} theme(s).")
        return 0
    if args.unlink:
        n = unlink(REPO_BG, CONFIG_BG)
        print(f"Unlinked {n} theme(s).")
        return 0

    source = args.source
    if not source:
        entered = input(f"Wallpaper folder [{DEFAULT_SOURCE}]: ").strip()
        source = os.path.expanduser(entered) if entered else DEFAULT_SOURCE
    curate(source=source, stock_dir=DEFAULT_STOCK, user_dir=DEFAULT_USER,
           repo_bg_dir=REPO_BG, config_bg_dir=CONFIG_BG,
           min_ratio=args.min_ratio, threshold=args.threshold,
           k=args.colors, assume_yes=args.yes,
           max_hues=args.max_hues, top_colors=args.top_colors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
