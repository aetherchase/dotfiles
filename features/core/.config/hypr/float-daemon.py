#!/usr/bin/env python3
"""Float new windows on float-mode workspaces and keep waybar button in sync.

State file: /tmp/hypr_float_ws — workspace IDs, one per line.
Written by layout-toggle.sh. Read here to decide whether to float windows.

Signals waybar (RTMIN+11) on:
  - openwindow   (new window may change float state visually)
  - workspace    (active workspace changed — button must reflect new ws mode)
  - focusedmon   (monitor focus changed — same reason)
  - destroyworkspace (clean up stale float state)
"""
import json
import os
import socket
import subprocess
import time

FLOAT_STATE = "/tmp/hypr_float_ws"


def read_float_ws():
    try:
        with open(FLOAT_STATE) as f:
            return {int(x.strip()) for x in f if x.strip()}
    except Exception:
        return set()


def write_float_ws(s):
    try:
        with open(FLOAT_STATE, "w") as f:
            for ws in sorted(s):
                f.write(f"{ws}\n")
    except Exception:
        pass


def signal_waybar():
    subprocess.run(["pkill", "-RTMIN+11", "waybar"], capture_output=True)


def ws_id_from_name(ws_name):
    try:
        result = subprocess.run(
            ["hyprctl", "workspaces", "-j"],
            capture_output=True, text=True, timeout=2,
        )
        for ws in json.loads(result.stdout):
            if ws["name"] == ws_name:
                return ws["id"]
    except Exception:
        pass
    return None


instance = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
sock_path = f"{runtime_dir}/hypr/{instance}/.socket2.sock"

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(sock_path)

buf = b""
while True:
    chunk = sock.recv(4096)
    if not chunk:
        break
    buf += chunk
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        event = line.decode("utf-8", errors="replace").strip()

        if event.startswith("openwindow>>"):
            rest = event[len("openwindow>>"):]
            parts = rest.split(",", 3)
            if len(parts) >= 2:
                addr, ws_name = parts[0], parts[1]
                float_ws = read_float_ws()
                if float_ws:
                    ws_id = ws_id_from_name(ws_name)
                    if ws_id is not None and ws_id in float_ws:
                        time.sleep(0.05)
                        subprocess.run(
                            ["hyprctl", "dispatch", "setfloating", f"address:0x{addr}"],
                            capture_output=True, timeout=2,
                        )
            signal_waybar()

        elif event.startswith(("workspace>>", "workspacev2>>", "focusedmon>>")):
            signal_waybar()

        elif event.startswith("destroyworkspace>>"):
            ws_name = event.split(">>", 1)[1].strip()
            ws_id = ws_id_from_name(ws_name)
            if ws_id is not None:
                float_ws = read_float_ws()
                if ws_id in float_ws:
                    float_ws.discard(ws_id)
                    write_float_ws(float_ws)
            signal_waybar()
