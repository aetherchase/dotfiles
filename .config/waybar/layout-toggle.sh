#!/bin/bash
# Usage: layout-toggle.sh          → output waybar JSON status
#        layout-toggle.sh --toggle → toggle all windows float/tile

FLOAT_STATE="/tmp/hypr_float_ws"
ws_id=$(hyprctl activeworkspace -j | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

if [ "$1" = "--toggle" ]; then
  python3 << EOF
import json, subprocess

FLOAT_STATE = "$FLOAT_STATE"
ws_id = $ws_id

def read_float_ws():
    try:
        with open(FLOAT_STATE) as f:
            return {int(x.strip()) for x in f if x.strip()}
    except Exception:
        return set()

def write_float_ws(s):
    with open(FLOAT_STATE, 'w') as f:
        for ws in sorted(s):
            f.write(f"{ws}\n")

clients = json.loads(subprocess.run(['hyprctl', 'clients', '-j'], capture_output=True, text=True).stdout)
ws_windows = [c for c in clients if c['workspace']['id'] == ws_id]
float_ws = read_float_ws()

if ws_id in float_ws:
    float_ws.discard(ws_id)
    for w in ws_windows:
        subprocess.run(['hyprctl', 'dispatch', 'settiled', f"address:{w['address']}"])
else:
    float_ws.add(ws_id)
    for w in ws_windows:
        subprocess.run(['hyprctl', 'dispatch', 'setfloating', f"address:{w['address']}"])

write_float_ws(float_ws)
EOF
  sleep 0.15 && pkill -RTMIN+11 waybar
else
  python3 << EOF
import json, subprocess

FLOAT_STATE = "$FLOAT_STATE"
ws_id = $ws_id

def read_float_ws():
    try:
        with open(FLOAT_STATE) as f:
            return {int(x.strip()) for x in f if x.strip()}
    except Exception:
        return set()

float_ws = read_float_ws()

if ws_id in float_ws:
    print(json.dumps({"text": "󱂬", "class": "float", "tooltip": "Floating — new windows auto-float\nSuper+Alt+T to tile all"}))
else:
    print(json.dumps({"text": "󰕴", "class": "tile", "tooltip": "Tiling\nSuper+Alt+T to float all"}))
EOF
fi
