# Muted-image matcher: color-cast + salient-accent paths

**Date:** 2026-07-07
**Branch:** `feat/wallpaper-theme-matcher`
**Depends on:** `match_wallpapers.py`, specs `2026-06-16-wallpaper-theme-matcher-design.md`,
`2026-07-06-everforest-fixture-tests-design.md`

## Problem

The labeled-fixture eval on `everforest.json` is red: 14/19 = 74%. All 5 errors are the same
shape — `do → rejected` (matcher too strict); **zero** false positives (`dont → assigned`).
All 5 die at the **neutral gate** (`theme_is_neutral(labs) != image_is_neutral(doms)`): their
dominant-weighted mean chroma is below `chroma_floor = 12`, so the matcher treats them as
"near-gray" and routes them away from the chromatic everforest palette.

Parameter sweeps do **not** fix it — the current strict defaults (chroma_floor 12, threshold
12, max_hues 4) are the *only* FP-free operating point; any loosening removes 1–2 FN but admits
≥2 FP. The problem is **structural**, not parametric.

### Root cause

Dominant colors come from median-cut, which is **area-weighted**. That blinds the matcher to
two things a human weights heavily:

1. **Faint but coherent color casts.** Misty / low-light forest photos carry a real green/teal
   tint at chroma 5–15. CIEDE2000 to the palette is dominated by the *saturation gap* (image
   chroma 5–15 vs palette chroma 21–44), so `score_image_strict` lands at 14–21 (> threshold)
   even though the **hue** matches. The image also trips the neutral gate.
2. **Tiny but salient accents.** `wallhaven-48qo7o.jpg` is a green comet on a black starfield —
   the coma/tail is unmistakably everforest green/teal to a human, but it is **< 0.1 %** of the
   pixels (5085 px, max chroma 35, at full 3420×2564 res). Area-weighted dominants — and any
   thumbnail scan below ~1000 px — erase it entirely (measured mean chroma 0.9).

Both classes are hue-consistent with everforest and both currently die at the neutral gate.
They need **new signals**, not new thresholds.

### Why the naive fixes fail (measured)

- Relaxing the neutral gate alone is insufficient: the 5 FN also have `score_image_strict`
  14–21 > threshold 12, so they'd still be rejected on score.
- A pure hue-agreement rule (ignore chroma) admits `wallhaven-ex59dr.jpg` — a **vivid** green
  the human rejected — so chroma cannot be fully ignored.
- A salient-accent detector sensitive enough to catch the comet (0.058 % @ maxC 35) fires
  first on `rainy_day_by_mleth-d94tvyv.png` (a `dont`): 0.64 % of pixels at chroma up to 100,
  aligned to everforest's salmon accent. **Color statistics alone cannot separate them** — the
  comet is spatially coherent (a compact blob); rainy's warm pixels are a *spread* city-light
  band. Spatial concentration is the discriminator color distance misses.

## Goal

Recover the muted `do` images — including the comet — **without** any new false positive on the
labeled `dont` set. Empirical target on the labeled fixtures: accuracy up, aiming 100 % at
**zero** false positives. `theme_matches_image` remains the single source of the per-(image,
theme) decision, called by `curate()`, the eval, and the gallery.

## Design: three decision paths

`theme_matches_image` keeps its gate order. The **chromatic** branch is unchanged. The **muted**
branch (image mean-chroma < neutral floor 12) gains two OR'd acceptance paths.

```
polychrome? .................................... → reject           (UNCHANGED)
chromatic image (dom mean-chroma ≥ 12):
    → score_image_strict worst-of-top-N ≤ threshold                (UNCHANGED — 0 FP today)
muted image (dom mean-chroma < 12):
    theme is neutral?  → match                                     (UNCHANGED gray↔gray)
    theme is chromatic:
        PATH A  cast:   cast_chroma ≥ CAST_C_MIN
                    AND hue_dist(cast_hue, palette hues incl. tinted bg) ≤ CAST_TOL
        PATH B  accent: dom mean-chroma < ACC_MONO_MAX
                    AND accent blob exists (chromatic pixels present)
                    AND accent_concentration ≥ CONC_MIN
                    AND hue_dist(accent_hue, chromatic accent hues) ≤ ACC_TOL
        neither → reject
```

- **strict** (unchanged) catches every chromatic `dont`: vivid green ex59dr, browns, blue
  skies, polychrome. Untouched → contributes no new FP.
- **PATH A — cast.** Whole-image chroma-weighted mean `(a, b)` → `cast_chroma`, `cast_hue`.
  Recovers the misty forests. `CAST_C_MIN` is what rejects washed / near-gray `dont`
  (g7l393 castC 2.3, rainy 3.6, 2y3wr9 2.9). Cast targets are palette hues whose color has
  chroma ≥ 3 — this **includes a tinted background** (everforest bg #2d353b, chroma 5, hue 250,
  which is what recovers the blue-cast pair 7pr53v/rqjrzq) but **excludes a pure-gray bg**
  whose hue would be noise.
- **PATH B — accent.** Over chromatic pixels (chroma ≥ `ACCENT_CHROMA_FLOOR`), bucket into a
  24×24 spatial grid; `accent_concentration` = share of accent pixels in the densest cell;
  `accent_hue` = chroma-weighted mean hue of that densest cell. `CONC_MIN` rejects rainy's
  *spread* city-light band (0.10) while admitting the comet blob (0.35). `ACC_MONO_MAX` keeps
  the path to mostly-monochromatic grounds (rejects chromatic pastels like g7l393). Accent
  targets are **chromatic** palette hues only (chroma ≥ 12) — not the bg — so black-compression
  noise (vpyekp, hue ≈ 269) does not align.

