#!/bin/bash
# place-code-windows.sh — pin VS Code (code-oss) startup windows to workspaces.
#
# WHY a script instead of `windowrule = workspace N silent, match:title …`:
# `workspace` is a *static* Hyprland rule — matched ONCE when the window is
# created. VS Code maps its window with a generic title and only *afterwards*
# rewrites it to "<file> - <folder>". So a title match never fires at creation
# and the window lands on whatever workspace had focus (the "random workspace"
# bug). Hyprland docs are explicit: static rules can't act on a post-creation
# title change. Class can't disambiguate either — every window below is class
# `code-oss`. So: wait for each folder title to settle, then move by address.
#
# movetoworkspacesilent never steals focus, so ws1 stays put while we fan out.
# Keep these substrings in sync with the `code-oss --new-window` lines launched
# from rules.conf.

# folder title substring -> target workspace
declare -A TARGETS=(
  ["webapp.users"]="2"
  ["localdeploy"]="3"
  ["dotfiles"]="special:scratchpad3"
)

deadline=$((SECONDS + 30))
while [ ${#TARGETS[@]} -gt 0 ] && [ "$SECONDS" -lt "$deadline" ]; do
  clients=$(hyprctl clients -j)
  for sub in "${!TARGETS[@]}"; do
    addr=$(printf '%s' "$clients" | jq -r --arg t "$sub" \
      '[.[] | select(.class == "code-oss" and (.title | contains($t)))][0].address // empty')
    if [ -n "$addr" ]; then
      hyprctl dispatch movetoworkspacesilent "${TARGETS[$sub]},address:$addr" >/dev/null
      unset "TARGETS[$sub]"
    fi
  done
  [ ${#TARGETS[@]} -gt 0 ] && sleep 0.2
done

# exit 0 only if every window was placed; 1 means some never showed (timeout)
[ ${#TARGETS[@]} -eq 0 ]
