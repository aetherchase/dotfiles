# Wallpaper → Theme Matcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Curate a wallpaper folder into omarchy's per-theme background rotation by color affinity — each landscape/square wallpaper is symlinked into every theme whose `colors.toml` palette it resembles; nothing binary enters git.

**Architecture:** One importable Python script `match_wallpapers.py` at the repo root (beside `apply.sh`). Pure functions (ratio filter, sRGB→Lab, CIEDE2000, palette parse, dominant-color extraction, scoring) are unit-tested; FS functions (relink/unlink/write) are tested in tmpdirs. The live `~/.config/omarchy/backgrounds/<slug>` dir-symlinks are created directly by the script (stow aborts on absolute symlinks); the `wallpapers` package tracks only `.gitkeep`. `apply.sh` calls `--relink`/`--unlink`; curation is manual.

**Tech Stack:** Python 3.14, Pillow 12.2 (present), `tomllib` (stdlib), `unittest` (stdlib, run via `python3 -m unittest`). No new dependencies.

---

## File Structure

- Create: `match_wallpapers.py` — the whole tool (pure fns + FS fns + CLI).
- Create: `tests/test_match_wallpapers.py` — unittest suite.
- Modify: `apply.sh` — swap the `link-omarchy-wallpapers.sh` calls for `match_wallpapers.py --relink` / `--unlink`.
- Delete: `link-omarchy-wallpapers.sh` — superseded.
- Modify: `CLAUDE.md` — document the `wallpapers` package + matcher.
- Already in place (prior work, do not redo): `features/wallpapers/.config/omarchy/backgrounds/.gitkeep`, `.gitignore` rules, `features.conf` entry, `features/.stow-local-ignore` `\.gitkeep` line.

**All test commands run from the repo root** (`cd ~/dotfiles`) so `import match_wallpapers` resolves.

---

### Task 1: Aspect-ratio filter

**Files:**
- Create: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_match_wallpapers.py
import unittest
import match_wallpapers as mw


class TestRatio(unittest.TestCase):
    def test_landscape_kept(self):
        self.assertTrue(mw.passes_ratio(2560, 1440, 1.0))

    def test_square_kept_at_default(self):
        self.assertTrue(mw.passes_ratio(1000, 1000, 1.0))

    def test_portrait_rejected(self):
        self.assertFalse(mw.passes_ratio(1080, 1920, 1.0))

    def test_custom_min_ratio(self):
        # 4:3 = 1.333 rejected when we demand >= 1.5
        self.assertFalse(mw.passes_ratio(1600, 1200, 1.5))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'match_wallpapers'` (or `AttributeError: passes_ratio`).

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
"""Curate a wallpaper folder into omarchy per-theme background dirs by color
affinity. See docs/superpowers/specs/2026-06-16-wallpaper-theme-matcher-design.md."""
from __future__ import annotations


def passes_ratio(width: int, height: int, min_ratio: float) -> bool:
    """True if width/height >= min_ratio (default caller passes 1.0 to drop portrait)."""
    if height <= 0:
        return False
    return (width / height) >= min_ratio
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): aspect-ratio filter for matcher"
```

---

