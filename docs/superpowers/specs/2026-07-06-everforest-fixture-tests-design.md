# Everforest fixture tests + gallery — design

**Date:** 2026-07-06
**Branch:** `feat/wallpaper-theme-matcher`
**Depends on:** `match_wallpapers.py`, spec `2026-06-16-wallpaper-theme-matcher-design.md`

## Problem

The matcher's unit tests (`tests/test_match_wallpapers.py`) validate the math with
**synthetic solid-color PNGs** (`Image.new`). Nothing exercises the full pipeline —
dominant-color extraction → the three rejection gates → strict score — against **real
photographs**. Commit `088e4b7` added the strictness that matters most (worst-color
strict score, polychrome gate, neutral gate) and it has no real-image regression guard.

## Goal

For one chosen theme — **everforest** (chromatic green; its don'ts naturally span all
three rejection paths) — add:

1. **Automated fixture test** — real wallpapers labeled do / don't, asserting the
   matcher classifies each correctly *and via the intended mechanism*.
2. **Visual gallery** — rendered reference showing each fixture, its verdict, and score,
   grouped by bucket. Tuning aid, no assertions.

Non-goals: other themes, exact-score golden snapshots, changing the matcher itself.

## Fixtures

Hand-picked real wallpapers from `~/Wallpapers` (147 available), **downscaled to ~400px
longest edge**. The matcher thumbnails to 256px internally (`dominant_colors`, `resize=256`),
so downscaling to 400px loses zero matching fidelity while keeping each file ~20–40KB.
Committed (not gitignored — these are test data, unlike the curated background symlinks).

Layout:

```
tests/fixtures/everforest/
  colors.toml                     # copied from live everforest theme (hermetic)
  do/                             # ~4 green/forest landscapes -> assigned to everforest
  dont/
    wrong-hue/                    # ~2 chromatic but off-palette (red desert, warm sunset)
    polychrome/                   # ~2 rainbow / neon / vaporwave
    neutral/                      # ~2 grayscale photos
```

Roughly 10 images, well under ~400KB total.

**Palette source — copy-in, not live.** `colors.toml` is copied into the fixture dir so
the test is hermetic: it survives Omarchy renaming/editing/removing the everforest theme
and runs on any host / CI without the omarchy install. Trade-off: it will not track
upstream palette edits — acceptable, the fixture set is a fixed regression baseline.

### Selection procedure

1. Run `match_wallpapers.py` over `~/Wallpapers` (or call `curate`/classify inline).
2. Pick **unambiguous** members of each bucket, verifying each classifies as intended
   *at current defaults* — chosen with **margin** (not sitting on the threshold /
   gate boundary) so normal tuning won't flip them.
   - do: `not polychrome`, `not neutral`, `score_image_strict ≤ threshold` comfortably.
   - wrong-hue: chromatic (`not neutral`), `not polychrome`, score **>** threshold.
   - polychrome: `is_polychrome` True.
   - neutral: `image_is_neutral` True.
3. Downscale, commit.

## Test — `tests/test_fixtures_everforest.py`

Loads the copied `colors.toml` via `mw.parse_palette` → Lab (same path as `load_themes`).
For each fixture, extracts `mw.dominant_colors` at the CLI default `k`, then asserts the
mechanism per bucket:

| Bucket      | Assertions |
|-------------|-----------|
| do          | `not is_polychrome(doms)`; `not image_is_neutral(doms)`; `score_image_strict(doms, labs, top_n=TOP) <= THRESHOLD` |
| wrong-hue   | `not is_polychrome(doms)`; `not image_is_neutral(doms)`; `score_image_strict(...) > THRESHOLD` |
| polychrome  | `is_polychrome(doms)` is True |
| neutral     | `image_is_neutral(doms)` is True |

`THRESHOLD`, `TOP` (`top_colors`), `k`, `max_hues` are read from the **same defaults the
CLI uses** (module-level / `argparse` defaults) so the test tracks the tool rather than
pinning a private copy. Iterates fixture files by globbing each bucket dir — adding a
fixture needs no test edit.

Complements (does not replace) the synthetic math tests.

## Gallery

Rendered reference: everforest palette swatches at top, then fixture thumbnails grouped
**do / wrong-hue / polychrome / neutral**, each captioned with its `score_image_strict`
value and the verdict (assigned / rejected-by-<gate>). Generated from the fixtures +
matcher so it stays truthful.

Form: a small generator script producing an HTML page (self-contained, thumbnails inline)
under `docs/`, regenerable after fixture changes. Exact path decided in the plan.

## Testing the tests

`python -m unittest` (or `pytest`) green on this host. Fixtures verified to classify as
labeled before commit (the selection procedure's step 2 is the check).

## Open questions

None blocking. Gallery output path + generator location settled during planning.
