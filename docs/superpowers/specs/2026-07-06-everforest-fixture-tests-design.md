# Labeled fixture eval — static labeler + gallery + data-driven test

**Date:** 2026-07-06
**Branch:** `feat/wallpaper-theme-matcher`
**Depends on:** `match_wallpapers.py`, spec `2026-06-16-wallpaper-theme-matcher-design.md`
**Supersedes** the earlier auto-classified / base64-embedded drafts of this file.

## Problem

The matcher's unit tests (`tests/test_match_wallpapers.py`) validate the math with
**synthetic solid-color PNGs**. Nothing grades the full pipeline of the branch's script
(`match_wallpapers.py`) against **real photographs** judged by a **human**. Auto-deriving
fixtures from the matcher is circular — it only confirms the matcher agrees with itself.
We want a **human-labeled ground-truth set** the matcher is graded against, so a regression
that starts mis-sorting real wallpapers turns a test red.

## Goal

A reusable **labeling form** where a human sorts wallpapers into do / don't buckets (with a
reason) **per theme**, producing one data file per theme. A **data-driven test of
`match_wallpapers.py`** grades the matcher against those files, reading the **original,
full-resolution images** for accuracy. A **gallery** renders the labeled set with the
matcher's verdict for tuning.

everforest is the first theme labeled; nothing is everforest-specific — every component is
theme-agnostic and driven by whichever label files exist.

## Ground truth is authoritative

The human label is the oracle. **If the matcher disagrees with any label, the test fails**
and reports accuracy (% of items the matcher classified as the human did) plus the list of
mismatches. This makes the fixture set a real accuracy gate, not a self-agreement check.

## Originals, referenced by path

The test works on the **original images**, not downscaled copies, for accuracy. Images are
**not** copied into the repo and **not** embedded — the label file stores each image's
`basename` plus a `source_dir`, and the test reads `source_dir/basename` in place. A static
browser form cannot obtain a file's absolute path (browsers expose only the basename), so
`source_dir` is a field the user sets in the form (default `~/Wallpapers`). Consequence:
the eval is **host-dependent** — where an original is absent (CI, another host) that item
**skips with a message** rather than failing. (The matcher thumbnails to 256px internally
anyway, so this changes results by nothing; it just guarantees we never grade a lossy copy.)

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
3. **`source_dir` field** — the absolute folder the labeled originals live in
   (default `~/Wallpapers`). Stored in the output; the test resolves originals against it.
4. **Candidate images:** user drags in / file-selects wallpapers from `source_dir`
   (a static page cannot list a directory — the user supplies the files). The form reads
   each blob only to render an **in-memory preview thumbnail** (downscaled via `<canvas>`
   for display speed); the downscaled bytes are **never stored** — only the `basename` is.
5. Per image: **do / dont** toggle + **reason** select (`wrong-hue`, `polychrome`,
   `neutral`, `other`; reason enabled only for `dont`).
6. **Submit** → downloads `<theme>.json` (schema below). Submit = the whole theme file,
   **full overwrite** (no merge/append).
7. **Optional load-to-edit:** an "import existing `<theme>.json`" control repopulates the
   form (labels/reasons/source_dir; previews reappear when the user re-adds the files) so
   relabeling doesn't start from scratch; a subsequent submit still fully overwrites.

The form writes nothing to disk itself (static). The downloaded file is placed by the user
at `tests/fixtures/labels/<theme>.json`.

### C. Per-theme label file — `tests/fixtures/labels/<theme>.json`

A table of basenames + labels; the matcher config and palette travel with it so the eval is
reproducible from the file + the originals on disk:

```json
{
  "theme": "everforest",
  "source_dir": "~/Wallpapers",
  "palette": ["#2d353b", "#7fbbb3", "..."],
  "params": { "threshold": 12.0, "top_colors": 3, "k": 8, "max_hues": 4 },
  "items": [
    { "name": "forest01.jpg", "label": "do",   "reason": null },
    { "name": "desert.jpg",   "label": "dont", "reason": "wrong-hue" }
  ]
}
```

- `palette` + `params` are embedded so the verdict is reproducible independent of live
  themes and of future CLI-default changes. The form defaults `params` from the matcher's
  current CLI defaults and `palette` from `themes.json`; both editable.
- Small, human-readable, clean diffs (no image bytes). Extension `.json`.

### D. Data-driven test — `tests/test_labeled_fixtures.py` (tests `match_wallpapers.py`)

- **Discovers** all `tests/fixtures/labels/*.json`. If **none exist → skip with a message**
  (`skipTest("no labeled fixture files in tests/fixtures/labels/")`), so the suite is green
  on a fresh checkout before anyone has labeled a theme.
