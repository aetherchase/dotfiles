#!/bin/bash
# Screen magnifier for Hyprland — adjusts cursor:zoom_factor (float, 1.0 = no
# zoom; zooms around the cursor like a magnifying glass). No dispatcher exists
# to step the value, so we read the current factor and write a clamped new one.
# Bound to SUPER+scroll in bindings.conf.
#
# Usage: cursor-zoom.sh in|out|reset

STEP=0.4
MIN=1.0
MAX=5.0

cur=$(hyprctl getoption cursor:zoom_factor -j | grep -oP '"float":\s*\K[0-9.]+')
[ -z "$cur" ] && cur=1.0

case "$1" in
  in)    new=$(awk -v c="$cur" -v s="$STEP" -v m="$MAX" 'BEGIN{n=c+s; if(n>m)n=m; printf "%.2f", n}') ;;
  out)   new=$(awk -v c="$cur" -v s="$STEP" -v m="$MIN" 'BEGIN{n=c-s; if(n<m)n=m; printf "%.2f", n}') ;;
  reset) new=1.0 ;;
  *)     echo "usage: $0 in|out|reset" >&2; exit 1 ;;
esac

hyprctl keyword cursor:zoom_factor "$new"
