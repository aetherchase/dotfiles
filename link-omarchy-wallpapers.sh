#!/bin/bash
# Create (or, with --unlink, remove) per-theme wallpaper symlinks so that
# `omarchy theme bg next` cycles ONE shared collection under EVERY theme.
#
# omarchy lists a theme's extra backgrounds from ~/.config/omarchy/backgrounds/<theme>/
# (it runs `find -L .../backgrounds/$THEME_NAME`), so we point each theme's dir
# straight at $WALLPAPER_SRC. The links live in ~/.config, NOT the repo: they
# reference a personal, per-host collection and must never be committed. Stow
# cannot relay them either (it aborts on absolute symlinks), so the `wallpapers`
# feature package tracks only a .gitkeep and apply.sh calls this script to
# (un)install the links — before stow when selected, on unstow when dropped.
#
# Source (first match wins): $WALLPAPER_SRC env, else a non-flag $1, else ~/Wallpapers.
set -euo pipefail

BG_DIR="$HOME/.config/omarchy/backgrounds"

UNLINK=0
case "${1:-}" in
    --unlink|-u) UNLINK=1 ;;
    "")          ;;
    *)           WALLPAPER_SRC="$1" ;;
esac
WALLPAPER_SRC="${WALLPAPER_SRC:-$HOME/Wallpapers}"

# Theme slugs = stock omarchy themes + any user themes. The slug is the dir name,
# which is also what omarchy writes to current/theme.name (the $THEME_NAME it
# uses to build the per-theme backgrounds path).
mapfile -t THEMES < <(
    { ls "$HOME/.local/share/omarchy/themes/" 2>/dev/null
      ls "$HOME/.config/omarchy/themes/"      2>/dev/null; } | sort -u
)

if [ "$UNLINK" -eq 1 ]; then
    n=0
    for theme in "${THEMES[@]}"; do
        [ -n "$theme" ] || continue
        link="$BG_DIR/$theme"
        # Only our own symlinks (a per-theme backgrounds dir is a symlink only
        # because we made it one); leave real dirs / non-links untouched.
        [ -L "$link" ] && { rm -f "$link"; n=$((n + 1)); }
    done
    echo "Removed $n wallpaper symlink(s) from $BG_DIR"
    exit 0
fi

if [ ! -d "$WALLPAPER_SRC" ]; then
    echo "WARN: wallpaper source '$WALLPAPER_SRC' not found — skipping wallpaper symlinks" >&2
    exit 0
fi

mkdir -p "$BG_DIR"
for theme in "${THEMES[@]}"; do
    [ -n "$theme" ] || continue
    ln -nsfT "$WALLPAPER_SRC" "$BG_DIR/$theme"
done
echo "Linked ${#THEMES[@]} theme(s) -> $WALLPAPER_SRC under $BG_DIR"
