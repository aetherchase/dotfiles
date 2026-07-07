# Muted + hue-family matcher paths — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover muted, comet-accent, and dark/earthy chromatic `do` wallpapers in `match_wallpapers.py` without new false positives, so the labeled-fixture eval reaches 100% / 0-FP on both everforest and gruvbox.

**Architecture:** `theme_matches_image` keeps its gate order and gains four decision paths. The chromatic branch: **strict** (unchanged CIEDE worst-of-top-N) then **hue-family** (dominant weight hue-aligned to the palette; per-theme `lenient` only). The muted branch: neutral routing (unchanged), then **cast** (whole-image color tint) and **accent** (spatially concentrated colored blob), both fed by a once-per-image `ImageFeatures` computed from a numpy pixel pass. Per-theme leniency comes from a `THEME_OVERRIDES` map (curate) and each label file's `params.lenient` (eval/gallery).

**Tech Stack:** Python 3.11+ (`tomllib`), Pillow, numpy (vectorized Lab pass), `unittest`.

## Global Constraints

- Python **3.11+** (uses `tomllib`). numpy is a required dependency (installed 2.4.6); Pillow already implicit.
- `theme_matches_image` stays the **single** per-(image, theme) decision — `curate()`, `tests/test_labeled_fixtures.py`, and `tools/gen_gallery.py` all route through it.
- The 6 existing `TestThemeMatches` tests call it with synthetic `dominants` and **no** image/features; they must keep passing **unchanged** (`features=None`, `lenient=False` → today's dominants-only behavior).
- Do **not** commit real wallpapers. The eval references originals by `source_dir/basename`; missing originals skip, not fail.
- Tuned parameter defaults (validated on both fixtures): `CAST_C_MIN=4.0`, `CAST_TOL=22.0`, `ACC_MONO_MAX=8.0`, `CONC_MIN=0.25`, `ACC_TOL=35.0`, `ACCENT_CHROMA_FLOOR=18.0`, `FEATURE_RES=1000`, `ACCENT_GRID=24`, `HUE_COV_MIN=0.45`, `HUE_TOL=20.0`. Neutral floor stays `12.0`; strict `threshold` default stays `12.0`.
- Match existing style: module-level pure functions, type hints, docstrings; run tests with `python -m unittest`.

## File Structure

- `match_wallpapers.py` (repo root) — add constants, `import numpy as np`, hue helpers, `on_hue_weight`, `ImageFeatures` + `image_features`, extend `theme_matches_image`, add `THEME_OVERRIDES`, rewire `curate()`.
- `tests/test_match_wallpapers.py` — new test classes for hue helpers, features, and the new decision paths; keep all existing tests green.
- `tests/test_labeled_fixtures.py` — `evaluate()` computes features + reads `params.lenient`.
- `tests/fixtures/labels/everforest.json`, `gruvbox.json` — add `params.lenient` (false / true).
- `tools/gen_gallery.py` — compute features + per-theme lenient in `render()`.
- `CLAUDE.md` — document numpy dep, the four paths, per-theme `lenient` / `THEME_OVERRIDES`.

---

### Task 1: Hue helpers + on-hue-weight (hue-family core)

**Files:**
- Modify: `match_wallpapers.py` (add constants near line 20; add functions after `lab_hue`, ~line 165)
- Test: `tests/test_match_wallpapers.py` (new class `TestHueHelpers`)

**Interfaces:**
- Consumes: existing `srgb_to_lab`, `lab_chroma`, `lab_hue`.
- Produces:
  - `hue_distance(h1: float, h2: float) -> float`
  - `nearest_hue_distance(hue: float, hues: list[float]) -> float` (`inf` if `hues` empty)
  - `palette_cast_hues(theme_labs, chroma_floor: float = 3.0) -> list[float]`
  - `palette_accent_hues(theme_labs, chroma_floor: float = 12.0) -> list[float]`
  - `on_hue_weight(dominants, accent_hues, hue_tol: float = HUE_TOL, chroma_floor: float = 12.0) -> float`
  - constants `HUE_TOL = 20.0`, `HUE_COV_MIN = 0.45`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_match_wallpapers.py`:

```python
class TestHueHelpers(unittest.TestCase):
    def test_hue_distance_wraps(self):
        self.assertAlmostEqual(mw.hue_distance(350, 10), 20.0)
        self.assertAlmostEqual(mw.hue_distance(10, 350), 20.0)
        self.assertAlmostEqual(mw.hue_distance(100, 100), 0.0)
        self.assertAlmostEqual(mw.hue_distance(0, 190), 170.0)

    def test_nearest_hue_distance_empty_is_inf(self):
        self.assertEqual(mw.nearest_hue_distance(120, []), float("inf"))
        self.assertAlmostEqual(mw.nearest_hue_distance(120, [10, 125, 300]), 5.0)

    def test_palette_hue_extractors_filter_by_chroma(self):
        labs = [mw.srgb_to_lab(mw.hex_to_rgb(h))
                for h in ("#2d353b", "#a7c080", "#7fbbb3")]  # dark-tint bg + green + teal
        # bg chroma ~5 -> in cast hues (>=3) but not accent hues (>=12)
        self.assertEqual(len(mw.palette_cast_hues(labs)), 3)
        self.assertEqual(len(mw.palette_accent_hues(labs)), 2)

    def test_on_hue_weight_counts_aligned_chromatic_weight(self):
        # green dom (aligned, chromatic) + gray dom (chroma<12, ignored) + red dom (wrong hue)
        doms = [((60, 160, 60), 0.5), ((128, 128, 128), 0.3), ((190, 0, 0), 0.2)]
        green_hues = [mw.lab_hue(mw.srgb_to_lab(mw.hex_to_rgb("#a7c080")))]  # ~123
        self.assertAlmostEqual(mw.on_hue_weight(doms, green_hues), 0.5, places=3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_match_wallpapers.TestHueHelpers -v`
Expected: FAIL — `AttributeError: module 'match_wallpapers' has no attribute 'hue_distance'`

- [ ] **Step 3: Write minimal implementation**

In `match_wallpapers.py`, add constants after the `PALETTE_KEYS` block (~line 20):

```python
HUE_TOL = 20.0
HUE_COV_MIN = 0.45
```

Add after `lab_hue` (~line 165):

```python
def hue_distance(h1: float, h2: float) -> float:
    """Smallest angular distance between two hues in degrees [0, 180]."""
    d = abs(h1 - h2) % 360.0
    return min(d, 360.0 - d)


def nearest_hue_distance(hue: float, hues: list[float]) -> float:
    """Distance from `hue` to the closest hue in `hues` (inf if empty)."""
    return min((hue_distance(hue, h) for h in hues), default=float("inf"))


def palette_cast_hues(theme_labs: list[tuple[float, float, float]],
                      chroma_floor: float = 3.0) -> list[float]:
    """Hues of palette colors carrying at least faint chroma (incl. a tinted bg)."""
    return [lab_hue(lab) for lab in theme_labs if lab_chroma(lab) >= chroma_floor]


def palette_accent_hues(theme_labs: list[tuple[float, float, float]],
                        chroma_floor: float = 12.0) -> list[float]:
    """Hues of the palette's genuinely chromatic accent colors."""
    return [lab_hue(lab) for lab in theme_labs if lab_chroma(lab) >= chroma_floor]


def on_hue_weight(dominants: list[tuple[tuple[int, int, int], float]],
                  accent_hues: list[float], hue_tol: float = HUE_TOL,
                  chroma_floor: float = 12.0) -> float:
    """Fraction of dominant weight that is chromatic (chroma >= chroma_floor) AND
    hue-aligned (within hue_tol) to some palette accent hue.

    Measures how much of the image sits in the theme's hue family — the signal a
    dark/earthy nature scene shares with the palette even when no single dominant
    is close under CIEDE2000."""
    total = 0.0
    for rgb, weight in dominants:
        lab = srgb_to_lab(rgb)
        if (lab_chroma(lab) >= chroma_floor
                and nearest_hue_distance(lab_hue(lab), accent_hues) <= hue_tol):
            total += weight
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_match_wallpapers.TestHueHelpers -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): hue helpers + on-hue-weight for hue-family matching"
```

---

### Task 2: Per-image pixel features (`ImageFeatures` / `image_features`)

**Files:**
- Modify: `match_wallpapers.py` (add `from dataclasses import dataclass`, `import numpy as np`; add constants; add `_lab_channels`, `ImageFeatures`, `image_features` after `dominant_colors`, ~line 140)
- Test: `tests/test_match_wallpapers.py` (new class `TestImageFeatures`)

**Interfaces:**
- Consumes: existing `dominant_colors`.
- Produces:
  - `@dataclass(frozen=True) class ImageFeatures` with fields `dominants: list[tuple[tuple[int,int,int], float]]`, `cast_chroma: float`, `cast_hue: float`, `accent_concentration: float`, `accent_hue: float`.
  - `image_features(path, k: int = 8, feature_res: int = FEATURE_RES, accent_chroma_floor: float = ACCENT_CHROMA_FLOOR, accent_grid: int = ACCENT_GRID) -> ImageFeatures`
  - constants `FEATURE_RES = 1000`, `ACCENT_CHROMA_FLOOR = 18.0`, `ACCENT_GRID = 24`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_match_wallpapers.py`:

```python
class TestImageFeatures(unittest.TestCase):
    def test_solid_green_has_cast_and_no_blob(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "green.png")
            Image.new("RGB", (200, 200), (0, 160, 0)).save(p)
            f = mw.image_features(p, k=5)
        self.assertGreater(f.cast_chroma, 20.0)          # strong green tint
        self.assertTrue(110 < f.cast_hue < 160)          # green-ish hue
        self.assertLess(f.accent_concentration, 0.1)     # uniform -> not a blob

    def test_small_red_blob_on_black_is_concentrated(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "blob.png")
            img = Image.new("RGB", (480, 480), (0, 0, 0))
            for y in range(2, 17):                       # 15x15 saturated red square, one grid cell
                for x in range(2, 17):
                    img.putpixel((x, y), (220, 0, 0))
            img.save(p)
            f = mw.image_features(p, k=5)
        self.assertLess(f.cast_chroma, 3.0)              # mostly black -> weak cast
        self.assertGreater(f.accent_concentration, 0.9)  # all accent px in one cell
        self.assertTrue(20 < f.accent_hue < 50)          # red-ish hue
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_match_wallpapers.TestImageFeatures -v`
Expected: FAIL — `AttributeError: module 'match_wallpapers' has no attribute 'image_features'`

- [ ] **Step 3: Write minimal implementation**

In `match_wallpapers.py`, extend the imports near the top:

```python
import math
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass

import numpy as np
from PIL import Image
```

Add constants near the other new constants (~line 20):

```python
FEATURE_RES = 1000
ACCENT_CHROMA_FLOOR = 18.0
ACCENT_GRID = 24
```

Add after `dominant_colors` (~line 140):

```python
def _lab_channels(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized sRGB(uint8 HxWx3) -> CIE Lab (D65); returns (L, a, b) arrays.

    Mirrors srgb_to_lab exactly so pixel-level features match the scalar path."""
    c = arr.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    x /= 0.95047
    z /= 1.08883

    def f(t: np.ndarray) -> np.ndarray:
        return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


@dataclass(frozen=True)
class ImageFeatures:
    """Per-image, theme-independent signals, computed once and reused across themes.

    dominants           : median-cut top-k [(rgb, weight)] (256px thumbnail)
    cast_chroma/cast_hue: magnitude/angle of the whole-image mean (a, b) tint
    accent_concentration: densest-cell share of chromatic pixels (spatial blob-ness)
    accent_hue          : chroma-weighted mean hue of that densest cell
    """
    dominants: list
    cast_chroma: float
    cast_hue: float
    accent_concentration: float
    accent_hue: float


def image_features(path: str, k: int = 8, feature_res: int = FEATURE_RES,
                   accent_chroma_floor: float = ACCENT_CHROMA_FLOOR,
                   accent_grid: int = ACCENT_GRID) -> ImageFeatures:
    """Compute dominants (via dominant_colors) plus the whole-image cast and the
    salient-accent descriptor from one numpy Lab pass at feature_res."""
    doms = dominant_colors(path, k=k)
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((feature_res, feature_res))
        arr = np.asarray(im)
    height, width = arr.shape[0], arr.shape[1]
    _, a, b = _lab_channels(arr)
    chroma = np.hypot(a, b)
    mean_a, mean_b = float(a.mean()), float(b.mean())
    cast_chroma = math.hypot(mean_a, mean_b)
    cast_hue = math.degrees(math.atan2(mean_b, mean_a)) % 360.0

    mask = chroma >= accent_chroma_floor
    n_acc = int(mask.sum())
    accent_concentration = 0.0
    accent_hue = 0.0
    if n_acc:
        ys, xs = np.nonzero(mask)
        cc = chroma[mask]
        hh = np.degrees(np.arctan2(b[mask], a[mask])) % 360.0
        gx = np.minimum(accent_grid - 1, (xs * accent_grid) // width)
        gy = np.minimum(accent_grid - 1, (ys * accent_grid) // height)
        cell = gy * accent_grid + gx
        counts = np.bincount(cell)
        accent_concentration = int(counts.max()) / n_acc
        sel = cell == int(counts.argmax())
        sa = float(np.sum(cc[sel] * np.sin(np.radians(hh[sel]))))
        ca = float(np.sum(cc[sel] * np.cos(np.radians(hh[sel]))))
        accent_hue = math.degrees(math.atan2(sa, ca)) % 360.0

    return ImageFeatures(dominants=doms, cast_chroma=cast_chroma, cast_hue=cast_hue,
                         accent_concentration=accent_concentration, accent_hue=accent_hue)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_match_wallpapers.TestImageFeatures -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): ImageFeatures + numpy cast/accent extraction"
```

---

### Task 3: Extend `theme_matches_image` with the four paths

**Files:**
- Modify: `match_wallpapers.py` (replace `theme_matches_image`, ~lines 233-249; add path-param constants)
- Test: `tests/test_match_wallpapers.py` (new class `TestThemeMatchesPaths`; keep `TestThemeMatches` unchanged)

**Interfaces:**
- Consumes: `is_polychrome`, `image_is_neutral`, `theme_is_neutral`, `score_image_strict`, `image_mean_chroma` (existing); `on_hue_weight`, `palette_accent_hues`, `palette_cast_hues`, `nearest_hue_distance` (Task 1); `ImageFeatures` (Task 2).
- Produces:
  - `theme_matches_image(dominants, theme_labs, *, threshold, top_colors, max_hues, features=None, lenient=False, cast_c_min=CAST_C_MIN, cast_tol=CAST_TOL, acc_mono_max=ACC_MONO_MAX, conc_min=CONC_MIN, acc_tol=ACC_TOL, hue_cov_min=HUE_COV_MIN, hue_tol=HUE_TOL) -> bool`
  - constants `CAST_C_MIN = 4.0`, `CAST_TOL = 22.0`, `ACC_MONO_MAX = 8.0`, `CONC_MIN = 0.25`, `ACC_TOL = 35.0`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_match_wallpapers.py`:

```python
class TestThemeMatchesPaths(unittest.TestCase):
    # everforest-like chromatic palette: dark tinted bg + green + teal
    THEME = [mw.srgb_to_lab(mw.hex_to_rgb(h))
             for h in ("#2d353b", "#a7c080", "#7fbbb3", "#83c092")]
    KW = dict(threshold=12.0, top_colors=3, max_hues=4)

    def _feats(self, doms, cast_chroma=0.0, cast_hue=0.0, conc=0.0, ahue=0.0):
        return mw.ImageFeatures(dominants=doms, cast_chroma=cast_chroma,
                                cast_hue=cast_hue, accent_concentration=conc,
                                accent_hue=ahue)

    def test_cast_path_matches_muted_aligned_image(self):
        # muted grey-green image (mean chroma < 12) with a green cast aligned to palette
        doms = [((70, 82, 74), 1.0)]
        feats = self._feats(doms, cast_chroma=9.0, cast_hue=150.0)
        self.assertTrue(mw.theme_matches_image(doms, self.THEME, features=feats, **self.KW))

    def test_cast_path_rejects_weak_cast(self):
        doms = [((70, 72, 71), 1.0)]                     # near-gray, cast too weak
        feats = self._feats(doms, cast_chroma=2.0, cast_hue=150.0)
        self.assertFalse(mw.theme_matches_image(doms, self.THEME, features=feats, **self.KW))

    def test_accent_path_matches_concentrated_blob(self):
        # mostly-mono image + concentrated accent blob at a palette accent hue (~teal 186)
        doms = [((18, 18, 18), 0.9), ((26, 30, 29), 0.1)]
        feats = self._feats(doms, cast_chroma=0.5, cast_hue=200.0, conc=0.4, ahue=186.0)
        self.assertTrue(mw.theme_matches_image(doms, self.THEME, features=feats, **self.KW))

    def test_accent_path_rejects_spread_accent(self):
        doms = [((18, 18, 18), 0.9), ((26, 30, 29), 0.1)]
        feats = self._feats(doms, cast_chroma=0.5, cast_hue=200.0, conc=0.10, ahue=186.0)
        self.assertFalse(mw.theme_matches_image(doms, self.THEME, features=feats, **self.KW))

    def test_hue_family_matches_only_when_lenient(self):
        # dark saturated green (chromatic, strict-far from light palette) hue-aligned to green
        doms = [((45, 71, 27), 0.6), ((30, 30, 30), 0.4)]
        self.assertFalse(mw.theme_matches_image(doms, self.THEME, lenient=False, **self.KW))
        self.assertTrue(mw.theme_matches_image(doms, self.THEME, lenient=True, **self.KW))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_match_wallpapers.TestThemeMatchesPaths -v`
Expected: FAIL — `TypeError: theme_matches_image() got an unexpected keyword argument 'features'`

- [ ] **Step 3: Write minimal implementation**

Add path-param constants near the other new constants (~line 20):

```python
CAST_C_MIN = 4.0
CAST_TOL = 22.0
ACC_MONO_MAX = 8.0
CONC_MIN = 0.25
ACC_TOL = 35.0
```

Replace `theme_matches_image` (~lines 233-249) with:

```python
def theme_matches_image(dominants: list[tuple[tuple[int, int, int], float]],
                        theme_labs: list[tuple[float, float, float]], *,
                        threshold: float, top_colors: int, max_hues: int,
                        features: "ImageFeatures | None" = None,
                        lenient: bool = False,
                        cast_c_min: float = CAST_C_MIN, cast_tol: float = CAST_TOL,
                        acc_mono_max: float = ACC_MONO_MAX, conc_min: float = CONC_MIN,
                        acc_tol: float = ACC_TOL, hue_cov_min: float = HUE_COV_MIN,
                        hue_tol: float = HUE_TOL) -> bool:
    """Would the curator assign this image to this theme? The single source of the
    per-(image, theme) decision, shared by curate(), the eval, and the gallery.

    Chromatic image (dominant mean-chroma >= 12):
      - strict: the theme covers every prominent color within `threshold`, OR
      - hue-family (lenient themes only): enough dominant weight is chromatic and
        hue-aligned to the palette (dark/earthy nature scenes).
    Muted image (mean-chroma < 12):
      - neutral routing (grayscale image <-> grayscale theme), else
      - cast: a coherent whole-image tint aligned to a palette hue, or
      - accent: a spatially concentrated colored blob on a palette accent hue.

    `features` is required for the cast/accent paths; when None (synthetic callers)
    the muted branch keeps the original neutral-routing behavior."""
    if is_polychrome(dominants, max_hues=max_hues):
        return False

    if not image_is_neutral(dominants):
        if score_image_strict(dominants, theme_labs, top_n=top_colors) <= threshold:
            return True
        if lenient:
            acc_hues = palette_accent_hues(theme_labs)
            if on_hue_weight(dominants, acc_hues, hue_tol=hue_tol) >= hue_cov_min:
                return True
        return False

    # muted image
    if theme_is_neutral(theme_labs):
        return True
    if features is None:
        return False
    cast_hues = palette_cast_hues(theme_labs)
    if (features.cast_chroma >= cast_c_min
            and nearest_hue_distance(features.cast_hue, cast_hues) <= cast_tol):
        return True
    acc_hues = palette_accent_hues(theme_labs)
    if (image_mean_chroma(dominants) < acc_mono_max
            and features.accent_concentration >= conc_min
            and nearest_hue_distance(features.accent_hue, acc_hues) <= acc_tol):
        return True
    return False
```

- [ ] **Step 4: Run new + existing path tests**

Run: `python -m unittest tests.test_match_wallpapers.TestThemeMatchesPaths tests.test_match_wallpapers.TestThemeMatches -v`
Expected: PASS — 5 new + 6 existing (the 6 unchanged tests confirm `features=None`/`lenient=False` fallback).

- [ ] **Step 5: Run the whole unit suite**

Run: `python -m unittest tests.test_match_wallpapers -v`
Expected: PASS (43 original + new).

- [ ] **Step 6: Commit**

```bash
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): four-path theme_matches_image (strict/hue-family/cast/accent)"
```

---

### Task 4: Wire `curate()` to features + per-theme leniency

**Files:**
- Modify: `match_wallpapers.py` — add `THEME_OVERRIDES` (~line 20); rewrite the per-image loop in `curate()` (~lines 372-394)
- Test: `tests/test_match_wallpapers.py` (add to `TestCurate`)

**Interfaces:**
- Consumes: `image_features` (Task 2), `theme_matches_image` (Task 3).
- Produces: `THEME_OVERRIDES: dict[str, dict]` (default lenient False; `{"gruvbox": {"lenient": True}}`); `curate()` computes `image_features` once per image and passes `features` + per-theme `lenient`.

- [ ] **Step 1: Write the failing test**

Add to the `TestCurate` class in `tests/test_match_wallpapers.py`:

```python
    def test_lenient_theme_matches_earthy_via_hue_family(self):
        # dark saturated green: chromatic, far from a LIGHT palette under CIEDE,
        # but hue-aligned -> matched only by the theme flagged lenient.
        with tempfile.TemporaryDirectory() as src, \
             tempfile.TemporaryDirectory() as stock, \
             tempfile.TemporaryDirectory() as repo_bg, \
             tempfile.TemporaryDirectory() as cfg:
            Image.new("RGB", (160, 90), (45, 71, 27)).save(os.path.join(src, "forest.png"))
            self._theme(stock, "gruvbox", "#a9b665", "#89b482")  # light greens; lenient via THEME_OVERRIDES
            self._theme(stock, "sortof", "#a9b665", "#89b482")   # same palette, NOT lenient

            mw.curate(source=src, stock_dir=stock, user_dir=os.path.join(stock, "none"),
                      repo_bg_dir=repo_bg, config_bg_dir=cfg,
                      min_ratio=1.0, threshold=12.0, k=8, assume_yes=True)

            self.assertIn("forest.png", os.listdir(os.path.join(repo_bg, "gruvbox")))
            self.assertFalse(os.path.isdir(os.path.join(repo_bg, "sortof")))  # strict theme rejects
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_match_wallpapers.TestCurate.test_lenient_theme_matches_earthy_via_hue_family -v`
Expected: FAIL — `gruvbox` dir absent (current curate has no hue-family path).

- [ ] **Step 3: Write minimal implementation**

Add near the other new constants (~line 20):

```python
# Themes opted into permissive hue-family matching (earthy/nature). Default: strict.
THEME_OVERRIDES = {"gruvbox": {"lenient": True}}
```

In `curate()`, replace the per-image body (currently ~lines 372-394):

```python
    for img in _list_images(source):
        try:
            with Image.open(img) as im:
                w, h = im.size
            if not passes_ratio(w, h, min_ratio):
                filtered += 1
                continue
            feats = image_features(img, k=k)
        except Exception as e:  # unreadable / truncated image
            print(f"WARN: skipping {img}: {e}", file=sys.stderr)
            continue
        # Reject "matches everything" images (rainbow, neon) before scoring.
        if is_polychrome(feats.dominants, max_hues=max_hues):
            polychrome += 1
            continue
        matched = False
        for slug, labs in themes.items():
            lenient = THEME_OVERRIDES.get(slug, {}).get("lenient", False)
            if theme_matches_image(feats.dominants, labs, threshold=threshold,
                                   top_colors=top_colors, max_hues=max_hues,
                                   features=feats, lenient=lenient):
                assignments[slug].append(img)
                matched = True
        if not matched:
            dropped += 1
