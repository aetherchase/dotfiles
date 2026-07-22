import glob
import json
import os
import tempfile
import unittest

from PIL import Image

import match_wallpapers as mw

LABELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "labels")
_GREEN_PARAMS = {"threshold": 18.0, "top_colors": 3, "k": 5, "max_hues": 4}


def _labs(hexes):
    return [mw.srgb_to_lab(mw.hex_to_rgb(h)) for h in hexes]


def _which_gate(doms, labs, params):
    """Best-effort reason a `dont` was rejected (informational only)."""
    if mw.is_polychrome(doms, max_hues=params["max_hues"]):
        return "polychrome"
    if mw.image_is_neutral(doms) or mw.theme_is_neutral(labs) != mw.image_is_neutral(doms):
        return "neutral"
    return "wrong-hue"


def evaluate(label_file):
    """Grade the matcher against one label file.
    Returns (mismatches, evaluated, skipped_missing, reason_notes)."""
    with open(label_file) as f:
        data = json.load(f)
    labs = _labs(data["palette"])
    p = data["params"]
    src = os.path.expanduser(data["source_dir"])
    mismatches, evaluated, skipped, notes = [], 0, [], []
    for item in data["items"]:
        path = os.path.join(src, item["name"])
        if not os.path.isfile(path):
            skipped.append(item["name"])
            continue
        try:
            doms = mw.dominant_colors(path, k=p["k"])
        except Exception as e:                      # unreadable/truncated
            skipped.append(f'{item["name"]} ({e})')
            continue
        assigned = mw.theme_matches_image(doms, labs, threshold=p["threshold"],
                                          top_colors=p["top_colors"], max_hues=p["max_hues"])
        expected = item["label"] == "do"
        evaluated += 1
        if assigned != expected:
            mismatches.append((item["name"], "assigned" if assigned else "rejected", item["label"]))
        elif item["label"] == "dont" and item.get("reason"):
            gate = _which_gate(doms, labs, p)
            if gate != item["reason"]:
                notes.append(f'{item["name"]}: labeled {item["reason"]}, gate fired {gate}')
    return mismatches, evaluated, skipped, notes


class TestEvalHarness(unittest.TestCase):
    def _write_img(self, d, name, color):
        Image.new("RGB", (160, 90), color).save(os.path.join(d, name))

    def _label_file(self, d, items, palette=("#0a960a", "#283228")):
        lf = os.path.join(d, "everforest.json")
        with open(lf, "w") as f:
            json.dump({"theme": "everforest", "source_dir": d, "palette": list(palette),
                       "params": _GREEN_PARAMS, "items": items}, f)
        return lf

    def test_agreeing_labels_have_no_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_img(d, "green.png", (0, 170, 0))
            self._write_img(d, "red.png", (190, 0, 0))
            lf = self._label_file(d, [
                {"name": "green.png", "label": "do", "reason": None},
                {"name": "red.png", "label": "dont", "reason": "wrong-hue"},
            ])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(mism, [])
        self.assertEqual(ev, 2)
        self.assertEqual(skip, [])

    def test_disagreement_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_img(d, "red.png", (190, 0, 0))
            lf = self._label_file(d, [{"name": "red.png", "label": "do", "reason": None}])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(len(mism), 1)          # red should NOT match green -> mislabeled do
        self.assertEqual(ev, 1)

    def test_missing_original_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            lf = self._label_file(d, [{"name": "ghost.png", "label": "do", "reason": None}])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(ev, 0)
        self.assertEqual(skip, ["ghost.png"])

    def test_reason_note_on_gate_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            self._write_img(d, "gray.png", (128, 128, 128))   # rejected by neutral gate
            lf = self._label_file(d, [{"name": "gray.png", "label": "dont", "reason": "wrong-hue"}])
            mism, ev, skip, notes = evaluate(lf)
        self.assertEqual(mism, [])              # correctly rejected -> not a hard failure
        self.assertEqual(len(notes), 1)         # but reason mismatch noted


class TestLabeledFixtures(unittest.TestCase):
    def test_all_label_files(self):
        files = sorted(glob.glob(os.path.join(LABELS_DIR, "*.json")))
        if not files:
            self.skipTest(f"no labeled fixture files in {LABELS_DIR}")
        for lf in files:
            with self.subTest(theme=os.path.basename(lf)):
                mism, ev, skip, notes = evaluate(lf)
                if ev == 0:
                    self.skipTest(f"{os.path.basename(lf)}: no originals present "
                                  f"({len(skip)} missing)")
                acc = (ev - len(mism)) / ev
                msg = (f"accuracy {ev - len(mism)}/{ev} = {acc:.0%}; "
                       f"skipped-missing={len(skip)}; mismatches={mism}; reason-notes={notes}")
                self.assertEqual(mism, [], msg)


if __name__ == "__main__":
    unittest.main()
