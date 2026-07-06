import json
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import gen_gallery as gg


class TestRender(unittest.TestCase):
    def _fixture(self, d):
        Image.new("RGB", (160, 90), (0, 170, 0)).save(os.path.join(d, "green.png"))
        lf = os.path.join(d, "everforest.json")
        with open(lf, "w") as f:
            json.dump({"theme": "everforest", "source_dir": d,
                       "palette": ["#0a960a", "#283228"],
                       "params": {"threshold": 18.0, "top_colors": 3, "k": 5, "max_hues": 4},
                       "items": [{"name": "green.png", "label": "do", "reason": None}]}, f)
        return lf

    def test_html_has_theme_item_and_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            html = gg.render([self._fixture(d)])
        self.assertIn("everforest", html)
        self.assertIn("green.png", html)
        self.assertIn("assigned", html)          # green matches green -> assigned
        self.assertIn("accuracy", html)

    def test_missing_original_marked(self):
        with tempfile.TemporaryDirectory() as d:
            lf = os.path.join(d, "t.json")
            with open(lf, "w") as f:
                json.dump({"theme": "t", "source_dir": d, "palette": ["#0a960a"],
                           "params": {"threshold": 18.0, "top_colors": 3, "k": 5, "max_hues": 4},
                           "items": [{"name": "ghost.png", "label": "do", "reason": None}]}, f)
            html = gg.render([lf])
        self.assertIn("missing", html)


if __name__ == "__main__":
    unittest.main()