```

- [ ] **Step 4: Run new + existing curate/neutral tests**

Run: `python -m unittest tests.test_match_wallpapers.TestCurate tests.test_match_wallpapers.TestNeutralCurate -v`
Expected: PASS — new lenient test + `test_end_to_end_assigns_by_color` + `test_neutral_image_only_matches_neutral_theme` (unchanged behavior for solids).

- [ ] **Step 5: Commit**

```bash
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "feat(wallpapers): curate computes features + per-theme leniency (THEME_OVERRIDES)"
```

---

### Task 5: Wire the labeled-fixture eval + fixture params (ACCEPTANCE GATE)

**Files:**
- Modify: `tests/test_labeled_fixtures.py` (`evaluate()`, ~lines 43-48; `_which_gate` uses `feats.dominants`)
- Modify: `tests/fixtures/labels/everforest.json` (add `"lenient": false` to `params`)
- Modify: `tests/fixtures/labels/gruvbox.json` (add `"lenient": true` to `params`)

**Interfaces:**
- Consumes: `image_features`, `theme_matches_image` (Tasks 2-3).
- Produces: eval passes `features` + `params.lenient` (default False when absent).

- [ ] **Step 1: Add `lenient` to the fixture params**

Edit `tests/fixtures/labels/everforest.json` `params` block to:

```json
  "params": {
    "threshold": 12,
    "top_colors": 3,
    "k": 8,
    "max_hues": 4,
    "lenient": false
  },
