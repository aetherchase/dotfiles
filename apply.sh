#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Symlinking dotfiles from: $DOTFILES_DIR"

stow --dir="$DOTFILES_DIR" --target="$HOME" --restow .

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

echo "Done."
