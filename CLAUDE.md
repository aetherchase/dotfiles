# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

Personal Arch Linux + Omarchy + Hyprland dotfiles managed with GNU Stow. Every file under `dotfiles/` maps 1:1 to `$HOME` via symlinks.

## Commands

```bash
# Apply (restow all symlinks)
./apply.sh                        # or: stow --target=$HOME --restow .

# Add a new app config
mkdir -p ~/.config/<app>
mv ~/.config/<app>/config .config/<app>/
./apply.sh
git add . && git commit -m "add <app> config"
```

## Structure

```
.config/
  alacritty/   # terminal — opacity, font
  hypr/
    bindings.conf   # keybindings, app launchers, language switch
    input.conf      # keyboard layouts, mouse sensitivity
    looknfeel.conf  # borders, gaps, cursor, blur, opacity
    monitors.conf   # display scaling / arrangement
.claude/
  settings.local.json   # Claude Code local overrides (not stowed to HOME)
```

## Hyprland config split

Hyprland config is split into sourced files — `hyprland.conf` (provided by Omarchy) sources each `.conf` in `.config/hypr/`. Edits go in the appropriate split file, not a monolithic conf.

## Stow behavior

`stow --restow` re-creates all symlinks, safe to re-run. Conflicts (real files at target path) must be removed manually before stowing. Gitignore excludes common generated/cache paths — check `.gitignore` before adding new files.

## Editing rules

**NEVER edit system config files directly** (e.g. `~/.config/hypr/hypridle.conf`).

If a config file is not yet in this repo:
1. Copy it here first: `cp ~/.config/<app>/file .config/<app>/file`
2. Remove the original: `rm ~/.config/<app>/file`
3. Restow: `stow --target=$HOME --restow .`
4. Then edit the file inside this repo

All edits must happen on files tracked in `dotfiles/`, never on `~/.config/` paths directly.