```

Edit `tests/fixtures/labels/gruvbox.json` `params` block to:

```json
  "params": {
    "threshold": 12,
    "top_colors": 3,
    "k": 8,
    "max_hues": 4,
    "lenient": true
  },
```

- [ ] **Step 2: Run the eval to verify it still fails (matcher not yet wired)**

Run: `python -m unittest tests.test_labeled_fixtures.TestLabeledFixtures -v`
Expected: FAIL — everforest 74% / gruvbox 77% (eval still calls the dominants-only path; params.lenient present but unused).

- [ ] **Step 3: Wire `evaluate()` to features + lenient**

In `tests/test_labeled_fixtures.py`, replace the dominants line and the call inside `evaluate()` (~lines 43-48):

```python
        try:
            feats = mw.image_features(path, k=p["k"])
        except Exception as e:                      # unreadable/truncated
            skipped.append(f'{item["name"]} ({e})')
            continue
        assigned = mw.theme_matches_image(
            feats.dominants, labs, threshold=p["threshold"], top_colors=p["top_colors"],
            max_hues=p["max_hues"], features=feats, lenient=p.get("lenient", False))
```

And update `_which_gate` to accept dominants explicitly — change its first line usage in `evaluate()`'s note branch (~line 54) from `doms` to `feats.dominants`:

```python
                gate = _which_gate(feats.dominants, labs, p)
