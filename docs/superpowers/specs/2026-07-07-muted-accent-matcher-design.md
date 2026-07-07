# Muted-image + hue-family matcher paths (color-cast, salient-accent, hue-family)

**Date:** 2026-07-07
**Branch:** `feat/wallpaper-theme-matcher`
**Depends on:** `match_wallpapers.py`, specs `2026-06-16-wallpaper-theme-matcher-design.md`,
`2026-07-06-everforest-fixture-tests-design.md`
**Validated against:** `everforest.json` (19 imgs) + `gruvbox.json` (13 imgs)

## Problem

The labeled-fixture eval is red on both themes against the current matcher:

- **everforest 14/19 = 74 %** — 5 `do → rejected`, 0 FP. All 5 die at the **neutral gate**
  (`image_is_neutral` true because dominant-weighted mean chroma < 12) → routed away from the
  chromatic palette.
- **gruvbox 10/13 = 77 %** — 3 `do → rejected`, 0 FP. All 3 are *chromatic* images killed by the
  **strict score** (`score_image_strict` worst-of-top-3 CIEDE = 21–27 > threshold 12).

Parameter sweeps do not fix either without new false positives — the failures are **structural**.

### Root cause (one cause, two surfaces)

The human matches on **hue family**; CIEDE2000's lightness and chroma terms over-penalize when the
image's *tone/saturation* differs from the palette's, even at matching hue. Median-cut dominants are
also **area-weighted**, blind to faint casts and tiny accents. This shows up three ways:

1. **Faint coherent casts** (misty forests): real green/teal tint at chroma 5–15; CIEDE inflated by
   the saturation gap to the palette (chroma 21–44); also trips the neutral gate.
2. **Tiny salient accents** (`48qo7o` — a green comet on black): the everforest-green coma/tail is
   < 0.1 % of pixels (max chroma 35 at full 3420×2564 res). Area weighting and any sub-~1000 px scan
   erase it (measured mean chroma 0.9).
3. **Dark / off-tone regions in chromatic nature scenes** (gruvbox `d682mj` forest floor, `q6e3jd`
   botanical print, `ex59dr` vivid green): the theme palette is **all light** (gruvbox chromatic
   colors L 60–71; its only dark color is the near-neutral bg L16/C0), so dark-saturated image
   regions match neither the light chromatic colors (L gap) nor the dark bg (C gap). Worst-of-top-3
   CIEDE explodes (21–27) though the hue is a near-exact palette green.

### Two themes, two aesthetics — a labeling-philosophy fact

everforest is labeled **strictly** (rejects the vivid green `ex59dr`); gruvbox is labeled
**permissively** ("earthy nature = gruvbox", accepts `ex59dr`). `ex59dr` is the *same image* — `do`
for gruvbox, `dont` for everforest — with near-identical color distances to both palettes (ciede
26.7 vs 26.4). **No palette-symmetric color metric can accept it for one theme and reject it for the
other.** Therefore the permissive "hue-family" behavior must be a **per-theme opt-in**, not global.

### Measured dead-ends (why the naive fixes fail)

- Relaxing the neutral gate alone: the everforest FN still score 14–21 on strict > threshold 12.
- Global threshold bump to ~21 (to admit gruvbox FN): gives everforest 3 FP.
- Lightness-reweighted CIEDE (kL 1.5–3) or lightness-free CIEDE: gruvbox's do/dont **overlap** at
  every setting, and everforest's donts collapse (`1ppx2w` → 6.7) → FP.
- Salient-accent detector sensitive enough for the comet (0.058 % @ maxC 35) fires first on `rainy`
  (0.64 % @ chroma≤100, salmon-aligned) → FP. The comet is a spatially **coherent** blob; rainy's
  warm pixels are a **spread** city-light band — spatial concentration is the discriminator.

## Goal

Recover the muted `do` (incl. the comet) and the chromatic earthy-nature `do`, **without** any new
false positive on either labeled `dont` set. Empirical target: **100 %, zero FP on both fixtures**
(achieved by the prototype below). `theme_matches_image` stays the single per-(image, theme)
decision, called by `curate()`, the eval, and the gallery.

