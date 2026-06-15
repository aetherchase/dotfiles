#!/usr/bin/env python3
"""Omarchy hotkeys panel (SUPER+K) that also filters live when you press a chord.

Behaves like the stock panel: opens walker with the full keybindings list and
you type to search. On top of that, if you physically press a binding chord
(SUPER + something), the panel re-opens filtered to that binding's row — so you
can ask "what does this chord do?" by just pressing it.

Why this is non-trivial: walker holds keyboard focus while open and can't be
re-filtered in place, and Hyprland fires SUPER chords as global binds (so a
pressed chord would execute, not be observable). The only way to intercept a
chord is to EVIOCGRAB the keyboard at the evdev layer (same mechanism as
scroll-debounce's mouse grab). But grabbing also steals normal typing from
walker — so we re-inject unmodified keystrokes through a uinput virtual
keyboard (typing/search keep working), while swallowing SUPER/CTRL/ALT chords
and turning them into a filter. The virtual device only ever sees unmodified
keys, so Hyprland never fires a bind from it.

Bound in bindings.conf (overrides Omarchy's SUPER+K); see CLAUDE.md.
"""

import json
import re
import select
import subprocess
import sys
import time

import evdev
from evdev import ecodes as e, UInput

LOG = "/tmp/keybind-lookup.log"


def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


# evdev modifier code -> (mask bit, panel name). Mask bits mirror Hyprland's
# modmask integers / the sed map in omarchy-menu-keybindings.
MODS = {
    e.KEY_LEFTMETA: (64, "SUPER"), e.KEY_RIGHTMETA: (64, "SUPER"),
    e.KEY_LEFTSHIFT: (1, "SHIFT"), e.KEY_RIGHTSHIFT: (1, "SHIFT"),
    e.KEY_LEFTCTRL: (4, "CTRL"), e.KEY_RIGHTCTRL: (4, "CTRL"),
    e.KEY_LEFTALT: (8, "ALT"), e.KEY_RIGHTALT: (8, "ALT"),
}
# Panel column order: SUPER, SHIFT, CTRL, ALT.
MOD_ORDER = [(64, "SUPER"), (1, "SHIFT"), (4, "CTRL"), (8, "ALT")]
# Modifiers that mark a keypress as a "lookup chord" (swallowed, not typed).
# SHIFT is excluded: SHIFT alone is just a capital letter, so it passes through
# to walker's search like normal typing.
CHORD_MODS = {e.KEY_LEFTMETA, e.KEY_RIGHTMETA, e.KEY_LEFTCTRL,
              e.KEY_RIGHTCTRL, e.KEY_LEFTALT, e.KEY_RIGHTALT}


def notify(msg):
    subprocess.run(["notify-send", "-t", "1500", "Keybindings", msg],
                   stderr=subprocess.DEVNULL)


def build_keysym_map():
    """X11 keycode -> keysym name from the active compiled keymap (same source
    as the panel, so Return->RETURN, e->E align)."""
    out = subprocess.run(["xkbcli", "compile-keymap"], stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, check=True).stdout
    code_by_name, sym_by_name = {}, {}
    section = ""
    for line in out.splitlines():
        if "xkb_keycodes" in line:
            section = "codes"
        elif "xkb_symbols" in line:
            section = "syms"
        if section == "codes":
            m = re.search(r"<([A-Za-z0-9_]+)>\s*=\s*(\d+)\s*;", line)
            if m:
                code_by_name[m.group(1)] = int(m.group(2))
        elif section == "syms":
            m = re.search(r"key\s*<([A-Za-z0-9_]+)>\s*\{\s*\[\s*([^,\] ]+)", line)
            if m:
                sym_by_name[m.group(1)] = m.group(2)
    code2sym = {}
    for name, code in code_by_name.items():
        sym = sym_by_name.get(name)
        if sym and sym != "NoSymbol":
            code2sym[code] = sym
    return code2sym


def panel_combo(mask, code, code2sym):
    sym = code2sym.get(code + 8)  # evdev code + 8 = X11 keycode
    if not sym:
        return None
    key = sym.upper()
    mod_str = " ".join(name for bit, name in MOD_ORDER if mask & bit)
    combo = f"{mod_str} + {key}"
    combo = re.sub(r"^[ \t]*\+?[ \t]*", "", combo)
    return re.sub(r"[ \t]+", " ", combo).strip()


def find_keyboards():
    kbds = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        keys = dev.capabilities().get(e.EV_KEY, [])
        if e.KEY_ENTER in keys and e.KEY_A in keys:
            kbds.append(dev)
    return kbds


