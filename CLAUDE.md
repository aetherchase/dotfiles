# CLAUDE.md

Personal Arch Linux + Omarchy + Hyprland dotfiles managed with GNU Stow. Files live under `features/<package>/` and each maps 1:1 to `$HOME` via symlinks. The repo is **feature-sliced**: `apply.sh` stows a per-host subset of packages (see [Feature packages](#feature-packages)).

## Commands

```bash
# Install the default feature set (features.conf), or a per-host subset (features.local)
./apply.sh

# Install an explicit subset (core is always added); also UNSTOWS everything else
./apply.sh core yazi waybar

# Add untracked config to repo — pick the right feature package (or core)
mkdir -p features/<pkg>/.config/<app>
cp ~/.config/<app>/file features/<pkg>/.config/<app>/file
# edit features/<pkg>/.config/<app>/file in this repo
rm ~/.config/<app>/file          # remove real file so stow can create symlink
./apply.sh
git add . && git commit
```

Selection precedence: **CLI args > `features.local` (gitignored, per-host) > `features.conf` (committed default)**. `core` is always installed. Any package not selected is `stow -D`'d (clean deselection), so dropping a feature = remove its line and re-run `./apply.sh`.

## Structure

Each `features/<pkg>/` is a self-contained Stow package mirroring `$HOME`. `apply.sh` runs `stow --dir=features --target=$HOME <selected pkgs>`. Repo/docs/system files live ABOVE `features/` so stow never sees them.

```
features.conf                  # committed default feature list (one pkg per line)
features.local                 # GITIGNORED per-host override (optional)
features/
  .stow-local-ignore           # only ignores itself; nothing else is under the stow dir
  core/                        # ALWAYS installed: shared/base + machine-specific config
    .config/alacritty/alacritty.toml   # imports Omarchy base, overrides opacity
    .config/kitty/kitty.conf
    .config/gtk-3.0/settings.ini
    .config/omarchy/hooks/theme-set
    .config/hypr/
      bindings.conf       # keybindings, app launchers, language switch, mouse scroll/zoom binds
      hypridle.conf       # idle/lock timers
      input.conf          # shared input: kb layout, scroll, gestures; sources input-devices.conf
      input-devices.conf  # MACHINE: mouse device blocks (peripheral names, Windows pointer-accel custom curve)
      looknfeel.conf      # borders, gaps, cursor, blur, opacity, zoomFactor animation, walker/swayosd/mako blur layerrules
      monitors.conf       # MACHINE: display scaling (scale 1.3 on DP-2 2560x1440)
      envs.conf           # MACHINE: env vars (NVIDIA VA-API); sourced via apply.sh patch
      rules.conf          # window rules; sourced via apply.sh patch
      plugins.conf        # hyprexpo task view + keyboard submap
      float-daemon.py     # floating-window helper
      scripts/
        cursor-zoom.sh        # SUPER+scroll screen magnifier (steps cursor:zoom_factor)
        workspace-scroll.sh   # CTRL+SUPER+scroll workspace switch w/ per-bind debounce
        lang-switch.sh        # SUPER+SPACE: forces ALL keyboards to same xkb index (resync) + swayosd toast
        brightness-ddc.sh     # monitor brightness via ddcutil
        win-accel.py          # generator: Windows-10 SmoothMouseXCurve -> libinput custom accel points for input-devices.conf
    .local/bin/{clip,disk,yazi-tabs}
  swayosd-glass/               # frosted-glass OSD toast + cairo renderer fix
    .config/swayosd/style.css             # ONLY style.css symlinked (config.toml left as Omarchy's)
    .config/systemd/user/swayosd-server.service.d/override.conf  # GSK_RENDERER=cairo so OSD corners anti-alias
  walker-theme/                # custom launcher theme
    .config/walker/config.toml            # launcher: theme=omarchy-custom, providers, prefixes
    .config/walker/themes/omarchy-custom/
      style.css                # frosted-glass: @imports stock omarchy-default + translucent card, shadow, rounded pill
      layout.xml               # COPY of stock omarchy-default layout (not symlink): wider 760px + top-anchored
  yazi/                        # file manager (.config/yazi/*; plugins/ gitignored, restored by `ya pkg`)
  waybar/                      # status bar (config.jsonc, style.css, layout-toggle.sh, weather.sh)
  keybind-lookup/
    .config/hypr/scripts/keybind-lookup.py  # SUPER+K: hotkeys panel + live chord reverse-lookup (grab + uinput)
system/                        # NOT stowed — reference copies of files installed to /etc
  99-uinput-input-group.rules  # udev: /dev/uinput -> input group (lets keybind-lookup create a virtual keyboard)
  install-uinput.sh            # one-time installer: python-evdev + udev rule (for keybind-lookup SUPER+K)
.claude/                       # Claude Code local overrides (not stowed to HOME)
```

Both `core` and `keybind-lookup` ship `.config/hypr/scripts/` — stow merges them into one real dir (it only conflicts on two packages claiming the same FILE path).

## Feature packages

`apply.sh` stows `core` plus the selected feature packages; deselected ones are `stow -D`'d. Selection precedence: **CLI args > `features.local` > `features.conf`**; `core` is always added + de-duplicated.

| Package | What it is | Selectable |
|---------|-----------|------------|
| `core` | all shared/base + machine-specific config (hypr `.conf` files, scripts, alacritty, kitty, gtk, omarchy hook, `.local/bin/{clip,disk,yazi-tabs}`) | no — always on |
| `swayosd-glass` | frosted-glass OSD `style.css` + cairo-renderer drop-in | yes |
| `walker-theme` | custom Walker launcher theme + config | yes |
| `yazi` | yazi file manager config | yes |
| `waybar` | status bar config + scripts | yes |
| `keybind-lookup` | SUPER+K hotkeys panel script | yes |
| `wallpapers` | color-matched wallpaper curation: symlinks landscape pics into per-theme omarchy background dirs by palette affinity | yes |

Small script/plugin features (cursor-zoom, workspace-scroll, lang-switch, brightness-ddc, float-daemon, hyprexpo) live in `core`: their bind/plugin lines are in `core`'s `bindings.conf`/`plugins.conf`, so splitting them out would only create dangling references.

## Ownership boundary

Files in this repo — owned by dotfiles, Omarchy updates ignored. Paths below are relative to a package's root; **Pkg** names the feature package the file lives in:

| File | Pkg | Why owned |
|------|-----|-----------|
| `hypr/bindings.conf` | core | custom keybindings (hyprexpo, language switch, scroll/zoom binds) |
| `hypr/hypridle.conf` | core | custom idle/lock timers |
| `hypr/input.conf` | core | shared input (kb layout `us,ru`, scroll, gestures); sources `input-devices.conf` |
| `hypr/input-devices.conf` | core | **machine-specific**: mouse peripheral tuning (device names + `accel_profile = custom` Windows pointer-accel curve, generated by `scripts/win-accel.py`) |
| `hypr/looknfeel.conf` | core | appearance preferences; `layerrule = blur` on walker + swayosd + mako namespaces (pair with walker theme + swayosd OSD glass) |
| `hypr/monitors.conf` | core | **machine-specific**: display scaling (scale `1.3` on DP-2 2560x1440) |
| `hypr/envs.conf` | core | **machine-specific**: env vars (NVIDIA VA-API); apply.sh patches hyprland.conf to source it |
| `hypr/plugins.conf` | core | hyprexpo plugin (not in Omarchy) |
| `hypr/scripts/` | core | helper scripts for binds (cursor-zoom, workspace-scroll, lang-switch, brightness-ddc); `win-accel.py` = mouse-accel curve generator; not in Omarchy |
| `swayosd/style.css` | swayosd-glass | frosted-glass OSD toast (translucent bg + hairline + 12px radius, matches waybar pills); **only style.css symlinked**, `config.toml` left as Omarchy's. NO CSS hot-reload — reload after edit: `omarchy restart swayosd`. Corners anti-alias only with the cairo renderer drop-in below. |
| `.config/systemd/user/swayosd-server.service.d/override.conf` | swayosd-glass | drop-in forcing `GSK_RENDERER=cairo` — GTK4's GL renderer aliases the OSD pill's rounded corners (jagged "ladder" over high-contrast bg + fractional scale); cairo fixes it. Drop-in **dir must be a real dir** (systemd ignores symlinked `.d` dirs) — that's why `apply.sh` uses `stow --no-folding`. |
| `alacritty/alacritty.toml` | core | imports Omarchy base, adds opacity override |
| `walker/config.toml` | walker-theme | launcher config: points theme at custom `omarchy-custom` |
| `walker/themes/omarchy-custom/` | walker-theme | custom Walker theme: `style.css` @imports stock omarchy-default + frosted-glass overrides; `layout.xml` is a copy (won't track upstream layout changes) |
| `hypr/scripts/keybind-lookup.py` | keybind-lookup | SUPER+K hotkeys panel + live chord reverse-lookup |
| `match_wallpapers.py` (repo root) | wallpapers | curate tool: filters wallpapers by aspect ratio, scores each against every theme's `colors.toml` palette (CIEDE2000), symlinks matches into `features/wallpapers/.config/omarchy/backgrounds/<theme>/` (gitignored) and dir-symlinks each into `~/.config/omarchy/backgrounds/`. `--relink`/`--unlink` used by apply.sh; bare invocation = interactive curate. |
| `tools/gen_theme_data.py`, `tools/fixtures-labeler/` | wallpapers | static labeling form + its generated `themes.js` (palette/background hints) for building per-theme do/dont fixture sets |
| `tools/gen_gallery.py` | wallpapers | renders `docs/wallpapers-gallery.html` from the label files (matcher verdict vs human label) |
| `tests/fixtures/labels/<theme>.json` | wallpapers | human-labeled do/dont ground truth per theme; consumed by `tests/test_labeled_fixtures.py` |
| `system/` | (not stowed) | uinput udev rule + installer (for keybind-lookup); targets `/etc`, run `system/install-uinput.sh` once per host |

Files Omarchy owns — do NOT add to this repo:

| File | Notes |
|------|-------|
| `hypr/hyprland.conf` | Omarchy-managed; apply.sh patches it to source rules.conf, plugins.conf, envs.conf |
| `hypr/autostart.conf` | Omarchy-managed |
| `hypr/hyprlock.conf` | Omarchy-managed |
| `hypr/hyprsunset.conf` | Omarchy-managed |

## References

- [hyprexpo docs](https://hyprexpo.lol/docs/) — task view plugin (SUPER+TAB), config in `.config/hypr/plugins.conf`
- Walker theme `omarchy-custom` @imports stock `~/.local/share/omarchy/default/walker/themes/omarchy-default/style.css` (absolute path) so per-theme colors + theme switching keep working; only borders/glass are overridden. GTK4 has no CSS backdrop-blur — blur comes from the Hyprland `layerrule` in `looknfeel.conf`.
- **lang-switch** (`hypr/scripts/lang-switch.sh`, SUPER+SPACE): this box has multiple xkb devices (physical keyboards + an `fcitx5` virtual keyboard, which is the one Hyprland marks `main=true`). `hyprctl switchxkblayout all next` advances each device **independently**, so they drift out of phase and the old toast — read from the `main` device — stopped matching the keyboard you actually type on (looked workspace/window dependent because focus picks a different active device). Fix: track an index in a state file and `switchxkblayout all <id>` to force every device to the **same** index — always synced, displayed name deterministic, no read-back race. Keep the `layouts`/`names` arrays in sync with `kb_layout` in `input.conf`. swayosd toast = frosted glass via `swayosd/style.css` + `layerrule blur` on namespace `swayosd`.
- **mouse accel** (`hypr/input-devices.conf`, `scripts/win-accel.py`): `accel_profile = custom <step> <points…>` replicates the Windows "Enhance pointer precision" curve (Windows-10 `SmoothMouseXCurve`/`YCurve`). `win-accel.py` params: `device_dpi` (mouse DPI, sets the x-axis `step`), `screen_dpi`/`screen_scaling_factor` (=monitor scale 1.3), `sensitivity_factor` (Windows slider notch, 6 = 1.0×). Regenerate + repaste all three device blocks if DPI/slider/scale change. `accel_profile = flat` + `sensitivity = 0` would instead give Windows' "precision OFF" raw 1:1. Refs: wiki.archlinux.org/title/Mouse_acceleration, libinput pointer-acceleration custom profile.
- **swayosd cairo renderer** (`.config/systemd/user/swayosd-server.service.d/override.conf`): GTK4's default GL/NGL renderer aliases `border-radius` clips → the OSD pill shows stair-step "ladders" on the corner curve (stark over high-contrast bg + fractional scale 1.3). `GSK_RENDERER=cairo` anti-aliases them. systemd does NOT read a **symlinked** `*.service.d` dir, so `apply.sh` runs `stow --no-folding` (real dirs, file symlinks). Debug OSD headless: `swayosd-client --output-volume +1`, `grim`, crop the bottom-center pill, inspect.
- **keybind-lookup** (`hypr/scripts/keybind-lookup.py`, **SUPER+K**, overrides Omarchy's `omarchy-menu-keybindings`): the hotkeys panel — opens walker with the full list and type-to-search exactly like the stock panel — that *also* filters live to a binding's row when you physically press its chord. **Why it can't be done in walker alone:** walker holds keyboard focus, filters only by *typed text*, has no `--query` flag, and **can't be re-filtered once open**; Hyprland exposes no "what did I press" hook and fires SUPER chords as global binds (so a pressed chord executes, never observable). So the script `EVIOCGRAB`s every keyboard (devices with `KEY_ENTER`+`KEY_A`) — an evdev grab, which reliably blocks Hyprland from seeing the events on this box. **The catch with grabbing:** it also steals normal typing from walker, so the script creates a **uinput virtual keyboard** (`UInput.from_device` on `/dev/uinput`, writable via the `input`-group udev rule — see `system/install-uinput.sh`) and **re-injects every unmodified keystroke** (letters, SHIFT, arrows, Enter, Esc, Backspace) → walker search keeps working. Keys pressed **while SUPER/CTRL/ALT is held** (`CHORD_MODS`; SHIFT excluded = capital letters pass through) are *swallowed* (never injected, so Hyprland fires no bind, and the virtual device only ever sees unmodified keys) and the non-modifier key-down is mapped to a combo via `xkbcli compile-keymap` (`evdev code +8` = X11 keycode; same keysym source as the panel so `Return`→`RETURN`, `e`→`E` align), then the menu is re-spawned filtered to that combo's row (`Panel` class owns the proc; walker can't be filtered in place). **walker daemon quirk:** walker runs as a `--gapplication-service`, so a second `walker --dmenu` issued *while a menu is open* kills the first and exits immediately (the new list never shows). `Panel._spawn` therefore **closes the open menu (`walker --close` + terminate) and waits ~0.12s for the daemon to settle before opening the next** — sequential, never concurrent. Cost: a brief blink per chord (the daemon can't refilter in place). Loop ends when walker exits. Held state is seeded from `active_keys()` so the launching SUPER+K isn't mis-read. **Gotchas burned in:** `xkbcli` MUST get `stdin=DEVNULL` — it inherits the bind's non-tty stdin and exits 1 otherwise (this was the original "shortcuts still execute" bug: crash happened *before* the grab, so chords leaked through). A `time.sleep(0.12)` after creating the uinput device lets Hyprland attach it before the first re-injected key (else early keystrokes drop). Needs `python-evdev` + `input` group + `/dev/uinput` access (set up by `system/install-uinput.sh`); degrades to filter-only if uinput is unavailable. Debug: read `/tmp/keybind-lookup.log`. Keyboard chords only (no mouse binds); can't look up SUPER+K itself (it's the trigger). **Open speed:** the panel paints *before* any capture setup — `main` generates the list and shows walker first, then does the slow bits behind it (evdev device enumeration alone is ~200ms; `_spawn` skips the close+settle on first open). Don't move the grab/`find_keyboards`/uinput ahead of `show_full` or the menu goes back to ~½s to appear.
- **wallpapers** (`match_wallpapers.py`, package `wallpapers`): `omarchy theme bg next` lists `find -L ~/.config/omarchy/backgrounds/$THEME_NAME/`, so each theme's user-backgrounds dir is a symlink into the repo (gitignored), and inside it each wallpaper is a symlink to the source folder — `find -L` resolves both hops. Stow can't relay absolute symlinks (it aborts), so the matcher creates the `~/.config` dir-symlinks directly; the package tracks only `.gitkeep` (stow-ignored via `features/.stow-local-ignore`). Matching: Pillow median-cut dominant colors vs the theme palette (`background`/`accent`/`color1-6,9-14`, CIEDE2000 ≤ `--threshold`, default 18); aspect filter `--min-ratio` default 1.0 drops portrait/mobile. Re-run after adding wallpapers or themes: `./match_wallpapers.py`. Spec/plan: `docs/superpowers/`. Labeled-fixture eval: `tools/fixtures-labeler/` (static form) writes `tests/fixtures/labels/<theme>.json` (basenames + do/dont + reason + palette + params + source_dir); `tests/test_labeled_fixtures.py` grades `match_wallpapers.py` on the **original** images (referenced by `source_dir/basename`, missing → skip) and fails with an accuracy report on any disagreement; `python3 tools/gen_gallery.py` renders the gallery. Regenerate form data with `python3 tools/gen_theme_data.py`.

## Rules

- **Never edit `~/.config/` paths directly** — edit files in this repo only (under `features/<pkg>/`)
- **New files go under a feature package** — `features/<pkg>/.config/...`. Pick the matching feature, or `core` for shared/base config. Each file must live in exactly ONE package (stow conflicts on two packages owning the same target path).
- **Machine-specific config** (`core/.config/hypr/{monitors,envs,input-devices}.conf`) is isolated for portability — on a new host, edit only these. `monitors.conf`/`envs.conf` began as Omarchy templates and are now dotfiles-owned, so `omarchy refresh` would write through the symlink into the repo.
- Hyprland config is split: `hyprland.conf` sources each `.conf` in `~/.config/hypr/` — add new hypr `.conf` files under `features/core/.config/hypr/`
- `alacritty.toml` imports `~/.local/share/omarchy/config/alacritty/alacritty.toml` — Omarchy alacritty updates flow through automatically
- `apply.sh` stows from `features/` with `--no-folding`; dropping a feature requires re-running `apply.sh` (it `stow -D`'s the complement) — don't `rm` symlinks by hand
- Check `.gitignore` before adding new files
