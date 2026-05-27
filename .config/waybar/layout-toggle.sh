#!/bin/bash
# Usage: layout-toggle.sh          → output waybar JSON status
#        layout-toggle.sh --toggle → toggle all windows float/tile

ws_id=$(hyprctl activeworkspace -j | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

if [ "$1" = "--toggle" ]; then
  python3 << EOF
import json, subprocess

clients = json.loads(subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True, text=True).stdout)
ws_windows = [c for c in clients if c['workspace']['id'] == $ws_id]

if not ws_windows:
    exit()

floating_count = sum(1 for c in ws_windows if c.get('floating', False))

if floating_count == len(ws_windows):
    for w in ws_windows:
        subprocess.run(['hyprctl', 'dispatch', 'settiled', f"address:{w['address']}"])
else:
    for w in ws_windows:
        subprocess.run(['hyprctl', 'dispatch', 'setfloating', f"address:{w['address']}"])
EOF
else
  python3 << EOF
import json, subprocess

clients = json.loads(subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True, text=True).stdout)
ws_windows = [c for c in clients if c['workspace']['id'] == $ws_id]

total = len(ws_windows)
floating = sum(1 for c in ws_windows if c.get('floating', False))

if total == 0 or floating < total:
    print(json.dumps({"text": "󰕴", "class": "tile", "tooltip": "Tiling\nSuper+Alt+T to float all"}))
else:
    print(json.dumps({"text": "󱂬", "class": "float", "tooltip": "Floating\nSuper+Alt+T to tile all"}))
EOF
fi
