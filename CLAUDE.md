# CLAUDE.md

Personal Arch Linux + Omarchy + Hyprland dotfiles managed with GNU Stow. Every file maps 1:1 to `$HOME` via symlinks.

## Commands

```bash
# Restow all symlinks
stow --target=$HOME --restow .

# Add untracked config to repo
cp ~/.config/<app>/file .config/<app>/file
# edit .config/<app>/file in this repo
./apply.sh
git add . && git commit
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

## References

- [hyprexpo docs](https://hyprexpo.lol/docs/) — task view plugin (SUPER+TAB), config in `.config/hypr/plugins.conf`

## Rules

- **Never edit `~/.config/` paths directly** — edit files in this repo only
- Hyprland config is split: `hyprland.conf` sources each `.conf` in `.config/hypr/` — edit the appropriate split file
- Check `.gitignore` before adding new files
