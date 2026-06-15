#!/usr/bin/env bash
# Cycle keyboard layout across ALL keyboards in lockstep and toast the result.
#
# Why a state file + explicit index instead of `switchxkblayout all next`:
# this box has several xkb devices (physical keyboards + an fcitx5 virtual
# keyboard, which is the one Hyprland marks main=true). `... all next` advances
# each device independently, so the moment they fall out of phase they stay
# offset forever — and the toast, read from the "main" device, stops matching
# the keyboard you actually type on (the bug looked workspace/window dependent
# because focus picks a different active device). Forcing every device to the
# SAME index keeps them synced and makes the displayed name deterministic, so
# no read-back / race (`sleep`) is needed at all.
#
# Keep `layouts` in sync with kb_layout in input.conf.
set -euo pipefail

layouts=(us ru)
names=("English (US)" "Russian")
state="${XDG_RUNTIME_DIR:-/tmp}/hypr-kblayout-idx"

i=$(cat "$state" 2>/dev/null || echo 0)
i=$(( (i + 1) % ${#layouts[@]} ))
echo "$i" >"$state"

hyprctl switchxkblayout all "$i" >/dev/null
omarchy swayosd client --custom-message "${names[$i]}" --custom-icon input-keyboard-symbolic
