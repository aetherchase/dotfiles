# Smart Wallpaper → Theme Matcher

**Date:** 2026-06-16
**Feature package:** `wallpapers`
**Status:** Approved design

## Goal

Curate a personal wallpaper collection into omarchy's per-theme background
rotation by **color affinity**: each wallpaper is assigned to *every* theme whose
palette it resembles, so `omarchy theme bg next` cycles only on-palette
wallpapers for the active theme. Portrait/mobile shots are filtered out. Nothing
binary enters git — only gitignored symlinks.

## Background (how omarchy consumes this)

`omarchy theme bg next` builds its candidate list with:

```
find -L "$HOME/.config/omarchy/backgrounds/$THEME_NAME/" \
        "$HOME/.config/omarchy/current/theme/backgrounds/" -maxdepth 1 -type f
```

- `$THEME_NAME` is the theme **slug** = the theme directory name = the content of
  `~/.config/omarchy/current/theme.name` (e.g. `everforest`).
- `find -L` follows symlinks, so the per-theme dir AND the files inside it may be
  symlinks; it resolves multiple hops.
- Each theme ships its palette at
  `~/.local/share/omarchy/themes/<slug>/colors.toml` (user themes:
  `~/.config/omarchy/themes/<slug>/colors.toml`). Format: `accent`, `background`,
  `foreground`, `color0`–`color15`, all `#rrggbb`.

**Stow limitation (learned):** `stow` aborts when a package contains an absolute
symlink ("source is an absolute symlink … All operations aborted"). Therefore the
live `~/.config/omarchy/backgrounds/<slug>` links are created **directly by the
script**, not via stow. The `wallpapers` package tracks only a `.gitkeep`
(stow-ignored) so it stays a selectable feature.

## Architecture

Single script **`match-wallpapers.py`** at the repo top level (beside
`apply.sh`; repo tooling lives above `features/` so stow never sees it).

### Layout produced

```
features/wallpapers/.config/omarchy/backgrounds/        # in repo, gitignored (except .gitkeep)
  .gitkeep                                               # tracked; keeps package selectable
  everforest/                                            # gitignored dir
    14214893842680.jpg -> /home/keroqq/Wallpapers/14214893842680.jpg
    ...
  tokyo-night/
    ...

~/.config/omarchy/backgrounds/                           # NOT in repo
  everforest -> <repo>/features/wallpapers/.config/omarchy/backgrounds/everforest   # dir symlink
  tokyo-night -> <repo>/.../backgrounds/tokyo-night
```

`find -L` resolves the two hops: `~/.config/.../everforest` (dir symlink) →
repo `everforest/` → each pic symlink → `~/Wallpapers/<pic>`.

Only themes that received ≥1 match get a repo dir and a `~/.config` dir-symlink.

### Modes

| Invocation | Interactive | What it does |
|------------|-------------|--------------|
| `match-wallpapers.py` | yes | Full curate pass (below). |
| `match-wallpapers.py --relink` | no | Recreate `~/.config` dir-symlinks for every populated repo theme dir. Idempotent. Called by `apply.sh` when `wallpapers` is selected. |
| `match-wallpapers.py --unlink` | no | Remove the `~/.config/omarchy/backgrounds/<slug>` symlinks the script owns (only entries that are symlinks). Called by `apply.sh` on deselect. |

Flags (curate mode): `--source DIR` (default `~/Wallpapers`), `--min-ratio FLOAT`
(default `1.0`), `--threshold FLOAT` (CIEDE2000 cutoff, default `18.0`),
`--colors INT` (dominant colors per image, default `5`), `--yes` (skip the
dry-run confirmation). Interactive prompts back the source folder when not
passed; flags override prompts.

### Curate pipeline