- For **each** label file (one `subTest` per theme so themes report separately): build the
  Lab palette from `palette`; expand `source_dir` (`os.path.expanduser`). For each item:
  resolve `path = source_dir/name`. **If the original is missing → skip that item**, note it
  in the summary (host-dependent, not a failure). Otherwise extract `mw.dominant_colors` at
  `params.k`, then compute the matcher's verdict with the file's `params`:

  ```
  assigned = (not is_polychrome(doms, max_hues)
              and not image_is_neutral(doms)
              and score_image_strict(doms, labs, top_n=top_colors) <= threshold)
  expected = (label == "do")
  ```

- Collect every mismatch (`assigned != expected`) among evaluated (non-skipped) items.
  **Assert none.** On failure the message reports **accuracy** (`matches/evaluated`), how
  many items were skipped-missing, and each mismatched `name` with matcher-verdict vs
  human-label.
- **Reason (secondary):** for a `dont` item, record which gate actually fired
  (polychrome / neutral / score) and compare to `reason`. A gate/reason mismatch is an
  **informational note in the summary, not a hard failure** (avoids brittleness when two
  gates could both reject an image). Hard failure is assignment only.

Complements — does not replace — the synthetic math tests in `test_match_wallpapers.py`.

### E. Gallery — `tools/gen-gallery.py` → `docs/wallpapers-gallery.html`

Reads the label files, renders HTML: per theme, palette swatches, then items grouped
**do / dont→reason**, each showing the original via `<img src="file://source_dir/name">`,
the matcher's verdict + `score_image_strict`, and a ✓/✗ against the human label. Per-theme
accuracy header. Because it references originals by `file://` path it renders **locally**
(not on GitHub) — matching the host-dependent nature of the eval. Regenerate after
relabeling: `python3 tools/gen-gallery.py`.

## Locked decisions

1. **Static** labeler (html/js/css), theme dropdown, palette + existing-wallpaper hints.
2. Test works on **original full-res images, referenced by `source_dir` + `basename`** — not
   copied into the repo, not embedded. Missing original → **skip with message**.
3. Matcher-vs-label disagreement → **test fails, reporting accuracy** + mismatch list.
4. Labels are **do / dont + reason**; reason drives the gallery and an informational
   gate-check (not a hard assertion).
5. Test is **data-driven** and lives beside `test_match_wallpapers.py`, testing the branch
   script `match_wallpapers.py`; keys off `tests/fixtures/labels/*.json`; **no files → skip
   with message**.
6. One **`.json` per theme** (basenames + labels + reason + palette + params); submit fully
   overwrites.

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
  test_labeled_fixtures.py          # data-driven eval of match_wallpapers.py
docs/
  wallpapers-gallery.html           # generated gallery (committed)
```

## Testing the tests

- `python -m unittest` green: with `everforest.json` present and its originals on disk the
  eval runs; with the labels dir empty the eval **skips with a message** (assert this path,
  e.g. point discovery at an empty temp dir); with a label file whose originals are absent,
  those items **skip** (assert via a temp label file naming a nonexistent basename).
- `gen-theme-data.py` / `gen-gallery.py`: smoke-tested on temp inputs (parse a fake
  `colors.toml`, assert `themes.json` shape; feed a tiny label file + a temp image, assert
  the gallery HTML contains the item + verdict).
- Manual: open the labeler, set `source_dir`, label a handful, submit, drop the file at
  `tests/fixtures/labels/everforest.json`, run the suite.

## Risks / notes

- **Host-dependent eval:** originals live outside the repo, so the accuracy gate only runs
  where they exist; elsewhere items skip. Accepted trade for grading real originals.
- **Static `file://` limits:** existing-wallpaper hint thumbnails and the gallery images may
  not render under browser `file://` restrictions. Palette swatches are the guaranteed hint;
  candidate images come via file-input/drag-drop, which always works.
- **`k` default footgun:** `dominant_colors` defaults `k=5` but the CLI/`curate` default is
  `k=8`. The label file's `params.k` (default 8) is authoritative in the test — do not copy
  the `k=5` from the existing unit tests.
- **`.gitignore`:** curated backgrounds are gitignored; confirm `tests/`, `tools/`, and
  `docs/wallpapers-gallery.html` are **not** swept up so the code/data actually commit.
- **Scope:** three loosely-coupled pieces (labeler+data / eval test / gallery). The plan
  phases them so each is independently testable; the eval test (D) is the core deliverable
  and can land before the gallery (E).

## Open questions

None blocking. Exact gallery styling and labeler UX polish settled during planning.