### Task 2: sRGB → CIE Lab conversion

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
class TestLab(unittest.TestCase):
    def test_white(self):
        L, a, b = mw.srgb_to_lab((255, 255, 255))
        self.assertAlmostEqual(L, 100.0, places=1)
        self.assertAlmostEqual(a, 0.0, places=1)
        self.assertAlmostEqual(b, 0.0, places=1)

    def test_black(self):
        L, a, b = mw.srgb_to_lab((0, 0, 0))
        self.assertAlmostEqual(L, 0.0, places=2)

    def test_red(self):
        L, a, b = mw.srgb_to_lab((255, 0, 0))
        self.assertAlmostEqual(L, 53.24, places=1)
        self.assertAlmostEqual(a, 80.09, places=1)
        self.assertAlmostEqual(b, 67.20, places=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestLab -v`
Expected: FAIL — `AttributeError: module 'match_wallpapers' has no attribute 'srgb_to_lab'`.

- [ ] **Step 3: Write minimal implementation**

Add near the top of `match_wallpapers.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestLab -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): sRGB to CIE Lab conversion"
```

---

### Task 3: CIEDE2000 color distance

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

Reference values from Sharma et al. CIEDE2000 test data.

```python
class TestCiede2000(unittest.TestCase):
    def test_identity(self):
        self.assertAlmostEqual(mw.ciede2000((50, 2.5, 0), (50, 2.5, 0)), 0.0, places=4)

    def test_sharma_pair_1(self):
        d = mw.ciede2000((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485))
        self.assertAlmostEqual(d, 2.0425, places=4)

    def test_sharma_pair_2(self):
        d = mw.ciede2000((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485))
        self.assertAlmostEqual(d, 2.8615, places=4)

    def test_sharma_pair_3(self):
        d = mw.ciede2000((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485))
        self.assertAlmostEqual(d, 3.4412, places=4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestCiede2000 -v`
Expected: FAIL — `AttributeError: ... 'ciede2000'`.

- [ ] **Step 3: Write minimal implementation**

Add to `match_wallpapers.py` (and `import math` at the top of the file):

```python
import math


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestCiede2000 -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): CIEDE2000 color distance"
```

---

### Task 4: Parse a theme `colors.toml` into the matching palette

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
import tempfile, os


class TestParsePalette(unittest.TestCase):
    SAMPLE = (
        'accent = "#7fbbb3"\n'
        'background = "#2d353b"\n'
        'foreground = "#d3c6aa"\n'
        'color0 = "#475258"\n'
        'color1 = "#e67e80"\n'
        'color2 = "#a7c080"\n'
        'color3 = "#dbbc7f"\n'
        'color4 = "#7fbbb3"\n'
        'color5 = "#d699b6"\n'
        'color6 = "#83c092"\n'
        'color7 = "#d3c6aa"\n'
    )

    def test_hex_to_rgb(self):
        self.assertEqual(mw.hex_to_rgb("#7fbbb3"), (127, 187, 179))

    def test_parse_uses_match_subset(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "colors.toml")
            with open(p, "w") as f:
                f.write(self.SAMPLE)
            rgbs = mw.parse_palette(p)
        # background, accent, color1..6 present in sample => 8 entries
        # (color9..14 absent in this sample, simply skipped)
        self.assertIn((45, 53, 59), rgbs)      # background
        self.assertIn((127, 187, 179), rgbs)   # accent
        self.assertIn((230, 126, 128), rgbs)   # color1
        self.assertNotIn((71, 82, 88), rgbs)   # color0 excluded
        self.assertEqual(len(rgbs), 8)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestParsePalette -v`
Expected: FAIL — `AttributeError: ... 'hex_to_rgb'`.

- [ ] **Step 3: Write minimal implementation**

Add to `match_wallpapers.py` (and `import tomllib` at top):

```python
import tomllib

# Hue-bearing palette keys; color0/7/8/15 (near black/white) are skipped.
PALETTE_KEYS = (
    "background", "accent",
    "color1", "color2", "color3", "color4", "color5", "color6",
    "color9", "color10", "color11", "color12", "color13", "color14",
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestParsePalette -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): parse theme colors.toml palette"
```

---

### Task 5: Dominant-color extraction (Pillow median-cut)

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
from PIL import Image


