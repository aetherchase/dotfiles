import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import gen_theme_data as g


class TestCollect(unittest.TestCase):
    def _theme(self, root, slug, palette_body, backgrounds=()):
        d = os.path.join(root, slug)
        os.makedirs(d)
        with open(os.path.join(d, "colors.toml"), "w") as f:
            f.write(palette_body)
        if backgrounds:
            bg = os.path.join(d, "backgrounds")
            os.makedirs(bg)
            for name in backgrounds:
                open(os.path.join(bg, name), "w").close()

    def test_palette_hex_and_backgrounds(self):
        with tempfile.TemporaryDirectory() as stock:
            self._theme(stock, "everforest",
                        'background = "#2d353b"\naccent = "#7fbbb3"\ncolor1 = "#e67e80"\n',
                        backgrounds=("a.jpg", "b.png", "notes.txt"))
            data = g.collect(stock, os.path.join(stock, "none"))
        self.assertIn("everforest", data)
        self.assertEqual(data["everforest"]["palette"][:2], ["#2d353b", "#7fbbb3"])
        bgs = [os.path.basename(p) for p in data["everforest"]["backgrounds"]]
        self.assertEqual(sorted(bgs), ["a.jpg", "b.png"])   # non-image skipped

    def test_theme_without_palette_skipped(self):
        with tempfile.TemporaryDirectory() as stock:
            os.makedirs(os.path.join(stock, "empty"))
            open(os.path.join(stock, "empty", "colors.toml"), "w").close()
            data = g.collect(stock, os.path.join(stock, "none"))
        self.assertEqual(data, {})


if __name__ == "__main__":
    unittest.main()
