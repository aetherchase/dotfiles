# Labeled Fixture Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grade `match_wallpapers.py` against a human-labeled set of real wallpapers per theme, via a static labeling form, a data-driven test, and a gallery.

**Architecture:** A static browser form emits one `<theme>.json` per theme (basenames + do/dont + reason + palette + params + source_dir). A data-driven unittest reads those files, resolves each original from `source_dir/basename`, and runs the matcher's real assignment decision (`theme_matches_image`, extracted from `curate`) — any disagreement with the human label fails the test with an accuracy report. A generator renders a local HTML gallery of labels vs matcher verdicts. Theme palettes/backgrounds for the form come from a generator over the omarchy theme dirs.

**Tech Stack:** Python 3 stdlib + Pillow (matcher already uses it); `unittest`; static HTML/CSS/vanilla JS (no deps, runs from `file://`).

## Global Constraints

- Python: **stdlib + Pillow only**. No new dependencies.
- Tests: **`unittest`**, run from repo root with `python -m unittest` (pytest collects nothing here).
- Tool scripts live in `tools/` with **underscore filenames** (`gen_theme_data.py`, `gen_gallery.py`) so tests can `import` them; hyphens are not importable.
- Static labeler: **no external JS/CSS, no network calls** — must work opened as a `file://` page. Theme data is loaded as a JS global (`themes.js`), never via `fetch` (blocked on `file://`).
- **Do not commit real wallpaper images.** Originals are referenced by `source_dir/basename`; missing original → the test skips that item.
- `theme_matches_image(...)` is the **single source** of the per-(image,theme) assignment decision — both `curate()` and the eval call it. Never duplicate the gate logic.
- DRY, YAGNI, TDD, commit per task.

---

### Task 1: Extract `theme_matches_image` (refactor the assignment decision)

**Files:**
- Modify: `match_wallpapers.py` (add function ~after `theme_is_neutral`, ~line 231; refactor `curate` inner loop ~lines 368-382)
- Test: `tests/test_match_wallpapers.py` (add `TestThemeMatches`)

**Interfaces:**
- Produces: `theme_matches_image(dominants, theme_labs, *, threshold, top_colors, max_hues) -> bool` — True iff the curator would assign this image to this theme. Consumed by `curate` (Task 1) and the eval harness (Task 3).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_match_wallpapers.py`:

```python
class TestThemeMatches(unittest.TestCase):
    GREEN = [((0, 160, 0), 1.0)]
    RED = [((190, 0, 0), 1.0)]
    GRAY = [((128, 128, 128), 1.0)]
    RAINBOW = [((255, 0, 0), 0.17), ((255, 255, 0), 0.17), ((0, 255, 0), 0.17),
               ((0, 255, 255), 0.17), ((0, 0, 255), 0.16), ((255, 0, 255), 0.16)]
    green_theme = [mw.srgb_to_lab((10, 150, 10)), mw.srgb_to_lab((40, 50, 40))]
    gray_theme = [mw.srgb_to_lab((30, 30, 30)), mw.srgb_to_lab((200, 200, 200))]
    KW = dict(threshold=18.0, top_colors=3, max_hues=4)

    def test_matching_hue_assigned(self):
        self.assertTrue(mw.theme_matches_image(self.GREEN, self.green_theme, **self.KW))

    def test_wrong_hue_rejected(self):
        self.assertFalse(mw.theme_matches_image(self.RED, self.green_theme, **self.KW))

    def test_polychrome_rejected(self):
        self.assertFalse(mw.theme_matches_image(self.RAINBOW, self.green_theme, **self.KW))

    def test_neutral_image_rejected_by_chromatic_theme(self):
        self.assertFalse(mw.theme_matches_image(self.GRAY, self.green_theme, **self.KW))

    def test_neutral_image_assigned_to_neutral_theme(self):
        self.assertTrue(mw.theme_matches_image(self.GRAY, self.gray_theme, **self.KW))

    def test_chromatic_image_rejected_by_neutral_theme(self):
        self.assertFalse(mw.theme_matches_image(self.GREEN, self.gray_theme, **self.KW))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_match_wallpapers.TestThemeMatches -v`
Expected: FAIL — `AttributeError: module 'match_wallpapers' has no attribute 'theme_matches_image'`

- [ ] **Step 3: Add the function**

In `match_wallpapers.py`, immediately after `theme_is_neutral` (before `load_themes`):

```python
def theme_matches_image(dominants: list[tuple[tuple[int, int, int], float]],
                        theme_labs: list[tuple[float, float, float]], *,
                        threshold: float, top_colors: int, max_hues: int) -> bool:
    """Would the curator assign this image to this theme? The single source of the
    per-(image, theme) decision, shared by curate() and the labeled-fixture eval.

    Order mirrors curate(): reject polychrome images outright; route by neutrality
    (grayscale image <-> grayscale theme only); otherwise the theme must cover the
    image's prominent colors within `threshold` (strict worst-color score)."""
    if is_polychrome(dominants, max_hues=max_hues):
        return False
    img_neutral = image_is_neutral(dominants)
    if theme_is_neutral(theme_labs) != img_neutral:
        return False
    if img_neutral:
        return True
    return score_image_strict(dominants, theme_labs, top_n=top_colors) <= threshold
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_match_wallpapers.TestThemeMatches -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Refactor `curate` to use it (no behavior change)**

