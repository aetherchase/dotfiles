#!/bin/bash
# DDC/CI brightness for external monitor (no /sys/class/backlight device).
# omarchy-brightness-display uses brightnessctl, a no-op on external displays,
# so brightness keys are rebound to this in bindings.conf. VCP 0x10 = brightness.
#
# DDC/CI is a slow protocol (~0.3s/write, monitor-firmware bound) — can't be
# beaten. So we decouple feel from physics:
#   * foreground updates a cached target + shows the OSD instantly
#   * a single background writer chases the latest cached target via ddcutil
#   * a flock makes key-repeat collapse to the final value instead of queueing
#     N backed-up 0.3s writes.

CACHE="${XDG_RUNTIME_DIR:-/tmp}/ddc-brightness"   # "BUS VALUE"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/ddc-brightness.lock"
DDC=(ddcutil --noverify --sleep-multiplier .1)

detect_bus() {
  ddcutil detect --terse 2>/dev/null | grep -oP 'I2C bus:\s*/dev/i2c-\K[0-9]+' | head -1
}

# Load cached "BUS VAL"; bootstrap on miss (runtime dir clears on logout, so a
# stale bus from a previous boot never persists).
BUS="" VAL=""
[ -f "$CACHE" ] && read -r BUS VAL < "$CACHE"
if [ -z "$BUS" ]; then
  BUS=$(detect_bus)
  VAL=$("${DDC[@]}" --bus "$BUS" getvcp 10 2>/dev/null | grep -oP 'current value =\s*\K[0-9]+')
fi
[ -z "$VAL" ] && VAL=50

case "$1" in
  up)   VAL=$((VAL + 5)); ((VAL > 100)) && VAL=100 ;;
  down) VAL=$((VAL - 5)); ((VAL < 0))   && VAL=0   ;;
  max)  VAL=100 ;;
  min)  VAL=1   ;;
  *)    exit 1  ;;
esac

# Instant: publish target + show OSD before touching the slow bus.
echo "$BUS $VAL" > "$CACHE"
omarchy-swayosd-brightness "$VAL"

# Async writer, single-flight. If a writer already holds the lock it will see
# our just-written target on its next loop, so we just exit.
(
  exec 9>"$LOCK"
  flock -n 9 || exit 0
  while :; do
    read -r b t < "$CACHE"
    if ! "${DDC[@]}" --bus "$b" setvcp 10 "$t" 2>/dev/null; then
      b=$(detect_bus)
      "${DDC[@]}" --bus "$b" setvcp 10 "$t" 2>/dev/null
      echo "$b $t" > "$CACHE"
    fi
    read -r _ t2 < "$CACHE"
    [ "$t2" = "$t" ] && break   # target stable — done
  done
) & disown