```

(`_which_gate`'s body already takes a `doms` parameter; only the caller's variable name changes.)

- [ ] **Step 4: Run the eval — acceptance gate**

Run: `python -m unittest tests.test_labeled_fixtures -v`
Expected: PASS — both subtests green. Confirm the accuracy lines read `19/19 = 100%` (everforest) and `13/13 = 100%` (gruvbox) with `mismatches=[]`.

If any mismatch remains, STOP and diagnose against the spec's validated numbers before proceeding — do not tune fixtures to force green.

- [ ] **Step 5: Commit**

```bash
git add tests/test_labeled_fixtures.py tests/fixtures/labels/everforest.json tests/fixtures/labels/gruvbox.json
git commit -m "test(wallpapers): eval passes features + per-theme lenient; both fixtures 100%"
```

---

### Task 6: Wire the gallery generator

**Files:**
- Modify: `tools/gen_gallery.py` (`render()`, ~lines 55-59)

**Interfaces:**
- Consumes: `image_features`, `theme_matches_image` (Tasks 2-3).
- Produces: gallery verdicts reflect the four-path decision with per-theme `lenient`.

- [ ] **Step 1: Update `render()` to compute features + lenient**

In `tools/gen_gallery.py`, replace the block inside the `if os.path.isfile(path):` branch (~lines 55-59):

```python
                if os.path.isfile(path):
                    feats = mw.image_features(path, k=p["k"])
                    assigned = mw.theme_matches_image(
                        feats.dominants, labs, threshold=p["threshold"],
                        top_colors=p["top_colors"], max_hues=p["max_hues"],
                        features=feats, lenient=p.get("lenient", False))
                    score = round(mw.score_image_strict(feats.dominants, labs,
                                                         top_n=p["top_colors"]), 1)