In `match_wallpapers.py` `curate`, replace the per-image assignment block (currently the
`if is_polychrome(...)` short-circuit through the `for slug, labs in themes.items()` loop)
with:

```python
        # Reject "matches everything" images (rainbow, neon) before scoring.
        if is_polychrome(doms, max_hues=max_hues):
            polychrome += 1
            continue
        matched = False
        for slug, labs in themes.items():
            if theme_matches_image(doms, labs, threshold=threshold,
                                   top_colors=top_colors, max_hues=max_hues):
                assignments[slug].append(img)
                matched = True
        if not matched:
            dropped += 1
```

(The `polychrome` short-circuit stays for the counter; `theme_matches_image` re-checks it
harmlessly. The neutral-routing and score logic now live only in the function.)

- [ ] **Step 6: Run the full matcher suite to prove no regression**

Run: `python -m unittest tests.test_match_wallpapers -v`
Expected: PASS (all existing classes incl. `TestCurate`, `TestNeutralCurate`, plus `TestThemeMatches`)

- [ ] **Step 7: Commit**

```bash
git add match_wallpapers.py tests/test_match_wallpapers.py
git commit -m "refactor(wallpapers): extract theme_matches_image decision"
```

---

### Task 2: Theme data generator → `themes.js`

**Files:**
- Create: `tools/gen_theme_data.py`
- Create (generated, committed): `tools/fixtures-labeler/themes.js`
- Test: `tests/test_gen_theme_data.py`

**Interfaces:**
- Consumes: `match_wallpapers.parse_palette`, `match_wallpapers.IMAGE_EXTS`, `DEFAULT_STOCK`, `DEFAULT_USER`.
- Produces: `collect(stock_dir, user_dir) -> dict[str, {"palette": list[str], "backgrounds": list[str]}]`; `main()` writes `tools/fixtures-labeler/themes.js` containing `window.FIXTURE_THEMES = {...};`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_gen_theme_data.py`:

```python
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import gen_theme_data as g


class TestCollect(unittest.TestCase):
    def _theme(self, root, slug, palette_body, backgrounds=()):
        d = os.path.join(root, slug)
        os.makedirs(d)
        with open(os.path.join(d, "colors.toml"), "w") as f:
            f.write(palette_body)
        if backgrounds:
            bg = os.path.join(d, "backgrounds")
            os.makedirs(bg)
            for name in backgrounds:
                open(os.path.join(bg, name), "w").close()

    def test_palette_hex_and_backgrounds(self):
        with tempfile.TemporaryDirectory() as stock:
            self._theme(stock, "everforest",
                        'background = "#2d353b"\naccent = "#7fbbb3"\ncolor1 = "#e67e80"\n',
                        backgrounds=("a.jpg", "b.png", "notes.txt"))
            data = g.collect(stock, os.path.join(stock, "none"))
        self.assertIn("everforest", data)
        self.assertEqual(data["everforest"]["palette"][:2], ["#2d353b", "#7fbbb3"])
        bgs = [os.path.basename(p) for p in data["everforest"]["backgrounds"]]
        self.assertEqual(sorted(bgs), ["a.jpg", "b.png"])   # non-image skipped

    def test_theme_without_palette_skipped(self):
        with tempfile.TemporaryDirectory() as stock:
            os.makedirs(os.path.join(stock, "empty"))
            open(os.path.join(stock, "empty", "colors.toml"), "w").close()
            data = g.collect(stock, os.path.join(stock, "none"))
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_gen_theme_data -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gen_theme_data'`

- [ ] **Step 3: Write the generator**

Create `tools/gen_theme_data.py`:

