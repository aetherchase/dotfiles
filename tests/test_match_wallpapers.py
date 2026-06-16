# tests/test_match_wallpapers.py
import os
import tempfile
import unittest

from PIL import Image

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


class TestDominant(unittest.TestCase):
    def _png(self, d, name, color, size=(64, 64)):
        p = os.path.join(d, name)
        Image.new("RGB", size, color).save(p)
        return p

    def test_solid_red(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._png(d, "red.png", (255, 0, 0))
            doms = mw.dominant_colors(p, k=5)
        self.assertEqual(len(doms), 1)            # only one color present
        rgb, weight = doms[0]
        self.assertEqual(rgb, (255, 0, 0))
        self.assertAlmostEqual(weight, 1.0, places=3)

    def test_weights_sum_to_one(self):
        with tempfile.TemporaryDirectory() as d:
            img = Image.new("RGB", (100, 100), (0, 0, 255))
            for x in range(100):           # half blue, half green
                for y in range(50):
                    img.putpixel((x, y), (0, 255, 0))
            p = os.path.join(d, "split.png")
            img.save(p)
            doms = mw.dominant_colors(p, k=5)
        self.assertAlmostEqual(sum(w for _, w in doms), 1.0, places=3)


class TestScore(unittest.TestCase):
    def test_green_image_closer_to_green_theme(self):
        green_doms = [((0, 200, 0), 1.0)]
        green_theme = [mw.srgb_to_lab((10, 190, 10)), mw.srgb_to_lab((40, 40, 40))]
        red_theme = [mw.srgb_to_lab((200, 10, 10)), mw.srgb_to_lab((40, 40, 40))]
        s_green = mw.score_image(green_doms, green_theme)
        s_red = mw.score_image(green_doms, red_theme)
        self.assertLess(s_green, s_red)

    def test_score_is_weighted_min_distance(self):
        doms = [((0, 200, 0), 0.5), ((0, 0, 200), 0.5)]
        theme = [mw.srgb_to_lab((0, 200, 0))]  # exactly matches the green dom
        s = mw.score_image(doms, theme)
        # green term contributes ~0, blue term contributes 0.5 * dist(blue,green)
        blue_dist = mw.ciede2000(mw.srgb_to_lab((0, 0, 200)), theme[0])
        self.assertAlmostEqual(s, 0.5 * blue_dist, places=3)


class TestLoadThemes(unittest.TestCase):
    def _theme(self, root, slug, accent="#7fbbb3"):
        d = os.path.join(root, slug)
        os.makedirs(d)
        with open(os.path.join(d, "colors.toml"), "w") as f:
            f.write(f'accent = "{accent}"\nbackground = "#2d353b"\ncolor1 = "#e67e80"\n')

    def test_loads_stock_and_user(self):
        with tempfile.TemporaryDirectory() as stock, tempfile.TemporaryDirectory() as user:
            self._theme(stock, "everforest")
            self._theme(user, "aether")
            themes = mw.load_themes(stock, user)
        self.assertEqual(set(themes), {"everforest", "aether"})
        self.assertTrue(all(len(labs) == 3 for labs in themes.values()))

    def test_missing_dirs_ok(self):
        themes = mw.load_themes("/no/such/stock", "/no/such/user")
        self.assertEqual(themes, {})


if __name__ == "__main__":
    unittest.main()
