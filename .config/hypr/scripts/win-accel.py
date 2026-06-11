#!/usr/bin/env python3
"""Generate a libinput `custom` acceleration curve that mimics the Windows
"Enhance pointer precision" (EPP) feel, for use in Hyprland's accel_profile.

Prints a line ready to paste into a device{} block in input-devices.conf:
    accel_profile = custom <step> <p0> <p1> ... <pN>

Adapted from fufexan's script (https://gist.github.com/fufexan/de2099bc3086f3a6c83d61fc1fcc06c9),
itself from yinonburgansky (https://gist.github.com/yinonburgansky/7be4d0489a0df8c06a923240b8eb0191).
Math: http://www.esreality.com/index.php?a=post&id=1945096

NOT bit-exact: Windows also applies temporal smoothing + subpixel carry that a
static libinput lookup curve can't reproduce. This matches the velocity-gain
curve, which is the dominant component of the feel.

MACHINE-SPECIFIC: edit the PARAMETERS for this host, then re-run:
    python3 ~/.config/hypr/scripts/win-accel.py
and paste the output into each device block in input-devices.conf.

DPI note: device_dpi scales ONLY `step` (linearly). The point values do not
change with DPI. So if you change DPI, you can just rescale step instead of
re-running (e.g. 800->1600 means step *= 2).
"""
import struct

# ===== PARAMETERS (edit for this machine) =====
device_dpi = 2400           # mouse DPI (ATK Hex80). Derived from "3x too fast" feedback at 800. CONFIRM in mouse software.
screen_dpi = 96             # Windows logical baseline; leave at 96
screen_scaling_factor = 1.3 # matches monitors.conf: DP-2 scale 1.3
sensitivity_factor = 6      # Windows pointer-speed slider notch: 6 = 1.0 (default)
sample_point_count = 20     # more points = closer to the true Windows curve
# slider table: 1=0.1 2=0.2 3=0.4 4=0.6 5=0.8 6=1.0 7=1.2 8=1.4 9=1.6 10=1.8 11=2.0
# ===== END PARAMETERS =====

scale_x = device_dpi / 1e3
scale_y = screen_dpi / 1e3 / screen_scaling_factor * sensitivity_factor

def f16(n):
    return struct.unpack('<i', n[:-4])[0] / 0xffff

# Windows 10 registry SmoothMouseXCurve / SmoothMouseYCurve (default values)
X = [b'\x00\x00\x00\x00\x00\x00\x00\x00', b'\x15\x6e\x00\x00\x00\x00\x00\x00',
     b'\x00\x40\x01\x00\x00\x00\x00\x00', b'\x29\xdc\x03\x00\x00\x00\x00\x00',
     b'\x00\x00\x28\x00\x00\x00\x00\x00']
Y = [b'\x00\x00\x00\x00\x00\x00\x00\x00', b'\xfd\x11\x01\x00\x00\x00\x00\x00',
     b'\x00\x24\x04\x00\x00\x00\x00\x00', b'\x00\xfc\x12\x00\x00\x00\x00\x00',
     b'\x00\xc0\xbb\x01\x00\x00\x00\x00']

windows_points = [[f16(a), f16(b)] for a, b in zip(X, Y)]
points = [[x * scale_x, y * scale_y] for x, y in windows_points]

def find2points(x):
    i = 0
    while i < len(points) - 2 and x >= points[i + 1][0]:
        i += 1
    return points[i], points[i + 1]

def interpolate(x):
    (x0, y0), (x1, y1) = find2points(x)
    return ((x - x0) * y1 + (x1 - x) * y0) / (x1 - x0)

max_x = points[-2][0]
step = max_x / (sample_point_count - 2)
xs = [i * step for i in range(sample_point_count)]
ys = [interpolate(x) for x in xs]
body = ' '.join(f'{y:.3f}' for y in ys)

print(f"# device_dpi={device_dpi} screen_dpi={screen_dpi} "
      f"scaling={screen_scaling_factor} sens={sensitivity_factor} pts={sample_point_count}")
print(f"accel_profile = custom {step:.10f} {body}")