```python
#!/usr/bin/env python3
"""Generate tools/fixtures-labeler/themes.js (window.FIXTURE_THEMES) from omarchy
theme palettes + backgrounds, for the static labeling form's hints/dropdown."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import match_wallpapers as mw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures-labeler", "themes.js")


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def collect(stock_dir: str, user_dir: str) -> dict:
    """Map theme slug -> {palette: [hex], backgrounds: [abs paths]} (user wins on clash)."""
    out: dict[str, dict] = {}
    for base in (stock_dir, user_dir):
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            tdir = os.path.join(base, slug)
            toml_path = os.path.join(tdir, "colors.toml")
            if not os.path.isfile(toml_path):
                continue
            rgbs = mw.parse_palette(toml_path)
            if not rgbs:
                continue
            bg_dir = os.path.join(tdir, "backgrounds")
            backgrounds = []
            if os.path.isdir(bg_dir):
                backgrounds = [os.path.join(bg_dir, f) for f in sorted(os.listdir(bg_dir))
                               if f.lower().endswith(mw.IMAGE_EXTS)]
            out[slug] = {"palette": [_hex(c) for c in rgbs], "backgrounds": backgrounds}
    return out


def main(argv=None) -> int:
    data = collect(mw.DEFAULT_STOCK, mw.DEFAULT_USER)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("window.FIXTURE_THEMES = " + json.dumps(data, indent=2) + ";\n")
    print(f"Wrote {len(data)} theme(s) to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_gen_theme_data -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Generate the real data file**

Run: `python3 tools/gen_theme_data.py`
Expected: `Wrote 20 theme(s) to .../themes.js` (19 stock + `aether`)
Verify: `head -3 tools/fixtures-labeler/themes.js` shows `window.FIXTURE_THEMES = {`

- [ ] **Step 6: Commit**

```bash
git add tools/gen_theme_data.py tools/fixtures-labeler/themes.js tests/test_gen_theme_data.py
git commit -m "feat(wallpapers): theme-data generator for the labeler"
```

---

### Task 3: Data-driven eval test

**Files:**
- Create: `tests/test_labeled_fixtures.py`

**Interfaces:**
- Consumes: `match_wallpapers.theme_matches_image` (Task 1), `dominant_colors`, `score_image_strict`, `hex_to_rgb`, `srgb_to_lab`, `is_polychrome`, `image_is_neutral`, `theme_is_neutral`.
- Label file schema (Task 6 produces the real one; tests here build temp ones):
  `{theme, source_dir, palette:[hex], params:{threshold,top_colors,k,max_hues}, items:[{name,label,reason}]}`.

- [ ] **Step 1: Write the failing test (harness meta-tests)**

Create `tests/test_labeled_fixtures.py`:

```python
import glob
import json
import os
import tempfile
import unittest

from PIL import Image

import match_wallpapers as mw

LABELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "labels")
_GREEN_PARAMS = {"threshold": 18.0, "top_colors": 3, "k": 5, "max_hues": 4}


def _labs(hexes):
    return [mw.srgb_to_lab(mw.hex_to_rgb(h)) for h in hexes]


def _which_gate(doms, labs, params):
    """Best-effort reason a `dont` was rejected (informational only)."""
    if mw.is_polychrome(doms, max_hues=params["max_hues"]):
        return "polychrome"
    if mw.image_is_neutral(doms) or mw.theme_is_neutral(labs) != mw.image_is_neutral(doms):
        return "neutral"
    return "wrong-hue"


def evaluate(label_file):
    """Grade the matcher against one label file.
    Returns (mismatches, evaluated, skipped_missing, reason_notes)."""
    with open(label_file) as f:
        data = json.load(f)
    labs = _labs(data["palette"])
    p = data["params"]
    src = os.path.expanduser(data["source_dir"])
    mismatches, evaluated, skipped, notes = [], 0, [], []
    for item in data["items"]:
        path = os.path.join(src, item["name"])
        if not os.path.isfile(path):
            skipped.append(item["name"])
            continue
        try:
            doms = mw.dominant_colors(path, k=p["k"])
        except Exception as e:                      # unreadable/truncated
            skipped.append(f'{item["name"]} ({e})')
            continue
        assigned = mw.theme_matches_image(doms, labs, threshold=p["threshold"],
                                          top_colors=p["top_colors"], max_hues=p["max_hues"])
        expected = item["label"] == "do"
        evaluated += 1
        if assigned != expected:
            mismatches.append((item["name"], "assigned" if assigned else "rejected", item["label"]))
        elif item["label"] == "dont" and item.get("reason"):
            gate = _which_gate(doms, labs, p)
            if gate != item["reason"]:
                notes.append(f'{item["name"]}: labeled {item["reason"]}, gate fired {gate}')
    return mismatches, evaluated, skipped, notes