def menu_height():
    try:
        mons = json.loads(subprocess.run(
            ["hyprctl", "monitors", "-j"], stdin=subprocess.DEVNULL,
            capture_output=True, text=True).stdout)
        h = next(m["height"] for m in mons if m.get("focused"))
        return str(int(h * 40 / 100))
    except Exception:
        return "600"


class Panel:
    """Owns the walker process; can be re-spawned with a filtered list."""

    def __init__(self, all_lines, height):
        self.all_lines = all_lines
        self.height = height
        self.proc = None

    def _close_current(self):
        # walker runs as a --gapplication-service daemon: a second `walker
        # --dmenu` issued while a menu is open kills the first and exits
        # immediately (the list never replaces). So we must fully close the
        # open menu and let the daemon settle before opening the next one.
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        subprocess.run(["walker", "--close"], stdin=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    def _spawn(self, lines, prompt):
        self._close_current()
        time.sleep(0.12)  # let the daemon tear down the old menu first
        self.proc = subprocess.Popen(
            ["walker", "--dmenu", "-p", prompt,
             "--width", "800", "--height", self.height],
            stdin=subprocess.PIPE, text=True)
        try:
            self.proc.stdin.write("\n".join(lines))
            self.proc.stdin.close()
        except BrokenPipeError:
            pass
        log(f"spawned walker '{prompt}' ({len(lines)} rows) poll={self.proc.poll()}")

    def show_full(self):
        self._spawn(self.all_lines, "Keybindings")

    def show_filtered(self, combo):
        matches = [ln for ln in self.all_lines
                   if ln.split(" → ")[0].strip() == combo]
        if not matches:
            matches = [f"{combo:<35} → (no binding)"]
        log(f"filter {combo} -> {len(matches)} row(s)")
        self._spawn(matches, combo)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def run(kbds, code2sym, all_lines, height):
    fdmap = {d.fd: d for d in kbds}
    for d in kbds:
        d.grab()
    log(f"grabbed {len(kbds)}: {[d.name for d in kbds]}")

    # Virtual keyboard for re-injecting normal typing back to walker. It only
    # ever receives unmodified keys, so Hyprland never fires a bind from it.
    ui = None
    try:
        ui = UInput.from_device(kbds[0], name="keybind-lookup-passthrough")
        time.sleep(0.12)  # let Hyprland attach the new device before we type
        log("uinput ready")
    except Exception as ex:
        log(f"uinput unavailable: {ex} (typing passthrough disabled)")

    # Seed held state from the kernel: the launching SUPER+K may still be down.
    held = set()
    for d in kbds:
        held.update(d.active_keys())
    log(f"initial held={held}")

    panel = Panel(all_lines, height)
    panel.show_full()

    try:
        while True:
            if not panel.alive():
                log("walker closed")
                return
            r, _, _ = select.select(fdmap, [], [], 0.1)
            for fd in r:
                try:
                    events = list(fdmap[fd].read())
                except OSError:
                    continue
                for ev in events:
                    if ev.type != e.EV_KEY:
                        continue
                    code, val = ev.code, ev.value
                    if val == 1:
                        held.add(code)
                    elif val == 0:
                        held.discard(code)

                    chord_active = bool(held & CHORD_MODS) or code in CHORD_MODS
                    if chord_active:
                        # Swallow everything while a chord modifier is held; a
                        # fresh non-modifier key-down is the binding to look up.
                        if val == 1 and code not in MODS:
                            mask = sum(MODS[m][0] for m in held if m in MODS)
                            combo = panel_combo(mask, code, code2sym)
                            log(f"chord code={code} mask={mask} combo={combo}")
                            if combo:
                                panel.show_filtered(combo)
                        continue
                    # No chord modifier held -> normal typing. Re-inject so
                    # walker's search receives it (letters, SHIFT, arrows,
                    # Enter, Esc, Backspace, …).
                    if ui is not None:
                        ui.write(e.EV_KEY, code, val)
                        ui.syn()
    finally:
        panel.close()
        for d in kbds:
            try:
                d.ungrab()
            except OSError:
                pass
        if ui is not None:
            ui.close()


def main():
    log("--- start ---")
    try:
        code2sym = build_keysym_map()
    except Exception as ex:
        log(f"keymap error: {ex}")
        notify("Keymap error")
        sys.exit(1)
    kbds = find_keyboards()
    if not kbds:
        log("no keyboard found")
        notify("No keyboard found")
        sys.exit(1)
    all_lines = subprocess.run(
        ["omarchy", "menu", "keybindings", "--print"], stdin=subprocess.DEVNULL,
        capture_output=True, text=True).stdout.splitlines()
    height = menu_height()
    run(kbds, code2sym, all_lines, height)


if __name__ == "__main__":
    main()