```

- [ ] **Step 2: Regenerate the gallery and verify accuracy**

Run: `python3 tools/gen_gallery.py`
Expected: `Wrote .../docs/wallpapers-gallery.html (2 theme file(s))`. Open it; each theme's accuracy line reads 100% and every tile is green-outlined (`.ok`).

- [ ] **Step 3: Commit**

```bash
git add tools/gen_gallery.py docs/wallpapers-gallery.html
git commit -m "feat(wallpapers): gallery reflects four-path matcher + per-theme lenient"
```

---

### Task 7: Documentation + full-suite green

**Files:**
- Modify: `CLAUDE.md` (the `wallpapers` reference bullet under "References")
- Verify: whole `tests/` suite

**Interfaces:** none (docs + verification).

- [ ] **Step 1: Run the entire test suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — all of `test_match_wallpapers.py` (43 + new) and `test_labeled_fixtures.py` (harness + both fixtures at 100%).

- [ ] **Step 2: Update `CLAUDE.md`**

In the `wallpapers` reference bullet, append (keep the existing text; add these sentences):

> Matching is four paths in `theme_matches_image` (the single decision source): **strict** (CIEDE worst-of-top-N ≤ threshold), **hue-family** (dominant weight hue-aligned to the palette; only for themes flagged `lenient` in `THEME_OVERRIDES`, e.g. gruvbox — recovers dark/earthy nature scenes), **cast** (whole-image color tint on muted images), **accent** (a spatially concentrated colored blob on an otherwise mono image — e.g. a green comet on black). cast/accent read a once-per-image `ImageFeatures` from a numpy Lab pass at `FEATURE_RES` (1000px) — **numpy is now a dependency** (with Pillow). Per-theme leniency is a manual choice (`THEME_OVERRIDES` for curate, `params.lenient` in each `tests/fixtures/labels/*.json` for the eval), not auto-derived. Eval validated on everforest (strict) + gruvbox (lenient) at 100%/0-FP.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(wallpapers): document four-path matcher, numpy dep, per-theme leniency"
```

---

## Self-Review

**Spec coverage:**
- strict path unchanged → Task 3 (kept). hue-family path → Tasks 1+3. cast path → Tasks 2+3. accent path → Tasks 2+3. Per-theme leniency → Task 4 (curate `THEME_OVERRIDES`) + Task 5 (`params.lenient`). Feature extraction / `ImageFeatures` → Task 2. Signature (`features=None`, `lenient=False`) + 6 tests unchanged → Task 3. Both-fixture 100%/0-FP acceptance → Task 5. Gallery reflects paths → Task 6. numpy dependency + docs → Tasks 2, 7. No real wallpapers committed → fixtures only carry JSON (Task 5).
- All spec requirements map to a task.

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code; the one stray-paren risk in Task 2 is called out explicitly with the corrected line.

**Type consistency:** `image_features(path, k=...) -> ImageFeatures` (Task 2) is consumed with `feats.dominants` / `feats.cast_chroma` / `feats.cast_hue` / `feats.accent_concentration` / `feats.accent_hue` in Tasks 3-6. `theme_matches_image(..., features=None, lenient=False, ...)` (Task 3) is called with `features=feats, lenient=...` in Tasks 4-6. `on_hue_weight`, `palette_accent_hues`, `palette_cast_hues`, `nearest_hue_distance` (Task 1) are used in Task 3. Constant names (`CAST_C_MIN`, `CONC_MIN`, `ACC_TOL`, `HUE_COV_MIN`, `HUE_TOL`, `FEATURE_RES`, `ACCENT_GRID`, `ACCENT_CHROMA_FLOOR`) consistent across tasks.
