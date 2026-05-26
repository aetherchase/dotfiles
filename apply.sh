#!/bin/bash
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Symlinking dotfiles from: $DOTFILES_DIR"

stow --dir="$DOTFILES_DIR" --target="$HOME" --restow .

echo "Done."
