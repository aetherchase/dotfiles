#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FEATURES_DIR="$DOTFILES_DIR/features"

# --- Resolve which feature packages to install ---------------------------------
# Order of precedence: CLI args  >  features.local  >  features.conf.
# `core` is always installed (prepended + de-duplicated below).
if [ "$#" -gt 0 ]; then
    REQUESTED=("$@")
elif [ -f "$DOTFILES_DIR/features.local" ]; then
    mapfile -t REQUESTED < <(grep -vE '^\s*(#|$)' "$DOTFILES_DIR/features.local")
else
    mapfile -t REQUESTED < <(grep -vE '^\s*(#|$)' "$DOTFILES_DIR/features.conf")
fi

declare -A seen; SELECTED=()
for f in core "${REQUESTED[@]}"; do
    [ -n "${seen[$f]:-}" ] && continue
    if [ ! -d "$FEATURES_DIR/$f" ]; then
        echo "WARN: no feature package '$f' under features/, skipping" >&2
        continue
    fi
    seen[$f]=1; SELECTED+=("$f")
done

echo "Symlinking features from: $FEATURES_DIR"
echo "Selected: ${SELECTED[*]}"

# Ask for sudo once upfront, then refresh the timestamp in the background
# so later yay/hyprpm calls reuse it instead of prompting again.
sudo -v
( while true; do sudo -n true; sleep 60; kill -0 "$$" 2>/dev/null || exit; done ) 2>/dev/null &
SUDO_KEEPALIVE_PID=$!
trap 'kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true' EXIT

# --- Clean deselection: unstow any package NOT in the selected set -------------
# Removes dangling symlinks left by a feature that was previously installed but
# is no longer selected. `stow -D` on a not-stowed package is a harmless no-op.
for d in "$FEATURES_DIR"/*/; do
    pkg="$(basename "$d")"
    [ -n "${seen[$pkg]:-}" ] && continue
    echo "Unstowing deselected feature: $pkg"
    stow -D --no-folding --dir="$FEATURES_DIR" --target="$HOME" "$pkg" 2>/dev/null || true
done

# --- Install the selected packages ---------------------------------------------
# --no-folding: create real directories and symlink individual files, instead of
# symlinking whole directories. Required so systemd drop-in dirs
# (e.g. ~/.config/systemd/user/*.service.d) are REAL dirs — systemd does not
# traverse a symlinked .d directory, so a folded symlink silently drops the override.
# Packages that share a parent dir (e.g. core + keybind-lookup both ship
# .config/hypr/scripts/) merge into one real dir; stow only conflicts on two
# packages claiming the same FILE path. Single invocation = atomic conflict check.
stow --no-folding --dir="$FEATURES_DIR" --target="$HOME" --restow "${SELECTED[@]}"

# Ensure hyprland.conf sources rules.conf and plugins.conf
HYPR_CONF="$HOME/.config/hypr/hyprland.conf"
RULES_SOURCE="source = ~/.config/hypr/rules.conf"

if ! grep -qF "$RULES_SOURCE" "$HYPR_CONF" 2>/dev/null; then
    echo "" >> "$HYPR_CONF"
    echo "# Window rules (managed by dotfiles/apply.sh)" >> "$HYPR_CONF"
    echo "$RULES_SOURCE" >> "$HYPR_CONF"
    echo "Patched $HYPR_CONF to source rules.conf"
fi

# Ensure hyprland.conf sources plugins.conf (file is not in dotfiles, so we patch it)
PLUGINS_SOURCE="source = ~/.config/hypr/plugins.conf"

if ! grep -qF "$PLUGINS_SOURCE" "$HYPR_CONF" 2>/dev/null; then
    echo "" >> "$HYPR_CONF"
    echo "# Plugins (managed by dotfiles/apply.sh)" >> "$HYPR_CONF"
    echo "$PLUGINS_SOURCE" >> "$HYPR_CONF"
    echo "Patched $HYPR_CONF to source plugins.conf"
fi

# Ensure hyprland.conf sources envs.conf (machine env, e.g. NVIDIA — Omarchy template omits this source line)
ENVS_SOURCE="source = ~/.config/hypr/envs.conf"

if ! grep -qF "$ENVS_SOURCE" "$HYPR_CONF" 2>/dev/null; then
    echo "" >> "$HYPR_CONF"
    echo "# Machine env (managed by dotfiles/apply.sh)" >> "$HYPR_CONF"
    echo "$ENVS_SOURCE" >> "$HYPR_CONF"
    echo "Patched $HYPR_CONF to source envs.conf"
fi

# Install hyprpm build dependencies
yay -S --needed --noconfirm cmake gcc git cpio pkgconf

# Install and enable hyprexpo plugin
hyprpm update
hyprpm add https://github.com/sandwichfarm/hyprexpo
hyprpm enable hyprexpo
hyprpm reload

# Reload Hyprland config if running
if hyprctl version &>/dev/null; then
    hyprctl reload
    echo "Hyprland config reloaded."
fi

echo "Done. Installed: ${SELECTED[*]}"