## Design: four decision paths + a per-theme leniency flag

`theme_matches_image` keeps its gate order. The **chromatic** branch gains a *lenient-only*
hue-family path; the **muted** branch gains two always-on paths.

```
polychrome? .............................................. → reject     (UNCHANGED)
chromatic image (dom mean-chroma ≥ 12):
    strict:      score_image_strict worst-of-top-N ≤ threshold          (UNCHANGED)
    hue-family:  lenient AND on_hue_weight ≥ HUE_COV_MIN                 (NEW, per-theme)
    else → reject
muted image (dom mean-chroma < 12):
    theme is neutral?  → match                                          (UNCHANGED gray↔gray)
    cast:    cast_chroma ≥ CAST_C_MIN AND hue_dist(cast_hue, tinted-palette-hues) ≤ CAST_TOL  (NEW)
    accent:  dom mean-chroma < ACC_MONO_MAX AND accent blob present
             AND accent_concentration ≥ CONC_MIN
             AND hue_dist(accent_hue, chromatic-accent-hues) ≤ ACC_TOL  (NEW)
    else → reject
```

- **strict** (unchanged): worst nearest-palette CIEDE over the top-N dominants ≤ threshold.
- **hue-family** (chromatic, `lenient` themes only): `on_hue_weight` = fraction of dominant weight
  that is chromatic (chroma ≥ 12) **and** hue-aligned (≤ `HUE_TOL`) to a chromatic palette accent.
  Recovers dark/off-tone nature scenes whose hue family is the theme's even when no single dominant
  is close under CIEDE. Reads from **dominants only** — no pixel scan. Gated by the per-theme
  `lenient` flag so it never fires for strict themes (keeps `ex59dr` out of everforest).
- **cast** (muted, always on): whole-image chroma-weighted mean `(a,b)` → `cast_chroma`, `cast_hue`.
  `CAST_C_MIN` rejects washed near-gray donts. Cast targets are palette hues with chroma ≥ 3 —
  includes a *tinted* bg (everforest #2d353b, C5, H250, recovers the blue-cast pair) but excludes a
  pure-gray bg whose hue is noise.
- **accent** (muted, always on): over pixels with chroma ≥ `ACCENT_CHROMA_FLOOR`, bucket into an
  `ACCENT_GRID`×`ACCENT_GRID` grid; `accent_concentration` = densest-cell share; `accent_hue` =
  chroma-weighted mean hue of that cell. `CONC_MIN` rejects spread accents (rainy); `ACC_MONO_MAX`
  keeps the path to mostly-mono grounds; accent targets are chromatic hues only (not bg).

### Validation (prototype, graded on originals)

| theme | lenient | result | paths used by recovered `do` |
|-------|---------|--------|------------------------------|
| everforest | false | **19/19, FP 0, FN 0** | cast ×4, accent ×1 (comet) |
| gruvbox | true | **13/13, FP 0, FN 0** | hue-family ×3, strict ×1 |

## Feature extraction — `image_features(path) → ImageFeatures`

`on_hue_weight` needs only `dominants` (cheap). Only **cast** and **accent** need a pixel scan: one
numpy Lab pass at longest-side `FEATURE_RES` (≈ 1000 px, so the comet survives). Per image
(theme-independent):

| field | source | meaning |
|-------|--------|---------|
| `dominants` | existing median-cut (256 px) | polychrome / strict / neutral gate / on-hue-weight |
| `cast_chroma`, `cast_hue` | numpy pass | magnitude / angle of mean `(a,b)` over all pixels |
| `accent_concentration` | numpy pass | densest-cell share of pixels with chroma ≥ `ACCENT_CHROMA_FLOOR` |
| `accent_hue` | numpy pass | chroma-weighted mean hue of that densest cell |

Computed **once per image**, reused across all themes. Per-theme comparisons (`hue_dist`,
`on_hue_weight`, `score_image_strict`) stay inside `theme_matches_image`. The neutral gate and
`ACC_MONO_MAX` use the existing dominant-weighted `image_mean_chroma` (not the pixel mean) — fb002's
dominant mean 10.5 is muted; its pixel mean 12.0 would wrongly route it to the strict path.

## Signature — optional `features`, per-theme `lenient`

```python
theme_matches_image(dominants, theme_labs, *, threshold, top_colors, max_hues,
                    features=None, lenient=False, <new path params…>) -> bool
```

- Real callers (`curate`, eval, gallery) pass `features` and the theme's `lenient` → all paths active.
- `features is None` → muted branch falls back to **today's behavior** (neutral image + chromatic
  theme → reject); `lenient` defaults false. The 6 synthetic `TestThemeMatches` unit tests pass
  neither and **stay unchanged** — they exercise the strict/neutral core, still the single decision
  source.