class TestEvalHarness(unittest.TestCase):
    def _write_img(self, d, name, color):
        Image.new("RGB", (160, 90), color).save(os.path.join(d, name))

    def _label_file(self, d, items, palette=("#0a960a", "#283228")):
        lf = os.path.join(d, "everforest.json")
        with open(lf, "w") as f:
            json.dump({"theme": "everforest", "source_dir": d, "palette": list(palette),
                       "params": _GREEN_PARAMS, "items": items}, f)
        return lf

    def test_agreeing_labels_have_no_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_img(d, "green.png", (0, 170, 0))
            self._write_img(d, "red.png", (190, 0, 0))
            lf = self._label_file(d, [
                {"name": "green.png", "label": "do", "reason": None},
                {"name": "red.png", "label": "dont", "reason": "wrong-hue"},
            ])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(mism, [])
        self.assertEqual(ev, 2)
        self.assertEqual(skip, [])

    def test_disagreement_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_img(d, "red.png", (190, 0, 0))
            lf = self._label_file(d, [{"name": "red.png", "label": "do", "reason": None}])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(len(mism), 1)          # red should NOT match green -> mislabeled do
        self.assertEqual(ev, 1)

    def test_missing_original_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            lf = self._label_file(d, [{"name": "ghost.png", "label": "do", "reason": None}])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(ev, 0)
        self.assertEqual(skip, ["ghost.png"])

    def test_reason_note_on_gate_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_img(d, "gray.png", (128, 128, 128))   # rejected by neutral gate
            lf = self._label_file(d, [{"name": "gray.png", "label": "dont", "reason": "wrong-hue"}])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(mism, [])              # correctly rejected -> not a hard failure
        self.assertEqual(len(notes), 1)         # but reason mismatch noted


class TestLabeledFixtures(unittest.TestCase):
    def test_all_label_files(self):
        files = sorted(glob.glob(os.path.join(LABELS_DIR, "*.json")))
        if not files:
            self.skipTest(f"no labeled fixture files in {LABELS_DIR}")
        for lf in files:
            with self.subTest(theme=os.path.basename(lf)):
                mism, ev, skip, notes = evaluate(lf)
                if ev == 0:
                    self.skipTest(f"{os.path.basename(lf)}: no originals present "
                                  f"({len(skip)} missing)")
                acc = (ev - len(mism)) / ev
                msg = (f"accuracy {ev - len(mism)}/{ev} = {acc:.0%}; "
                       f"skipped-missing={len(skip)}; mismatches={mism}; reason-notes={notes}")
                self.assertEqual(mism, [], msg)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify the harness tests pass and the integration skips**

Run: `python -m unittest tests.test_labeled_fixtures -v`
Expected: `TestEvalHarness` 4 PASS; `TestLabeledFixtures.test_all_label_files` **skipped**
("no labeled fixture files in .../fixtures/labels") — the dir does not exist yet.

- [ ] **Step 3: Commit**

```bash
git add tests/test_labeled_fixtures.py
git commit -m "test(wallpapers): data-driven eval of matcher vs human labels"
```

---

### Task 4: Static labeling form

**Files:**
- Create: `tools/fixtures-labeler/index.html`
- Create: `tools/fixtures-labeler/style.css`
- Create: `tools/fixtures-labeler/app.js`

**Interfaces:**
- Consumes: `window.FIXTURE_THEMES` from `themes.js` (Task 2).
- Produces: a downloaded `<theme>.json` matching the Task 3 schema. Pure function
  `buildThemeFile(theme, sourceDir, palette, params, rows) -> object` (exported for node test).

- [ ] **Step 1: Write the failing node smoke test for the pure serializer**

Create `tools/fixtures-labeler/app.test.js`:

```javascript
const assert = require("assert");
const { buildThemeFile } = require("./app.js");

const out = buildThemeFile(
  "everforest", "~/Wallpapers",
  ["#2d353b", "#7fbbb3"],
  { threshold: 12, top_colors: 3, k: 8, max_hues: 4 },
  [
    { name: "a.jpg", label: "do", reason: null },
    { name: "b.jpg", label: "dont", reason: "wrong-hue" },
  ]
);
assert.strictEqual(out.theme, "everforest");
assert.strictEqual(out.source_dir, "~/Wallpapers");
assert.deepStrictEqual(out.params, { threshold: 12, top_colors: 3, k: 8, max_hues: 4 });
assert.strictEqual(out.items.length, 2);
assert.strictEqual(out.items[1].reason, "wrong-hue");
// a `do` row must not carry a reason
assert.strictEqual(out.items[0].reason, null);
console.log("app.js buildThemeFile OK");
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node tools/fixtures-labeler/app.test.js`
Expected: FAIL — `Cannot find module './app.js'` (or `buildThemeFile is not a function`).
(If `node` is unavailable, note it and rely on the manual acceptance in Step 6.)

