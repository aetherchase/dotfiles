#!/usr/bin/env python3
"""Render docs/wallpapers-gallery.html from tests/fixtures/labels/*.json: each labeled
image with the matcher's verdict + score, checked against the human label."""
import glob
import html
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import match_wallpapers as mw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LABELS = os.path.join(ROOT, "tests", "fixtures", "labels")
OUT = os.path.join(ROOT, "docs", "wallpapers-gallery.html")

_STYLE = ("body{font-family:sans-serif;background:#1c1c1c;color:#ddd;margin:1.5rem}"
          "img{height:90px;border-radius:4px}"
          ".item{display:inline-block;margin:6px;text-align:center;font-size:12px;"
          "vertical-align:top;max-width:150px}"
          ".ok{outline:2px solid #7fbb7f}.bad{outline:2px solid #e06c6c}"
          ".sw{display:inline-block;width:22px;height:22px;border-radius:3px;margin:1px}")


def _labs(hexes):
    return [mw.srgb_to_lab(mw.hex_to_rgb(h)) for h in hexes]


def render(label_files: list[str]) -> str:
    out = ["<!doctype html><meta charset=utf-8><title>Wallpaper matcher gallery</title>",
           f"<style>{_STYLE}</style>"]
    for lf in label_files:
        with open(lf) as f:
            data = json.load(f)
        labs = _labs(data["palette"])
        p = data["params"]
        src = os.path.expanduser(data["source_dir"])
        out.append(f"<h2>{html.escape(data['theme'])}</h2><div>")
        out += [f'<span class="sw" style="background:{html.escape(h)}"></span>'
                for h in data["palette"]]
        out.append("</div>")
        groups: dict[str, list] = {}
        for it in data["items"]:
            key = "do" if it["label"] == "do" else f'dont / {it.get("reason") or "other"}'
            groups.setdefault(key, []).append(it)
        ev = ok = 0
        body = []
        for key in sorted(groups):
            body.append(f"<h3>{html.escape(key)}</h3>")
            for it in groups[key]:
                path = os.path.join(src, it["name"])
                score = None
                cls = ""
                if os.path.isfile(path):
                    doms = mw.dominant_colors(path, k=p["k"])
                    assigned = mw.theme_matches_image(
                        doms, labs, threshold=p["threshold"],
                        top_colors=p["top_colors"], max_hues=p["max_hues"])
                    score = round(mw.score_image_strict(doms, labs, top_n=p["top_colors"]), 1)
                    expected = it["label"] == "do"
                    ev += 1
                    ok += int(assigned == expected)
                    cls = "ok" if assigned == expected else "bad"
                    verdict = "assigned" if assigned else "rejected"
                else:
                    verdict = "missing"
                body.append(
                    f'<div class="item {cls}"><img src="file://{html.escape(path)}" alt="">'
                    f'<br>{html.escape(it["name"])}<br>{verdict} score={score}</div>')
        acc = f"{ok}/{ev} = {ok / ev:.0%}" if ev else "n/a (no originals present)"
        out.append(f"<p>accuracy: {acc}</p>")
        out += body
    return "".join(out)


def main(argv=None) -> int:
    files = sorted(glob.glob(os.path.join(LABELS, "*.json")))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(files))
    print(f"Wrote {OUT} ({len(files)} theme file(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