## Per-theme leniency

`lenient` is **per theme**:

- **Eval**: carried in each label file's `params` block (`"lenient": true/false`), like `threshold`.
  everforest `false`, gruvbox `true`.
- **curate**: a repo-level override map (default `lenient=false`, strict) — e.g.
  `THEME_OVERRIDES = {"gruvbox": {"lenient": True}}` in `match_wallpapers.py`, applied per theme in
  the curate loop. A new theme is strict until a human opts it into hue-family matching.

Leniency is **not auto-derived** — gruvbox and everforest have near-identical palette *shapes*
(green/warm/dark-bg); the difference is aesthetic intent, which only a human sets. This is a known,
accepted manual step, documented in the ownership table / CLAUDE.md.

## Parameters (validated on both fixtures)

| param | default | role |
|-------|---------|------|
| `CAST_C_MIN` | 4.0 | min cast strength (PATH cast) |
| `CAST_TOL` | 22° | max cast-hue distance to a tinted palette hue (chroma ≥ 3) |
| `ACC_MONO_MAX` | 8.0 | accent path only for mostly-mono images (dom mean-chroma) |
| `CONC_MIN` | 0.25 | min densest-cell share for a concentrated accent |
| `ACC_TOL` | 35° | max accent-hue distance to a chromatic accent hue |
| `ACCENT_CHROMA_FLOOR` | 18 | chroma above which a pixel counts as accent |
| `FEATURE_RES` | 1000 | longest-side px for the feature scan |
| `ACCENT_GRID` | 24 | spatial grid resolution for concentration |
| `HUE_COV_MIN` | 0.45 | min on-hue dominant weight (PATH hue-family, lenient only) |
| `HUE_TOL` | 20° | hue tolerance for on-hue-weight |
| `lenient` | false (per theme) | enables the chromatic hue-family path |

Global defaults in code + CLI, mirrored in each fixture's `params`, defaulted when a label file
omits them (backward-compat).

## Overfitting status

Tuned and validated on **two** themes with opposite aesthetics (cool-strict everforest, warm-permissive
gruvbox), so less overfit than a single fixture — but still two. Thin margins remain (cast: 14653
castC 4.4 vs floor 4.0; hue-family: gruvbox d682mj 0.52 vs dont max 0.33). Each new theme labeled is
another test; the design stays theme-agnostic apart from the manual per-theme `lenient` choice.

## Dependencies & cost

- **numpy** (installed 2.4.6) for the vectorized Lab pass; pure-Python at 1000 px is ~3–5 s/image vs
  ~0.05 s. Document as a dependency (no requirements file today; Pillow is the current implicit dep).
- Feature scan at ~1000 px runs **once per image**; curate runs occasionally → acceptable.

## Acceptance criteria (empirical, via eval)

- `python -m unittest tests.test_labeled_fixtures -v` on `everforest.json` + `gruvbox.json`:
  **100 %** (or justified-close) at **zero** false positives, each theme.
- `python -m unittest discover -s tests` green; the 43 `test_match_wallpapers.py` tests stay green
  (updated principally, not force-fit). `theme_matches_image` remains the single decision source.
- `curate()` and the gallery pass `features` + per-theme `lenient` and reflect the new paths.
- No real wallpapers committed; eval references originals by `source_dir/basename`.

## Out of scope

- Auto-deriving `lenient` from the palette (manual per-theme for now).
- Spatial object / semantic detection beyond single-blob concentration.
- Retuning the chromatic **strict** metric (unchanged; FP-free).
- Labeling themes beyond everforest + gruvbox (future; design stays theme-agnostic).
