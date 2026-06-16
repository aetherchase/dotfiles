#!/bin/bash
# One-time host setup for uinput access by the input group.
# Needed by the keybind-lookup panel (SUPER+K): it grabs the keyboards and
# re-injects keystrokes through a uinput virtual device.
# Idempotent: safe to re-run.
#
#   dependency : python-evdev (from extra)
#   udev rule  : /etc/udev/rules.d/99-uinput-input-group.rules
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULE_SRC="$DOTFILES_DIR/system/99-uinput-input-group.rules"
RULE_DST="/etc/udev/rules.d/99-uinput-input-group.rules"

echo "==> Installing python-evdev"
yay -S --needed --noconfirm python-evdev

echo "==> Installing udev rule -> $RULE_DST"
sudo install -m 644 "$RULE_SRC" "$RULE_DST"
sudo udevadm control --reload-rules
# Apply to the already-present node immediately (module is loaded at boot):
sudo chgrp input /dev/uinput
sudo chmod 660 /dev/uinput

echo "Done. uinput is now writable by the input group."
