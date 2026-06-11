#!/bin/bash
# One-time setup for the scroll-debounce service (worn-encoder phantom-tick filter).
# Idempotent: safe to re-run after editing the udev rule or service.
#
#   dependency  : python-evdev (from extra)
#   udev rule   : /etc/udev/rules.d/99-scroll-debounce-uinput.rules
#   user service: ~/.config/systemd/user/scroll-debounce.service (stowed)
#
# Run AFTER ./apply.sh has stowed the script + service into $HOME.
set -euo pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULE_SRC="$DOTFILES_DIR/system/99-scroll-debounce-uinput.rules"
RULE_DST="/etc/udev/rules.d/99-scroll-debounce-uinput.rules"

echo "==> Installing python-evdev"
yay -S --needed --noconfirm python-evdev

echo "==> Installing udev rule -> $RULE_DST"
sudo install -m 644 "$RULE_SRC" "$RULE_DST"
sudo udevadm control --reload-rules
# Apply to the already-present node immediately (module is loaded at boot):
sudo chgrp input /dev/uinput
sudo chmod 660 /dev/uinput

echo "==> Enabling user service"
systemctl --user daemon-reload
systemctl --user enable --now scroll-debounce.service

echo "==> Status"
systemctl --user --no-pager status scroll-debounce.service || true
cat <<'EOF'

Done. To tune the debounce window, edit:
  ~/.config/systemd/user/scroll-debounce.service   (SD_WINDOW_MS, SD_DEBUG=1)
then:
  systemctl --user daemon-reload && systemctl --user restart scroll-debounce
EOF
