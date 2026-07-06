# Labeled fixture eval — static labeler + gallery + data-driven test

**Date:** 2026-07-06
**Branch:** `feat/wallpaper-theme-matcher`
**Depends on:** `match_wallpapers.py`, spec `2026-06-16-wallpaper-theme-matcher-design.md`
**Supersedes** the earlier auto-classified-fixtures draft of this file.

## Problem

The matcher's unit tests (`tests/test_match_wallpapers.py`) validate the math with
**synthetic solid-color PNGs**. Nothing checks the full pipeline against **real
photographs**, and — critically — nothing checks the matcher against **human
judgement**. Auto-deriving fixtures from the matcher is circular: it only confirms the
matcher agrees with itself. We want a **human-labeled ground-truth set** the matcher is
graded against, so a regression that starts mis-sorting real wallpapers turns a test red.

## Goal

A reusable **labeling form** where a human sorts wallpapers into do / don't buckets (with
a reason) **per theme**, producing one self-contained data file per theme. A **data-driven
test** grades the matcher against those files. A **gallery** renders the labeled set with
the matcher's verdict for tuning.

everforest is the first theme labeled; nothing is everforest-specific — every component is
theme-agnostic and driven by whichever label files exist.

## Ground truth is authoritative

The human label is the oracle. **If the matcher disagrees with any label, the test fails**
and reports accuracy (% of items the matcher classified as the human did) plus the list of
mismatches. This makes the fixture set a real accuracy gate, not a self-agreement check.

## Components

### A. Theme data generator — `tools/gen-theme-data.py`

Reads stock + user theme dirs (`~/.local/share/omarchy/themes`, `~/.config/omarchy/themes`)
and writes `tools/fixtures-labeler/themes.json` (committed):

```json
{
  "everforest": {
    "palette": ["#2d353b", "#7fbbb3", "#e67e80", "..."],
    "backgrounds": ["/abs/path/to/existing/bg1.jpg", "..."]
  }
}
```

- `palette` comes from `mw.parse_palette` on the theme's `colors.toml` → hex, so the form's
  hint uses **exactly** the hue-bearing keys the matcher scores against (single source of
  truth, no drift).
- `backgrounds` lists that theme's existing omarchy backgrounds (best-effort hint of "what
  already matches"). Regenerate when themes change: `python3 tools/gen-theme-data.py`.

### B. Static labeler — `tools/fixtures-labeler/{index.html,app.js,style.css}`

Pure static JS+HTML+CSS (no server; open via `file://` or any static host). Flow:

1. **Theme dropdown** populated from `themes.json`.
2. **Hints for the chosen theme:** palette swatches (guaranteed) + existing-wallpaper
   thumbnails (best-effort — `<img>` at the `file://` background paths; degrades silently
   if the browser blocks `file://` reads).
3. **Candidate images:** user drags in / file-selects wallpapers from `~/Wallpapers`
   (a static page cannot list a directory — the user supplies files).
4. Per image: **do / dont** toggle + **reason** select (`wrong-hue`, `polychrome`,
   `neutral`, `other`; reason enabled only for `dont`).
5. On add, each image is **downscaled to ≤400px longest edge via `<canvas>`**
   (matcher thumbnails to 256 internally, so 400px loses zero matching fidelity) and kept
   as a data-URI.
6. **Submit** → downloads `<theme>.json` (schema below). Submit = the whole theme file,
   **full overwrite** (no merge/append).
7. **Optional load-to-edit:** an "import existing `<theme>.json`" control repopulates the
   form so re-labeling doesn't start from scratch; a subsequent submit still fully
   overwrites.

The form writes nothing to disk itself (static). The downloaded file is placed by the user
at `tests/fixtures/labels/<theme>.json`.

### C. Per-theme label file — `tests/fixtures/labels/<theme>.json`

Self-contained (embeds downscaled images, so the test needs no `~/Wallpapers` and no
omarchy install — hermetic, CI-safe, and the gallery renders anywhere):

```json
{
  "theme": "everforest",
  "palette": ["#2d353b", "#7fbbb3", "..."],
  "params": { "threshold": 12.0, "top_colors": 3, "k": 8, "max_hues": 4 },
  "items": [
    { "name": "forest01.jpg", "label": "do",   "reason": null,        "image": "data:image/jpeg;base64,..." },
    { "name": "desert.jpg",   "label": "dont", "reason": "wrong-hue", "image": "data:image/jpeg;base64,..." }
  ]
}
```

- `palette` + `params` are embedded so the eval is fully reproducible from this one file,
  independent of live themes and of future CLI-default changes. Form defaults `params` from
  the matcher's current CLI defaults; editable in the form.