class TestDominant(unittest.TestCase):
    def _png(self, d, name, color, size=(64, 64)):
        p = os.path.join(d, name)
        Image.new("RGB", size, color).save(p)
        return p

    def test_solid_red(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._png(d, "red.png", (255, 0, 0))
            doms = mw.dominant_colors(p, k=5)
        self.assertEqual(len(doms), 1)            # only one color present
        rgb, weight = doms[0]
        self.assertEqual(rgb, (255, 0, 0))
        self.assertAlmostEqual(weight, 1.0, places=3)

    def test_weights_sum_to_one(self):
        with tempfile.TemporaryDirectory() as d:
            img = Image.new("RGB", (100, 100), (0, 0, 255))
            for x in range(100):           # half blue, half green
                for y in range(50):
                    img.putpixel((x, y), (0, 255, 0))
            p = os.path.join(d, "split.png")
            img.save(p)
            doms = mw.dominant_colors(p, k=5)
        self.assertAlmostEqual(sum(w for _, w in doms), 1.0, places=3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestDominant -v`
Expected: FAIL — `AttributeError: ... 'dominant_colors'`.

- [ ] **Step 3: Write minimal implementation**

Add to `match_wallpapers.py` (and `from PIL import Image` at top):

```python
from PIL import Image


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestDominant -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): dominant-color extraction via Pillow quantize"
```

---

### Task 6: Image↔theme score + threshold join

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
class TestScore(unittest.TestCase):
    def test_green_image_closer_to_green_theme(self):
        green_doms = [((0, 200, 0), 1.0)]
        green_theme = [mw.srgb_to_lab((10, 190, 10)), mw.srgb_to_lab((40, 40, 40))]
        red_theme = [mw.srgb_to_lab((200, 10, 10)), mw.srgb_to_lab((40, 40, 40))]
        s_green = mw.score_image(green_doms, green_theme)
        s_red = mw.score_image(green_doms, red_theme)
        self.assertLess(s_green, s_red)

    def test_score_is_weighted_min_distance(self):
        doms = [((0, 200, 0), 0.5), ((0, 0, 200), 0.5)]
        theme = [mw.srgb_to_lab((0, 200, 0))]  # exactly matches the green dom
        s = mw.score_image(doms, theme)
        # green term contributes ~0, blue term contributes 0.5 * dist(blue,green)
        blue_dist = mw.ciede2000(mw.srgb_to_lab((0, 0, 200)), theme[0])
        self.assertAlmostEqual(s, 0.5 * blue_dist, places=3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestScore -v`
Expected: FAIL — `AttributeError: ... 'score_image'`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestScore -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): weighted image-theme palette score"
```

---

### Task 7: Load all theme palettes (stock + user)

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
class TestLoadThemes(unittest.TestCase):
    def _theme(self, root, slug, accent="#7fbbb3"):
        d = os.path.join(root, slug)
        os.makedirs(d)
        with open(os.path.join(d, "colors.toml"), "w") as f:
            f.write(f'accent = "{accent}"\nbackground = "#2d353b"\ncolor1 = "#e67e80"\n')

    def test_loads_stock_and_user(self):
        with tempfile.TemporaryDirectory() as stock, tempfile.TemporaryDirectory() as user:
            self._theme(stock, "everforest")
            self._theme(user, "aether")
            themes = mw.load_themes(stock, user)
        self.assertEqual(set(themes), {"everforest", "aether"})
        self.assertTrue(all(len(labs) == 3 for labs in themes.values()))

    def test_missing_dirs_ok(self):
        themes = mw.load_themes("/no/such/stock", "/no/such/user")
        self.assertEqual(themes, {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestLoadThemes -v`
Expected: FAIL — `AttributeError: ... 'load_themes'`.

- [ ] **Step 3: Write minimal implementation**

Add to `match_wallpapers.py` (and `import os` at top):

```python
import os


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestLoadThemes -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): load stock + user theme palettes"
```

---

