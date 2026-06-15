#!/bin/bash
# Per-bind scroll throttle for workspace switching.
#
# Global binds:scroll_event_delay is 0 so SUPER+scroll zoom gets every wheel
# tick (smooth, and no event leaks past the bind into the focused app). That
# removes the throttle that kept CTRL+SUPER workspace scroll from over-jumping
# on a fast spin. This script re-adds a debounce for workspace scroll only:
# ticks arriving within DELAY_MS of the last accepted one are dropped.
#
# Usage: workspace-scroll.sh e+1|e-1

DELAY_MS=150
STAMP="${XDG_RUNTIME_DIR:-/tmp}/hypr-wsscroll"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/hypr-wsscroll.lock"

# Serialize concurrent wheel events so the timestamp gate is race-free.
exec 9>"$LOCK"
flock 9

now=$(date +%s%3N)
last=$(cat "$STAMP" 2>/dev/null || echo 0)
[ $((now - last)) -lt "$DELAY_MS" ] && exit 0

echo "$now" >"$STAMP"
hyprctl dispatch workspace "$1"
