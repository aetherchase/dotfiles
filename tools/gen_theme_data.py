#!/usr/bin/env python3
"""Generate tools/fixtures-labeler/themes.js (window.FIXTURE_THEMES) from omarchy
theme palettes + backgrounds, for the static labeling form's hints/dropdown."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import match_wallpapers as mw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures-labeler", "themes.js")


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def collect(stock_dir: str, user_dir: str) -> dict:
    """Map theme slug -> {palette: [hex], backgrounds: [abs paths]} (user wins on clash)."""
    out: dict[str, dict] = {}
    for base in (stock_dir, user_dir):
        if not os.path.isdir(base):
            continue
        for slug in sorted(os.listdir(base)):
            tdir = os.path.join(base, slug)
            toml_path = os.path.join(tdir, "colors.toml")
            if not os.path.isfile(toml_path):
                continue
            rgbs = mw.parse_palette(toml_path)
            if not rgbs:
                continue
            bg_dir = os.path.join(tdir, "backgrounds")
            backgrounds = []
            if os.path.isdir(bg_dir):
                backgrounds = [os.path.join(bg_dir, f) for f in sorted(os.listdir(bg_dir))
                               if f.lower().endswith(mw.IMAGE_EXTS)]
            out[slug] = {"palette": [_hex(c) for c in rgbs], "backgrounds": backgrounds}
    return out


def main(argv=None) -> int:
    data = collect(mw.DEFAULT_STOCK, mw.DEFAULT_USER)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("window.FIXTURE_THEMES = " + json.dumps(data, indent=2) + ";\n")
    print(f"Wrote {len(data)} theme(s) to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