### Task 8: Write matches as repo per-theme symlinks

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
class TestWriteMatches(unittest.TestCase):
    def test_writes_symlinks_and_clears_old(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as repo_bg:
            a = os.path.join(src, "a.jpg"); open(a, "w").close()
            b = os.path.join(src, "b.jpg"); open(b, "w").close()
            # pre-existing stale theme dir that must be cleared
            os.makedirs(os.path.join(repo_bg, "stale"))
            open(os.path.join(repo_bg, ".gitkeep"), "w").close()

            mw.write_matches(repo_bg, {"everforest": [a, b], "nord": [a]})

            ef = os.path.join(repo_bg, "everforest")
            self.assertTrue(os.path.islink(os.path.join(ef, "a.jpg")))
            self.assertEqual(os.readlink(os.path.join(ef, "a.jpg")), a)
            self.assertEqual(sorted(os.listdir(ef)), ["a.jpg", "b.jpg"])
            self.assertEqual(os.listdir(os.path.join(repo_bg, "nord")), ["a.jpg"])
            self.assertFalse(os.path.exists(os.path.join(repo_bg, "stale")))
            self.assertTrue(os.path.exists(os.path.join(repo_bg, ".gitkeep")))  # keeper survives
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestWriteMatches -v`
Expected: FAIL — `AttributeError: ... 'write_matches'`.

- [ ] **Step 3: Write minimal implementation**

Add to `match_wallpapers.py` (and `import shutil` at top):

```python
import shutil


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestWriteMatches -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): write matches as repo per-theme symlinks"
```

---

### Task 9: relink / unlink the live `~/.config` dir-symlinks

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

```python
class TestRelink(unittest.TestCase):
    def test_relink_links_populated_only_and_prunes(self):
        with tempfile.TemporaryDirectory() as repo_bg, tempfile.TemporaryDirectory() as cfg:
            os.makedirs(os.path.join(repo_bg, "everforest"))
            open(os.path.join(repo_bg, "everforest", "a.jpg"), "w").close()
            os.makedirs(os.path.join(repo_bg, "empty"))   # no files -> skipped
            # stale live symlink whose repo dir no longer qualifies -> pruned
            os.symlink(os.path.join(repo_bg, "empty"), os.path.join(cfg, "empty"))

            mw.relink(repo_bg, cfg)

            ef = os.path.join(cfg, "everforest")
            self.assertTrue(os.path.islink(ef))
            self.assertEqual(os.readlink(ef), os.path.join(repo_bg, "everforest"))
            self.assertFalse(os.path.lexists(os.path.join(cfg, "empty")))  # pruned

    def test_unlink_removes_only_symlinks(self):
        with tempfile.TemporaryDirectory() as repo_bg, tempfile.TemporaryDirectory() as cfg:
            os.makedirs(os.path.join(repo_bg, "everforest"))
            open(os.path.join(repo_bg, "everforest", "a.jpg"), "w").close()
            os.symlink(os.path.join(repo_bg, "everforest"), os.path.join(cfg, "everforest"))
            os.makedirs(os.path.join(cfg, "realdir"))      # must be left alone

            mw.unlink(repo_bg, cfg)

            self.assertFalse(os.path.lexists(os.path.join(cfg, "everforest")))
            self.assertTrue(os.path.isdir(os.path.join(cfg, "realdir")))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestRelink -v`
Expected: FAIL — `AttributeError: ... 'relink'`.

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestRelink -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): relink/unlink live config dir-symlinks"
```

---

### Task 10: CLI + curate orchestration

**Files:**
- Modify: `match_wallpapers.py`
- Test: `tests/test_match_wallpapers.py`

- [ ] **Step 1: Write the failing test**

`curate()` is the orchestration; test it end-to-end with generated solid PNGs and two fake themes, writing into tmp dirs (no prompts: pass `assume_yes=True`).

```python
class TestCurate(unittest.TestCase):
    def _theme(self, root, slug, *hexes):
        d = os.path.join(root, slug); os.makedirs(d)
        body = "".join(f'color{i+1} = "{h}"\n' for i, h in enumerate(hexes))
        with open(os.path.join(d, "colors.toml"), "w") as f:
            f.write('background = "#202020"\n' + body)

    def test_end_to_end_assigns_by_color(self):
        with tempfile.TemporaryDirectory() as src, \
             tempfile.TemporaryDirectory() as stock, \
             tempfile.TemporaryDirectory() as repo_bg, \
             tempfile.TemporaryDirectory() as cfg:
            Image.new("RGB", (160, 90), (0, 200, 0)).save(os.path.join(src, "green.png"))
            Image.new("RGB", (160, 90), (200, 0, 0)).save(os.path.join(src, "red.png"))
            Image.new("RGB", (90, 160), (0, 200, 0)).save(os.path.join(src, "tall.png"))  # portrait -> dropped
            self._theme(stock, "forest", "#10c010", "#1faa1f")
            self._theme(stock, "ember", "#c01010", "#aa1f1f")

            mw.curate(source=src, stock_dir=stock, user_dir=os.path.join(stock, "none"),
                      repo_bg_dir=repo_bg, config_bg_dir=cfg,
                      min_ratio=1.0, threshold=18.0, k=5, assume_yes=True)

            forest = os.listdir(os.path.join(repo_bg, "forest"))
            ember = os.listdir(os.path.join(repo_bg, "ember"))
            self.assertIn("green.png", forest)
            self.assertNotIn("red.png", forest)
            self.assertIn("red.png", ember)
            self.assertNotIn("tall.png", forest + ember)        # portrait filtered
            self.assertTrue(os.path.islink(os.path.join(cfg, "forest")))  # relinked
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dotfiles && python3 -m unittest tests.test_match_wallpapers.TestCurate -v`
Expected: FAIL — `AttributeError: ... 'curate'`.