- [ ] **Step 3: Write `app.js`**

Create `tools/fixtures-labeler/app.js`:

```javascript
"use strict";

// Pure: assemble the theme file object from UI state. Reason is kept only for `dont`.
function buildThemeFile(theme, sourceDir, palette, params, rows) {
  return {
    theme,
    source_dir: sourceDir,
    palette,
    params,
    items: rows.map((r) => ({
      name: r.name,
      label: r.label,
      reason: r.label === "dont" ? (r.reason || "other") : null,
    })),
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { buildThemeFile };
}

// ---- Browser glue (skipped under node) ----
if (typeof document !== "undefined") {
  const THEMES = window.FIXTURE_THEMES || {};
  const rows = []; // {name, label, reason, el}
  const $ = (id) => document.getElementById(id);

  function fillThemes() {
    const sel = $("theme");
    Object.keys(THEMES).sort().forEach((slug) => {
      const o = document.createElement("option");
      o.value = o.textContent = slug;
      sel.appendChild(o);
    });
    sel.addEventListener("change", showHints);
    showHints();
  }

  function showHints() {
    const t = THEMES[$("theme").value] || { palette: [], backgrounds: [] };
    $("palette").innerHTML = t.palette
      .map((h) => `<span class="sw" style="background:${h}" title="${h}"></span>`)
      .join("");
    $("bgs").innerHTML = t.backgrounds
      .map((p) => `<img class="bg" src="file://${p}" alt="">`)
      .join("");
  }

  function addFiles(fileList) {
    for (const file of fileList) {
      const row = { name: file.name, label: "dont", reason: "wrong-hue" };
      const el = document.createElement("div");
      el.className = "row";
      const url = URL.createObjectURL(file);
      el.innerHTML =
        `<img class="thumb" src="${url}">` +
        `<span class="nm">${file.name}</span>` +
        `<select class="lab"><option value="do">do</option>` +
        `<option value="dont" selected>dont</option></select>` +
        `<select class="rsn">` +
        ["wrong-hue", "polychrome", "neutral", "other"]
          .map((r) => `<option value="${r}">${r}</option>`)
          .join("") +
        `</select>`;
      const lab = el.querySelector(".lab");
      const rsn = el.querySelector(".rsn");
      lab.addEventListener("change", () => {
        row.label = lab.value;
        rsn.disabled = lab.value === "do";
      });
      rsn.addEventListener("change", () => (row.reason = rsn.value));
      row.el = el;
      rows.push(row);
      $("rows").appendChild(el);
    }
  }

  function currentParams() {
    return {
      threshold: parseFloat($("threshold").value),
      top_colors: parseInt($("top_colors").value, 10),
      k: parseInt($("k").value, 10),
      max_hues: parseInt($("max_hues").value, 10),
    };
  }

  function exportFile() {
    const theme = $("theme").value;
    const data = buildThemeFile(
      theme, $("source_dir").value, (THEMES[theme] || {}).palette || [],
      currentParams(), rows
    );
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = theme + ".json";
    a.click();
  }

  function importFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      const d = JSON.parse(reader.result);
      $("theme").value = d.theme;
      $("source_dir").value = d.source_dir;
      $("threshold").value = d.params.threshold;
      $("top_colors").value = d.params.top_colors;
      $("k").value = d.params.k;
      $("max_hues").value = d.params.max_hues;
      showHints();
      $("rows").innerHTML = "";
      rows.length = 0;
      // Prefill label/reason rows (previews reappear when the user re-adds the images).
      d.items.forEach((it) => {
        const el = document.createElement("div");
        el.className = "row";
        el.innerHTML = `<span class="nm">${it.name}</span> — ${it.label}` +
          (it.reason ? ` (${it.reason})` : "") + " <em>re-add file for preview</em>";
        $("rows").appendChild(el);
        rows.push({ name: it.name, label: it.label, reason: it.reason, el });
      });
    };
    reader.readAsText(file);
  }

  window.addEventListener("DOMContentLoaded", () => {
    fillThemes();
    $("files").addEventListener("change", (e) => addFiles(e.target.files));
    $("export").addEventListener("click", exportFile);
    $("import").addEventListener("change", (e) => e.target.files[0] && importFile(e.target.files[0]));
    const dz = $("drop");
    dz.addEventListener("dragover", (e) => e.preventDefault());
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      addFiles(e.dataTransfer.files);
    });
  });
}
```