- Extension `.json`. Trade-off: base64 makes noisy diffs, but each image is ~40KB and a
  theme has ~10 → ~400KB/file, acceptable, and it keeps the artifact self-contained + static.

### D. Data-driven test — `tests/test_labeled_fixtures.py`

- **Discovers** all `tests/fixtures/labels/*.json`. If **none exist → skip with a message**
  (`skipTest("no labeled fixture files in tests/fixtures/labels/")`), so the suite is green
  on a fresh checkout before anyone has labeled a theme.
- For **each** label file: build Lab palette from `palette`; for each item decode the
  base64 image (via `PIL.Image.open(BytesIO(...))`), extract `mw.dominant_colors` at the
  file's `params.k`, then compute the matcher's verdict with the file's `params`:

  ```
  assigned = (not is_polychrome(doms, max_hues)
              and not image_is_neutral(doms)
              and score_image_strict(doms, labs, top_n=top_colors) <= threshold)
  expected = (label == "do")
  ```

- Collect every mismatch (`assigned != expected`). **Assert none.** On failure the message
  reports **accuracy** (`matches/total`) and each mismatched `name` with matcher-verdict vs
  human-label. One sub-test per theme file (`subTest`) so multiple themes report separately.
- **Reason (secondary):** for a `dont` item, record which gate actually fired
  (polychrome / neutral / score) and compare to `reason`. A gate/reason mismatch is
  reported as an **informational note in the failure/summary, not a hard failure** (avoids
  brittleness when two gates could both reject an image). Hard failure is assignment only.

Complements — does not replace — the synthetic math tests.

### E. Gallery — `tools/gen-gallery.py` → `docs/wallpapers-gallery.html`

Reads the label files, renders a self-contained HTML: per theme, palette swatches, then
items grouped **do / dont→reason**, each showing the inline (base64) thumbnail, the
matcher's verdict + `score_image_strict`, and a ✓/✗ against the human label. Per-theme
accuracy header. Regenerate after relabeling: `python3 tools/gen-gallery.py`.

## Locked decisions

1. **Static** labeler (html/js/css), theme dropdown, palette + existing-wallpaper hints.
2. Images **embedded** (base64, downscaled ≤400px) in one **`.json` per theme**; submit
   fully overwrites.
3. Matcher-vs-label disagreement → **test fails, reporting accuracy** + mismatch list.
4. Labels are **do / dont + reason**; reason drives the gallery and an informational
   gate-check (not a hard assertion).
5. Test is **data-driven**: keys off `tests/fixtures/labels/*.json`; **no files → skip with
   message**.
6. `params` (threshold/top_colors/k/max_hues) + palette stored **in the file** → hermetic,
   reproducible eval.

## File map

```
tools/
  gen-theme-data.py                 # colors.toml + backgrounds -> themes.json
  gen-gallery.py                    # label files -> docs/wallpapers-gallery.html
  fixtures-labeler/
    index.html  app.js  style.css   # static labeling form
    themes.json                     # generated palette+backgrounds data (committed)
tests/
  fixtures/labels/
    everforest.json                 # first labeled set (committed)
  test_labeled_fixtures.py          # data-driven eval
docs/
  wallpapers-gallery.html           # generated gallery (committed)
```

## Testing the tests

- `python -m unittest` green: with `everforest.json` present the eval runs; delete it and
  the eval **skips with a message** (assert this path too, e.g. point discovery at an empty
  temp dir).
- `gen-theme-data.py` / `gen-gallery.py`: smoke-tested on temp inputs (parse a fake
  `colors.toml`, assert `themes.json` shape; feed a tiny label file, assert gallery HTML
  contains the item + verdict).
- Manual: open the labeler, label a handful, submit, drop the file in, run the suite.

## Risks / notes

- **Static `file://` limits:** existing-wallpaper thumbnails may not render under browser
  `file://` restrictions — palette swatches are the guaranteed hint; wallpaper thumbnails
  degrade silently. Candidate images come via file-input/drag-drop, which always works.
- **`k` default footgun:** `dominant_colors` defaults `k=5` but the CLI/`curate` default is
  `k=8`. The label file's `params.k` (default 8) is authoritative in the test — do not copy
  the `k=5` from the existing unit tests.
- **`.gitignore`:** curated backgrounds are gitignored; confirm `tests/fixtures/`,
  `tools/`, and `docs/wallpapers-gallery.html` are **not** swept up so images/data actually
  commit.
- **Scope:** three loosely-coupled pieces (labeler+data / eval test / gallery). The plan
  phases them so each is independently testable; the eval test (D) is the core deliverable
  and can land before the gallery (E).

## Open questions

None blocking. Exact gallery styling and any labeler UX polish settled during planning.