- [ ] **Step 3: Write minimal implementation**

Add to `match_wallpapers.py` (and `import argparse`, `import sys` at top):

```python
import argparse
import sys

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
           min_ratio=1.0, threshold=18.0, k=5, assume_yes=False) -> dict[str, list[str]]:
    if not os.path.isdir(source):
        print(f"ERROR: source folder not found: {source}", file=sys.stderr)
        sys.exit(1)
    themes = load_themes(stock_dir, user_dir)
    if not themes:
        print("ERROR: no theme palettes found", file=sys.stderr)
        sys.exit(1)

    assignments: dict[str, list[str]] = {slug: [] for slug in themes}
    dropped = filtered = 0
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
        matched = False
        for slug, labs in themes.items():
            if score_image(doms, labs) <= threshold:
                assignments[slug].append(img)
                matched = True
        if not matched:
            dropped += 1

    print(f"\nFiltered (ratio < {min_ratio}): {filtered}")
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
    ap.add_argument("--threshold", type=float, default=18.0)
    ap.add_argument("--colors", type=int, default=5)
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
           k=args.colors, assume_yes=args.yes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run full test suite**

Run: `cd ~/dotfiles && python3 -m unittest discover -s tests -v`
Expected: PASS (all tasks' tests).

- [ ] **Step 5: Make executable + commit**

```bash
cd ~/dotfiles
chmod +x match_wallpapers.py
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): CLI + curate orchestration"
```

---

### Task 11: Wire into apply.sh; remove old script

**Files:**
- Modify: `apply.sh` (the wallpapers pre-stow hook and the deselection-loop hook added in prior work)
- Delete: `link-omarchy-wallpapers.sh`

- [ ] **Step 1: Replace the pre-stow generate hook**

In `apply.sh`, find the block added earlier:

```bash
if [ -n "${seen[wallpapers]:-}" ]; then
    "$DOTFILES_DIR/link-omarchy-wallpapers.sh" || true
fi
```

Replace its body with the relink call (curation stays manual):

```bash
if [ -n "${seen[wallpapers]:-}" ]; then
    # Recreate live ~/.config dir-symlinks from whatever the matcher curated.
    # Curation itself (color matching) is a manual step: ./match_wallpapers.py
    python3 "$DOTFILES_DIR/match_wallpapers.py" --relink || true
fi
```

- [ ] **Step 2: Replace the deselection-loop hook**

In `apply.sh`, find:

```bash
    [ "$pkg" = wallpapers ] && "$DOTFILES_DIR/link-omarchy-wallpapers.sh" --unlink || true
```

Replace with:

```bash
    [ "$pkg" = wallpapers ] && python3 "$DOTFILES_DIR/match_wallpapers.py" --unlink || true
```

- [ ] **Step 3: Delete the superseded script**

```bash
cd ~/dotfiles && git rm --cached link-omarchy-wallpapers.sh 2>/dev/null; rm -f link-omarchy-wallpapers.sh
```

(`git rm --cached` only matters if it was ever staged; the `rm -f` removes the working file regardless.)

- [ ] **Step 4: Verify apply.sh parses + relink runs**

Run: `cd ~/dotfiles && bash -n apply.sh && python3 match_wallpapers.py --relink`
Expected: no syntax error; prints `Relinked N theme(s).` (N may be 0 before any curation).

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add apply.sh
git commit -m "feat(wallpapers): wire matcher into apply.sh; drop link-omarchy-wallpapers.sh"
```

