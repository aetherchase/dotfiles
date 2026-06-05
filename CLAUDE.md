# CLAUDE.md

Personal Arch Linux + Omarchy + Hyprland dotfiles managed with GNU Stow. Every file maps 1:1 to `$HOME` via symlinks.

## Commands

```bash
# Restow all symlinks
./apply.sh

# Add untracked config to repo
cp ~/.config/<app>/file .config/<app>/file
# edit .config/<app>/file in this repo
rm ~/.config/<app>/file          # remove real file so stow can create symlink
./apply.sh
git add . && git commit
```

## Structure

```
.config/
  alacritty/alacritty.toml   # imports Omarchy base, overrides opacity
  hypr/
    bindings.conf       # keybindings, app launchers, language switch, mouse scroll/zoom binds
    hypridle.conf       # idle/lock timers
    input.conf          # shared input: kb layout, scroll, gestures; sources input-devices.conf
    input-devices.conf  # MACHINE: mouse device blocks (peripheral names, flat accel, sensitivity)
    looknfeel.conf      # borders, gaps, cursor, blur, opacity, zoomFactor animation, walker blur layerrule
    monitors.conf       # MACHINE: display scaling (scale 1.3 on DP-2 2560x1440)
    envs.conf           # MACHINE: env vars (NVIDIA VA-API); sourced via apply.sh patch
    rules.conf          # window rules; sourced via apply.sh patch
    plugins.conf        # hyprexpo task view + keyboard submap
    scripts/
      cursor-zoom.sh        # SUPER+scroll screen magnifier (steps cursor:zoom_factor)
      workspace-scroll.sh   # CTRL+SUPER+scroll workspace switch w/ per-bind debounce
  walker/
    config.toml                 # launcher: theme=omarchy-custom, providers, prefixes
    themes/omarchy-custom/
      style.css                 # frosted-glass: @imports stock omarchy-default + translucent card, shadow, rounded search/selection pill
      layout.xml                # COPY of stock omarchy-default layout (not symlink): wider 760px + top-anchored (valign=start)
.claude/
  settings.local.json   # Claude Code local overrides (not stowed to HOME)
```

## Ownership boundary

Files in this repo — owned by dotfiles, Omarchy updates ignored:

| File | Why owned |
|------|-----------|
| `hypr/bindings.conf` | custom keybindings (hyprexpo, language switch, scroll/zoom binds) |
| `hypr/hypridle.conf` | custom idle/lock timers |
| `hypr/input.conf` | shared input (kb layout `us,ru`, scroll, gestures); sources `input-devices.conf` |
| `hypr/input-devices.conf` | **machine-specific**: mouse peripheral tuning (device names, flat accel, sensitivity `-0.3`) |
| `hypr/looknfeel.conf` | appearance preferences; `layerrule = blur` on walker namespace (pairs with walker theme) |
| `hypr/monitors.conf` | **machine-specific**: display scaling (scale `1.3` on DP-2 2560x1440) |
| `hypr/envs.conf` | **machine-specific**: env vars (NVIDIA VA-API); apply.sh patches hyprland.conf to source it |
| `hypr/plugins.conf` | hyprexpo plugin (not in Omarchy) |
| `hypr/scripts/` | helper scripts for binds (cursor-zoom, workspace-scroll); not in Omarchy |
| `alacritty/alacritty.toml` | imports Omarchy base, adds opacity override |
| `walker/config.toml` | launcher config: points theme at custom `omarchy-custom` |
| `walker/themes/omarchy-custom/` | custom Walker theme: `style.css` @imports stock omarchy-default + frosted-glass overrides; `layout.xml` is a copy (won't track upstream layout changes) |

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

## Rules

- **Never edit `~/.config/` paths directly** — edit files in this repo only
- **Machine-specific config** (`monitors.conf`, `envs.conf`, `input-devices.conf`) is isolated for portability — on a new host, edit only these. `monitors.conf`/`envs.conf` began as Omarchy templates and are now dotfiles-owned, so `omarchy refresh` would write through the symlink into the repo.
- Hyprland config is split: `hyprland.conf` sources each `.conf` in `.config/hypr/` — add new files for new features
- `alacritty.toml` imports `~/.local/share/omarchy/config/alacritty/alacritty.toml` — Omarchy alacritty updates flow through automatically
- Check `.gitignore` before adding new files
