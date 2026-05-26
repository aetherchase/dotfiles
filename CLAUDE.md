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
    bindings.conf    # keybindings, app launchers, language switch
    hypridle.conf    # idle/lock timers
    input.conf       # keyboard layouts, mouse (machine-specific)
    looknfeel.conf   # borders, gaps, cursor, blur, opacity
    monitors.conf    # display scaling (machine-specific)
    plugins.conf     # hyprexpo task view + keyboard submap
.claude/
  settings.local.json   # Claude Code local overrides (not stowed to HOME)
```

## Ownership boundary

Files in this repo — owned by dotfiles, Omarchy updates ignored:

| File | Why owned |
|------|-----------|
| `hypr/bindings.conf` | custom keybindings (hyprexpo, language switch) |
| `hypr/hypridle.conf` | custom idle/lock timers |
| `hypr/input.conf` | machine-specific layouts and mouse profiles |
| `hypr/looknfeel.conf` | appearance preferences |
| `hypr/monitors.conf` | machine-specific scaling (1.4 → 1.33 on DP-2 2560x1440) |
| `hypr/plugins.conf` | hyprexpo plugin (not in Omarchy) |
| `alacritty/alacritty.toml` | imports Omarchy base, adds opacity override |

Files Omarchy owns — do NOT add to this repo:

| File | Notes |
|------|-------|
| `hypr/hyprland.conf` | Omarchy-managed; apply.sh patches it to source plugins.conf |
| `hypr/autostart.conf` | Omarchy-managed |
| `hypr/hyprlock.conf` | Omarchy-managed |
| `hypr/hyprsunset.conf` | Omarchy-managed |

## References

- [hyprexpo docs](https://hyprexpo.lol/docs/) — task view plugin (SUPER+TAB), config in `.config/hypr/plugins.conf`

## Rules

- **Never edit `~/.config/` paths directly** — edit files in this repo only
- Hyprland config is split: `hyprland.conf` sources each `.conf` in `.config/hypr/` — add new files for new features
- `alacritty.toml` imports `~/.local/share/omarchy/config/alacritty/alacritty.toml` — Omarchy alacritty updates flow through automatically
- Check `.gitignore` before adding new files