### Validation to date

A sandbox prototype of all three paths, graded on the 19 everforest fixtures at the images'
originals, scores **19/19 = 100 %, FP = 0, FN = 0**. Path attribution: 7pr53v/rqjrzq/14653/
fb002 via cast, 48qo7o via accent, all 14 `dont` rejected (strict or muted-reject).

## Feature extraction — `image_features(path) → ImageFeatures`

One numpy Lab pass at the image thumbnailed to longest-side `FEATURE_RES` (≈ 1000 px, needed so
the comet survives). Returns, per image (theme-independent):

| field | meaning |
|-------|---------|
| `dominants` | existing median-cut `[(rgb, weight)]` (drives polychrome / strict / neutral gate) |
| `cast_chroma`, `cast_hue` | magnitude / angle of mean `(a, b)` over all pixels |
| `accent_concentration` | densest-cell share of pixels with chroma ≥ `ACCENT_CHROMA_FLOOR` (0 if none) |
| `accent_hue` | chroma-weighted mean hue of that densest cell |

Computed **once per image**, reused across all themes (curate scores each image against every
theme). The per-theme comparisons (`hue_dist` to palette / accent hues) stay inside
`theme_matches_image`. `dom mean-chroma` (neutral gate + `ACC_MONO_MAX`) stays the existing
dominant-weighted `image_mean_chroma` — **not** the pixel mean — for consistency with today's
regime split (fb002's dominant mean 10.5 is muted; its pixel mean 12.0 would wrongly route it
to the strict path).

## Signature — optional `features`

```python
theme_matches_image(dominants, theme_labs, *, threshold, top_colors, max_hues,
                    features=None, <new muted-path params…>) -> bool
```

- Real callers (`curate`, eval, gallery) pass `features` → cast + accent paths active.
- `features is None` → the muted branch falls back to **today's behavior** (neutral image +
  chromatic theme → reject). The 6 synthetic `TestThemeMatches` unit tests, which build
  hand-made `dominants` with no image file, pass nothing and **stay unchanged** — they exercise
  the strict/neutral core, which is still the single decision source.

Rationale: minimal ripple, existing tests remain meaningful, no awkward synthetic
`ImageFeatures`. (Alternative — mandatory `features`, rewriting the 6 tests — rejected for
churn with no correctness gain.)

## New parameters (provisional — everforest-tuned)

| param | provisional default | role |
|-------|--------------------|------|
| `CAST_C_MIN` | 4.0 | min cast strength for PATH A |
| `CAST_TOL` | 22° | max cast-hue distance to a palette hue |
| `ACC_MONO_MAX` | 8.0 | PATH B only for mostly-mono images (dom mean-chroma) |
| `CONC_MIN` | 0.25 | min densest-cell share for a "concentrated" accent |
| `ACC_TOL` | 35° | max accent-hue distance to a chromatic accent hue |
| `ACCENT_CHROMA_FLOOR` | 18 | chroma above which a pixel counts as accent |
| `FEATURE_RES` | 1000 | longest-side px for the feature scan |
| `ACCENT_GRID` | 24 | spatial grid resolution for concentration |

Exposed as `curate()` kwargs + CLI flags, mirroring `threshold` / `max_hues`; added to the
fixture `params` block; defaulted in code when a label file omits them (backward-compat with the
existing everforest.json).

## Overfitting risk & the 2-fixture requirement

**These 8 values are tuned on one fixture (everforest, 19 images) and some margins are thin**
(14653 castC 4.4 vs floor 4.0). To de-risk generalization, a **second theme — gruvbox (warm,
maximal contrast to everforest's cool green) — is labeled first**, and the design is
re-validated and re-tuned against **both** fixtures before implementation is trusted.

Possible outcome the 2nd fixture may force: absolute thresholds (`CAST_C_MIN`, `CAST_TOL`,
`ACC_TOL`) may need to become **palette-relative** (e.g. scaled by the theme's own chroma /
hue spread) rather than fixed. If so, the parameter table above becomes a set of *derived*
values and the spec is updated accordingly. The three-path *architecture* is expected to hold;
only the thresholding may change.

## Dependencies & cost

- **numpy** (already installed, 2.4.6) for the vectorized Lab pass — pure-Python at 1000 px is
  ~3–5 s/image vs ~0.05 s with numpy. Document numpy as a dependency (no requirements file
  exists today; Pillow is the current implicit dep).
- The feature scan at ~1000 px is heavier than today's 256 px dominant thumbnail, but runs
  **once per image**; the curate tool runs occasionally, so this is acceptable.

## Acceptance criteria (empirical, via eval)

- `python -m unittest tests.test_labeled_fixtures -v` on **both** `everforest.json` and
  `gruvbox.json`: accuracy up, target 100 % (or justified-close) at **zero** false positives.
- `python -m unittest discover -s tests` green. The 43 existing `test_match_wallpapers.py`
  tests stay green; any updated principally (not force-fit). `theme_matches_image` remains the
  single decision source (curate + eval + gallery call it).
- `curate()` and the gallery pass `features` and reflect the new paths.
- No real wallpapers committed; eval references originals by `source_dir/basename`.

## Out of scope

- Spatial object / semantic detection beyond the single-blob concentration measure.
- Retuning the chromatic (strict) path — it is FP-free and untouched.
- Labeling themes beyond everforest + gruvbox (future work; the design stays theme-agnostic).