- [ ] **Step 4: Run the node smoke test to verify it passes**

Run: `node tools/fixtures-labeler/app.test.js`
Expected: `app.js buildThemeFile OK`

- [ ] **Step 5: Write `index.html` and `style.css`**

Create `tools/fixtures-labeler/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wallpaper fixture labeler</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>Wallpaper fixture labeler</h1>
  <div class="bar">
    <label>Theme <select id="theme"></select></label>
    <label>Source dir <input id="source_dir" value="~/Wallpapers" size="30"></label>
  </div>
  <div class="bar">
    <label>threshold <input id="threshold" type="number" step="0.5" value="12"></label>
    <label>top_colors <input id="top_colors" type="number" value="3"></label>
    <label>k <input id="k" type="number" value="8"></label>
    <label>max_hues <input id="max_hues" type="number" value="4"></label>
  </div>
  <h3>Palette hint</h3><div id="palette"></div>
  <h3>Existing omarchy backgrounds</h3><div id="bgs"></div>
  <h3>Candidates</h3>
  <div id="drop">Drop wallpapers here, or <input id="files" type="file" accept="image/*" multiple></div>
  <div id="rows"></div>
  <div class="bar">
    <button id="export">Download &lt;theme&gt;.json</button>
    <label>Import existing <input id="import" type="file" accept="application/json"></label>
  </div>
  <script src="themes.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

Create `tools/fixtures-labeler/style.css`:

```css
body { font-family: sans-serif; margin: 1.5rem; background: #1c1c1c; color: #ddd; }
.bar { margin: .5rem 0; display: flex; gap: 1rem; flex-wrap: wrap; align-items: center; }
input[type=number] { width: 5rem; }
.sw { display: inline-block; width: 26px; height: 26px; border-radius: 4px; margin: 2px;
      border: 1px solid #0006; }
.bg, .thumb { height: 70px; border-radius: 4px; vertical-align: middle; }
#drop { border: 2px dashed #666; padding: 1rem; border-radius: 6px; margin: .5rem 0; }
.row { display: flex; gap: .6rem; align-items: center; margin: .3rem 0; }
.nm { min-width: 16rem; font-size: 13px; word-break: break-all; }
button { padding: .4rem .8rem; border-radius: 6px; cursor: pointer; }
```

- [ ] **Step 6: Manual acceptance**

1. `python3 tools/gen_theme_data.py` (ensures `themes.js` exists — done in Task 2).
2. Open `tools/fixtures-labeler/index.html` in a browser (e.g. `xdg-open`).
3. Verify: theme dropdown lists themes; selecting **everforest** shows palette swatches
   (background/accent/color1.. greens). Background thumbnails may or may not render under
   `file://` — that is acceptable (palette swatches are the guaranteed hint).
4. Add 2-3 wallpapers via the file picker and the drop zone; toggle do/dont; pick reasons.
5. Click **Download** → confirm a `everforest.json` downloads whose `items` match the UI
   and whose `do` rows have `reason: null`.

- [ ] **Step 7: Commit**

```bash
git add tools/fixtures-labeler/index.html tools/fixtures-labeler/style.css \
        tools/fixtures-labeler/app.js tools/fixtures-labeler/app.test.js
git commit -m "feat(wallpapers): static fixture labeling form"
```

---

### Task 5: Gallery generator

**Files:**
- Create: `tools/gen_gallery.py`
- Test: `tests/test_gen_gallery.py`

**Interfaces:**
- Consumes: `match_wallpapers.theme_matches_image`, `score_image_strict`, `dominant_colors`, `hex_to_rgb`, `srgb_to_lab`.
- Produces: `render(label_files: list[str]) -> str` (HTML); `main()` writes `docs/wallpapers-gallery.html`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_gen_gallery.py`:

```python
import json
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import gen_gallery as gg


class TestRender(unittest.TestCase):
    def _fixture(self, d):
        Image.new("RGB", (160, 90), (0, 170, 0)).save(os.path.join(d, "green.png"))
        lf = os.path.join(d, "everforest.json")
        with open(lf, "w") as f:
            json.dump({"theme": "everforest", "source_dir": d,
                       "palette": ["#0a960a", "#283228"],
                       "params": {"threshold": 18.0, "top_colors": 3, "k": 5, "max_hues": 4},
                       "items": [{"name": "green.png", "label": "do", "reason": None}]}, f)
        return lf

    def test_html_has_theme_item_and_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            html = gg.render([self._fixture(d)])
        self.assertIn("everforest", html)
        self.assertIn("green.png", html)
        self.assertIn("assigned", html)          # green matches green -> assigned
        self.assertIn("accuracy", html)

    def test_missing_original_marked(self):
        with tempfile.TemporaryDirectory() as d:
            lf = os.path.join(d, "t.json")
            with open(lf, "w") as f:
                json.dump({"theme": "t", "source_dir": d, "palette": ["#0a960a"],
                           "params": {"threshold": 18.0, "top_colors": 3, "k": 5, "max_hues": 4},
                           "items": [{"name": "ghost.png", "label": "do", "reason": None}]}, f)
            html = gg.render([lf])
        self.assertIn("missing", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_gen_gallery -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gen_gallery'`

- [ ] **Step 3: Write the generator**

Create `tools/gen_gallery.py`:

```python
#!/usr/bin/env python3
"""Render docs/wallpapers-gallery.html from tests/fixtures/labels/*.json: each labeled
image with the matcher's verdict + score, checked against the human label."""
import glob
import html
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import match_wallpapers as mw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LABELS = os.path.join(ROOT, "tests", "fixtures", "labels")
OUT = os.path.join(ROOT, "docs", "wallpapers-gallery.html")

_STYLE = ("body{font-family:sans-serif;background:#1c1c1c;color:#ddd;margin:1.5rem}"
          "img{height:90px;border-radius:4px}"
          ".item{display:inline-block;margin:6px;text-align:center;font-size:12px;"
          "vertical-align:top;max-width:150px}"
          ".ok{outline:2px solid #7fbb7f}.bad{outline:2px solid #e06c6c}"
          ".sw{display:inline-block;width:22px;height:22px;border-radius:3px;margin:1px}")


def _labs(hexes):
    return [mw.srgb_to_lab(mw.hex_to_rgb(h)) for h in hexes]


def render(label_files: list[str]) -> str:
    out = ["<!doctype html><meta charset=utf-8><title>Wallpaper matcher gallery</title>",
           f"<style>{_STYLE}</style>"]
    for lf in label_files:
        with open(lf) as f:
            data = json.load(f)
        labs = _labs(data["palette"])
        p = data["params"]
        src = os.path.expanduser(data["source_dir"])
        out.append(f"<h2>{html.escape(data['theme'])}</h2><div>")
        out += [f'<span class="sw" style="background:{html.escape(h)}"></span>'
                for h in data["palette"]]
        out.append("</div>")
        groups: dict[str, list] = {}
        for it in data["items"]:
            key = "do" if it["label"] == "do" else f'dont / {it.get("reason") or "other"}'
            groups.setdefault(key, []).append(it)
        ev = ok = 0
        body = []
        for key in sorted(groups):
            body.append(f"<h3>{html.escape(key)}</h3>")
            for it in groups[key]:
                path = os.path.join(src, it["name"])
                score = None
                cls = ""
                if os.path.isfile(path):
                    doms = mw.dominant_colors(path, k=p["k"])
                    assigned = mw.theme_matches_image(
                        doms, labs, threshold=p["threshold"],
                        top_colors=p["top_colors"], max_hues=p["max_hues"])
                    score = round(mw.score_image_strict(doms, labs, top_n=p["top_colors"]), 1)
                    expected = it["label"] == "do"
                    ev += 1
                    ok += int(assigned == expected)
                    cls = "ok" if assigned == expected else "bad"
                    verdict = "assigned" if assigned else "rejected"
                else:
                    verdict = "missing"
                body.append(
                    f'<div class="item {cls}"><img src="file://{html.escape(path)}" alt="">'
                    f'<br>{html.escape(it["name"])}<br>{verdict} score={score}</div>')
        acc = f"{ok}/{ev} = {ok / ev:.0%}" if ev else "n/a (no originals present)"
        out.append(f"<p>accuracy: {acc}</p>")
        out += body
    return "".join(out)


def main(argv=None) -> int:
    files = sorted(glob.glob(os.path.join(LABELS, "*.json")))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(files))
    print(f"Wrote {OUT} ({len(files)} theme file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_gen_gallery -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/gen_gallery.py tests/test_gen_gallery.py
git commit -m "feat(wallpapers): gallery generator for labeled fixtures"
```

---

### Task 6: Wiring, docs, full-suite gate

**Files:**
- Verify: `.gitignore` (no change expected)
- Modify: `CLAUDE.md` (ownership table + wallpapers reference)
- Modify: `README.md` (brief pointer)

- [ ] **Step 1: Confirm nothing new is gitignored**

Run: `git check-ignore -v tools/fixtures-labeler/themes.js tests/fixtures/labels/everforest.json docs/wallpapers-gallery.html tools/gen_theme_data.py || echo "NONE IGNORED (good)"`
Expected: `NONE IGNORED (good)` (the wallpaper-backgrounds rule must not match these paths).

- [ ] **Step 2: Add ownership rows to `CLAUDE.md`**

In the "Ownership boundary" table (after the `match_wallpapers.py` row), add:

```markdown
| `tools/gen_theme_data.py`, `tools/fixtures-labeler/` | wallpapers | static labeling form + its generated `themes.js` (palette/background hints) for building per-theme do/dont fixture sets |
| `tools/gen_gallery.py` | wallpapers | renders `docs/wallpapers-gallery.html` from the label files (matcher verdict vs human label) |
| `tests/fixtures/labels/<theme>.json` | wallpapers | human-labeled do/dont ground truth per theme; consumed by `tests/test_labeled_fixtures.py` |
```

And extend the **wallpapers** bullet in "References" with one sentence:

```markdown
Labeled-fixture eval: `tools/fixtures-labeler/` (static form) writes `tests/fixtures/labels/<theme>.json` (basenames + do/dont + reason + palette + params + source_dir); `tests/test_labeled_fixtures.py` grades `match_wallpapers.py` on the **original** images (referenced by `source_dir/basename`, missing → skip) and fails with an accuracy report on any disagreement; `python3 tools/gen_gallery.py` renders the gallery. Regenerate form data with `python3 tools/gen_theme_data.py`.
```

- [ ] **Step 3: Add a README pointer**

Append to `README.md` under the wallpapers area (or as a new line in the relevant list):

```markdown
- Wallpaper fixture labeler: open `tools/fixtures-labeler/index.html`, label do/dont per theme, drop the downloaded `<theme>.json` into `tests/fixtures/labels/`. `python -m unittest` then grades the matcher against it.
```

- [ ] **Step 4: Run the full test suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS across `test_match_wallpapers`, `test_gen_theme_data`, `test_gen_gallery`,
`test_labeled_fixtures` (its integration case **skips** — no label file committed yet).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs(wallpapers): document the labeled-fixture eval workflow"
```

---

### Task 7 (human handoff): Label everforest and grade the matcher

**Not agent-executed** — requires human judgement (auto-labeling would be circular, the
whole point of the design). Hand these steps to the user:

- [ ] Open `tools/fixtures-labeler/index.html`, select **everforest**, set `source_dir` to
  `~/Wallpapers`.
- [ ] Add candidate wallpapers; mark clear **do**s (green/forest) and **dont**s with reasons
  (`wrong-hue` / `polychrome` / `neutral`). Aim for a handful each.
- [ ] Download `everforest.json`, place it at `tests/fixtures/labels/everforest.json`.
- [ ] Run `python -m unittest tests.test_labeled_fixtures -v`.
  - Green → the matcher agrees with every label at current defaults.
  - Red → read the accuracy line + mismatch list: either fix a borderline label, or you
    have found a real matcher weakness to tune (`threshold`/`max_hues`/…). Record the
    decision; the label file is the regression baseline going forward.
- [ ] `python3 tools/gen_gallery.py` and open `docs/wallpapers-gallery.html` to eyeball.
- [ ] Commit `tests/fixtures/labels/everforest.json` (and the gallery if desired).

---

## Self-Review

**Spec coverage:**
- Static labeler (html/js/css), theme picker, palette + background hints → Task 4 + Task 2.
- Per-theme file, submit fully overwrites → Task 4 (`exportFile` writes a whole `<theme>.json`).
- Originals referenced by path, missing → skip → Task 3 (`evaluate` skip branch) + Task 5.
- Matcher-vs-label disagreement fails with accuracy → Task 3 (`TestLabeledFixtures`).
- do/dont + reason; reason = informational gate-check → Task 3 (`_which_gate`, notes).
- Data-driven, no file → skip with message → Task 3 Step 2.
- Eval tests the branch script `match_wallpapers.py` via `theme_matches_image` → Task 1 + Task 3.
- `k` default footgun handled → real label files default `k=8` (form field); harness meta-tests use `k=5` only because their synthetic solids are trivial. Documented in the form defaults.

**Placeholder scan:** none — every step ships real code/commands.

**Type consistency:** `theme_matches_image(dominants, theme_labs, *, threshold, top_colors, max_hues)` is defined in Task 1 and called identically in Tasks 3 and 5. Label-file schema keys (`theme`, `source_dir`, `palette`, `params.{threshold,top_colors,k,max_hues}`, `items[].{name,label,reason}`) are consistent across the form (Task 4), eval (Task 3), and gallery (Task 5). `buildThemeFile` signature matches between `app.js` and `app.test.js`.
