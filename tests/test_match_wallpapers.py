# tests/test_match_wallpapers.py
import os
import tempfile
import unittest

import match_wallpapers as mw


class TestRatio(unittest.TestCase):
    def test_landscape_kept(self):
        self.assertTrue(mw.passes_ratio(2560, 1440, 1.0))

    def test_square_kept_at_default(self):
        self.assertTrue(mw.passes_ratio(1000, 1000, 1.0))

    def test_portrait_rejected(self):
        self.assertFalse(mw.passes_ratio(1080, 1920, 1.0))

    def test_custom_min_ratio(self):
        # 4:3 = 1.333 rejected when we demand >= 1.5
        self.assertFalse(mw.passes_ratio(1600, 1200, 1.5))


class TestLab(unittest.TestCase):
    def test_white(self):
        L, a, b = mw.srgb_to_lab((255, 255, 255))
        self.assertAlmostEqual(L, 100.0, places=1)
        self.assertAlmostEqual(a, 0.0, places=1)
        self.assertAlmostEqual(b, 0.0, places=1)

    def test_black(self):
        L, a, b = mw.srgb_to_lab((0, 0, 0))
        self.assertAlmostEqual(L, 0.0, places=2)

    def test_red(self):
        L, a, b = mw.srgb_to_lab((255, 0, 0))
        self.assertAlmostEqual(L, 53.24, places=1)
        self.assertAlmostEqual(a, 80.09, places=1)
        self.assertAlmostEqual(b, 67.20, places=1)


class TestCiede2000(unittest.TestCase):
    def test_identity(self):
        self.assertAlmostEqual(mw.ciede2000((50, 2.5, 0), (50, 2.5, 0)), 0.0, places=4)

    def test_sharma_pair_1(self):
        d = mw.ciede2000((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485))
        self.assertAlmostEqual(d, 2.0425, places=4)

    def test_sharma_pair_2(self):
        d = mw.ciede2000((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485))
        self.assertAlmostEqual(d, 2.8615, places=4)

    def test_sharma_pair_3(self):
        d = mw.ciede2000((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485))
        self.assertAlmostEqual(d, 3.4412, places=4)


class TestParsePalette(unittest.TestCase):
    SAMPLE = (
        'accent = "#7fbbb3"\n'
        'background = "#2d353b"\n'
        'foreground = "#d3c6aa"\n'
        'color0 = "#475258"\n'
        'color1 = "#e67e80"\n'
        'color2 = "#a7c080"\n'
        'color3 = "#dbbc7f"\n'
        'color4 = "#7fbbb3"\n'
        'color5 = "#d699b6"\n'
        'color6 = "#83c092"\n'
        'color7 = "#d3c6aa"\n'
    )

    def test_hex_to_rgb(self):
        self.assertEqual(mw.hex_to_rgb("#7fbbb3"), (127, 187, 179))

    def test_parse_uses_match_subset(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "colors.toml")
            with open(p, "w") as f:
                f.write(self.SAMPLE)
            rgbs = mw.parse_palette(p)
        # background, accent, color1..6 present in sample => 8 entries
        # (color9..14 absent in this sample, simply skipped)
        self.assertIn((45, 53, 59), rgbs)      # background
        self.assertIn((127, 187, 179), rgbs)   # accent
        self.assertIn((230, 126, 128), rgbs)   # color1
        self.assertNotIn((71, 82, 88), rgbs)   # color0 excluded
        self.assertEqual(len(rgbs), 8)


if __name__ == "__main__":
    unittest.main()