1. **Resolve source** — `--source` or prompt (default `~/Wallpapers`). Abort if missing.
2. **Enumerate** — `*.jpg/.jpeg/.png/.webp` (case-insensitive), non-recursive.
3. **Aspect filter** — open with Pillow, compute `w/h`; keep `ratio >= --min-ratio`
   (default 1.0 ⇒ portrait/mobile dropped, square + landscape kept). Unreadable
   images are skipped with a warning.
4. **Dominant colors** — `Image.convert('RGB').quantize(colors=k, method=Image.Quantize.MEDIANCUT)`;
   read the palette + per-index pixel counts → list of `(rgb, weight)` where weight
   is the pixel fraction. (Downscale to ≤256px longest side first for speed.)
5. **Theme palettes** — parse each `colors.toml`; matching set = `background`,
   `accent`, and `color1..6` + `color9..14` (skip near-black/near-white
   `color0/7/8/15` which carry little hue signal). Convert each to Lab once.
6. **Score** — for each image dominant color, nearest theme-color ΔE (CIEDE2000);
   theme score = Σ(weightᵢ · min_ΔEᵢ). Image joins a theme iff `score <= --threshold`.
   An image may join many themes or none.
7. **Dry run** — print a table: theme → match count, plus "dropped (no theme): N"
   and "filtered (ratio): M". Prompt to proceed unless `--yes`.
8. **Write** — remove existing repo per-theme dirs under the package, recreate them,
   and for each (theme, image) match create `…/backgrounds/<slug>/<basename>` →
   absolute path in source. Then **relink** (mode below) so `~/.config` reflects the
   new set; prune `~/.config` symlinks for themes that ended up empty.

### Color math (inline, no deps)

- `srgb_to_lab(rgb)` — sRGB → linear → XYZ (D65) → CIE Lab.
- `ciede2000(lab1, lab2)` — standard ΔE₀₀ implementation.
- Unit-tested against published reference pairs (Sharma et al. test data).

## apply.sh integration

- Pre-stow (when `wallpapers` selected): replace the
  `link-omarchy-wallpapers.sh` call with `match-wallpapers.py --relink || true`.
- Deselection loop (`pkg == wallpapers`): replace with
  `match-wallpapers.py --unlink || true`.
- Curation is **never** run by `apply.sh` (slow + interactive); it is a manual
  step the user runs when adding wallpapers or themes.
- Delete `link-omarchy-wallpapers.sh`.

## Git / ownership

- `.gitignore` already carries:
  ```
  features/wallpapers/.config/omarchy/backgrounds/*
  !features/wallpapers/.config/omarchy/backgrounds/.gitkeep
  ```
  This ignores every per-theme dir + pic symlink; only `.gitkeep` is tracked.
- `features/.stow-local-ignore` already carries `\.gitkeep` so the keeper is never
  symlinked into `~/.config`.
- `features.conf` already lists `wallpapers`.

## Dependencies

- **Pillow** (present: 12.2.0). No others — CIEDE2000/Lab inline.

## Testing (TDD)

Pure functions first, with tests:
- `passes_ratio(w, h, min_ratio)` — boundary cases (portrait rejected, 1:1 kept).
- `srgb_to_lab` — known sRGB→Lab conversions.
- `ciede2000` — Sharma reference pairs (tolerance 1e-4).
- `score_image(dominants, theme_lab)` and threshold join — synthetic palettes
  (an all-green image joins a green theme, not a red one).
- `parse_colors_toml` — sample file → expected color set.

Integration (tmpdir, real FS):
- `--relink` creates dir-symlinks for populated themes only; idempotent.
- `--unlink` removes only symlinks the script owns, leaves real dirs alone.
- A tiny end-to-end on 2–3 generated solid-color PNGs against 2 fake themes.

## Out of scope / YAGNI

- Multi-monitor / per-resolution sets (single 16:9 monitor).
- Re-encoding or cropping wallpapers.
- Watching the source folder for changes (manual re-run).
- GUI / preview thumbnails (dry-run table suffices).
```