---

### Task 12: Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the package to the Feature packages table**

In `CLAUDE.md`, in the `## Feature packages` table, add a row after `keybind-lookup`:

```markdown
| `wallpapers` | color-matched wallpaper curation: symlinks landscape pics into per-theme omarchy background dirs by palette affinity | yes |
```

- [ ] **Step 2: Add an ownership-boundary row**

In the ownership table (the one listing `keybind-lookup` / `system/`), add:

```markdown
| `match_wallpapers.py` (repo root) | wallpapers | curate tool: filters wallpapers by aspect ratio, scores each against every theme's `colors.toml` palette (CIEDE2000), symlinks matches into `features/wallpapers/.config/omarchy/backgrounds/<theme>/` (gitignored) and dir-symlinks each into `~/.config/omarchy/backgrounds/`. `--relink`/`--unlink` used by apply.sh; bare invocation = interactive curate. |
```

- [ ] **Step 3: Add a References bullet**

Add under `## References`:

```markdown
- **wallpapers** (`match_wallpapers.py`, package `wallpapers`): `omarchy theme bg next` lists `find -L ~/.config/omarchy/backgrounds/$THEME_NAME/`, so each theme's user-backgrounds dir is a symlink into the repo (gitignored), and inside it each wallpaper is a symlink to the source folder — `find -L` resolves both hops. Stow can't relay absolute symlinks (it aborts), so the matcher creates the `~/.config` dir-symlinks directly; the package tracks only `.gitkeep` (stow-ignored via `features/.stow-local-ignore`). Matching: Pillow median-cut dominant colors vs the theme palette (`background`/`accent`/`color1-6,9-14`, CIEDE2000 ≤ `--threshold`, default 18); aspect filter `--min-ratio` default 1.0 drops portrait/mobile. Re-run after adding wallpapers or themes: `./match_wallpapers.py`. Spec/plan: `docs/superpowers/`. |
```

- [ ] **Step 4: Verify no broken table syntax**

Run: `cd ~/dotfiles && grep -n "wallpapers" CLAUDE.md`
Expected: shows the new rows.

- [ ] **Step 5: Commit**

```bash
cd ~/dotfiles
git add CLAUDE.md
git commit -m "docs(wallpapers): document color-matching wallpaper matcher"
```

---

## Self-Review

**Spec coverage:**
- Aspect filter (min-ratio, drop portrait) → Task 1 + Task 10. ✓
- sRGB→Lab, CIEDE2000 → Tasks 2, 3. ✓
- Palette parse (subset bg/accent/color1-6,9-14) → Task 4. ✓
- Dominant colors (Pillow quantize, weights) → Task 5. ✓
- Score + multi-theme threshold join, drop no-match → Task 6 + Task 10. ✓
- Load stock+user themes → Task 7. ✓
- Write gitignored repo per-theme symlinks → Task 8. ✓
- relink/unlink live ~/.config dir-symlinks (own symlinks only) → Task 9. ✓
- Dry-run table + confirm + flags + interactive source prompt → Task 10. ✓
- apply.sh `--relink`/`--unlink`, delete old script → Task 11. ✓
- Docs → Task 12. ✓
- `.gitignore`/`.stow-local-ignore`/`features.conf`/`.gitkeep` → prior work, noted in File Structure. ✓

**Placeholder scan:** none — every code step is complete.

**Type consistency:** function names used across tasks — `passes_ratio`, `srgb_to_lab`, `ciede2000`, `hex_to_rgb`, `parse_palette`, `dominant_colors`, `score_image`, `load_themes`, `write_matches`, `relink`, `unlink`, `curate`, `main` — all defined where first used and called consistently. `assignments` is `dict[slug, list[abs_path]]` throughout. `themes` is `dict[slug, list[lab]]` in Tasks 7/10.

**Note on imports:** several tasks add a top-of-file `import` (`math`, `tomllib`, `os`, `shutil`, `argparse`, `sys`, `from PIL import Image`). When implementing, keep one import block at the top; re-adding an existing import is a no-op to fix if duplicated.
