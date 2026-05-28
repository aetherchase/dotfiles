#!/bin/bash
set -euo pipefail

# Remove HEY webapp (Omarchy webapp, not a package)
HEY_FILES=(
    "$HOME/.local/share/applications/HEY.desktop"
    "$HOME/.local/share/applications/icons/HEY.png"
    "$HOME/.local/share/icons/hicolor/48x48/apps/HEY.png"
)

for f in "${HEY_FILES[@]}"; do
    if [[ -e "$f" ]]; then
        rm -f "$f"
        echo "Removed $f"
    fi
done
