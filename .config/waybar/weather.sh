#!/bin/bash
# Robust weather for waybar.
#
# Omarchy's stock omarchy-weather-icon pulls wttr.in's heavy ?format=j1 JSON
# (to derive a nerd-font glyph from the weatherCode). wttr.in frequently starves
# that endpoint — the connection opens but the body never finishes — so the
# module returns {"class":"unavailable"} and the pill renders empty.
#
# wttr.in's lightweight one-line formats answer fast (~100ms), so this uses
# those, caches the last good result, and falls back to cache when wttr.in is
# slow — the pill stays populated instead of blanking out.
#
# Output: waybar custom-module JSON. text = condition glyph + temperature.
# `--notify` mode: pop the descriptive tooltip line as a notification (waybar
# on-click). Single source for the wttr formats — no duplication in config.jsonc.

cache="${XDG_CACHE_HOME:-$HOME/.cache}/waybar-weather.json"
loc=""   # empty = wttr.in IP geolocation; pin a city here (e.g. "Penza") to override

# %c = condition glyph (emoji), %t = temperature (e.g. "+12°C")
icon_fmt='%c%t'
# Descriptive one-liner for the tooltip: "Location: Condition +12°C (feels +10°C)"
tip_fmt='%l:+%C+%t+(feels+%f)'

# tr strips newlines AND tabs so a stray control char can't break the JSON below.
fetch() { curl -fsS --max-time 6 "https://wttr.in/${loc}?format=$1" 2>/dev/null | tr -d '\n\t'; }

if [[ $1 == --notify ]]; then
  tip=$(fetch "$tip_fmt")
  notify-send -u low "${tip:-Weather unavailable}"
  exit 0
fi

raw=$(fetch "$icon_fmt")
tip=$(fetch "$tip_fmt")

if [[ -n $raw ]]; then
  # "☀️ +12°C" -> "☀️ 12°": drop the leading +, drop the C, squeeze spaces
  text=$(printf '%s' "$raw" | sed -E 's/\+([0-9])/\1/g; s/°C/°/g; s/  +/ /g; s/^ //; s/ $//')
  text=$(printf '%s' "$text" | sed 's/["\\]/\\&/g')
  tip=$(printf '%s' "${tip:-$text}" | sed 's/["\\]/\\&/g')
  printf '{"text":"%s","tooltip":"%s"}\n' "$text" "$tip" | tee "$cache"
elif [[ -f $cache ]]; then
  cat "$cache"
else
  printf '{"text":"","class":"unavailable"}\n'
fi
