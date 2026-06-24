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


class TestWriteMatches(unittest.TestCase):
    def test_writes_symlinks_and_clears_old(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as repo_bg:
            a = os.path.join(src, "a.jpg"); open(a, "w").close()
            b = os.path.join(src, "b.jpg"); open(b, "w").close()
            # pre-existing stale theme dir that must be cleared
            os.makedirs(os.path.join(repo_bg, "stale"))
            open(os.path.join(repo_bg, ".gitkeep"), "w").close()

            mw.write_matches(repo_bg, {"everforest": [a, b], "nord": [a]})

            ef = os.path.join(repo_bg, "everforest")
            self.assertTrue(os.path.islink(os.path.join(ef, "a.jpg")))
            self.assertEqual(os.readlink(os.path.join(ef, "a.jpg")), a)
            self.assertEqual(sorted(os.listdir(ef)), ["a.jpg", "b.jpg"])
            self.assertEqual(os.listdir(os.path.join(repo_bg, "nord")), ["a.jpg"])
            self.assertFalse(os.path.exists(os.path.join(repo_bg, "stale")))
            self.assertTrue(os.path.exists(os.path.join(repo_bg, ".gitkeep")))  # keeper survives


class TestRelink(unittest.TestCase):
    def test_relink_links_populated_only_and_prunes(self):
        with tempfile.TemporaryDirectory() as repo_bg, tempfile.TemporaryDirectory() as cfg:
            os.makedirs(os.path.join(repo_bg, "everforest"))
            open(os.path.join(repo_bg, "everforest", "a.jpg"), "w").close()
            os.makedirs(os.path.join(repo_bg, "empty"))   # no files -> skipped
            # stale live symlink whose repo dir no longer qualifies -> pruned
            os.symlink(os.path.join(repo_bg, "empty"), os.path.join(cfg, "empty"))

            mw.relink(repo_bg, cfg)

            ef = os.path.join(cfg, "everforest")
            self.assertTrue(os.path.islink(ef))
            self.assertEqual(os.readlink(ef), os.path.join(repo_bg, "everforest"))
            self.assertFalse(os.path.lexists(os.path.join(cfg, "empty")))  # pruned

    def test_unlink_removes_only_symlinks(self):
        with tempfile.TemporaryDirectory() as repo_bg, tempfile.TemporaryDirectory() as cfg:
            os.makedirs(os.path.join(repo_bg, "everforest"))
            open(os.path.join(repo_bg, "everforest", "a.jpg"), "w").close()
            os.symlink(os.path.join(repo_bg, "everforest"), os.path.join(cfg, "everforest"))
            os.makedirs(os.path.join(cfg, "realdir"))      # must be left alone

            mw.unlink(repo_bg, cfg)

            self.assertFalse(os.path.lexists(os.path.join(cfg, "everforest")))
            self.assertTrue(os.path.isdir(os.path.join(cfg, "realdir")))


class TestChromaHue(unittest.TestCase):
    def test_neutral_has_low_chroma(self):
        self.assertLess(mw.lab_chroma(mw.srgb_to_lab((128, 128, 128))), 2.0)

    def test_saturated_has_high_chroma(self):
        self.assertGreater(mw.lab_chroma(mw.srgb_to_lab((255, 0, 0))), 50.0)

    def test_hue_in_range(self):
        h = mw.lab_hue(mw.srgb_to_lab((255, 0, 0)))
        self.assertTrue(0.0 <= h < 360.0)


class TestPolychrome(unittest.TestCase):
    def test_rainbow_is_polychrome(self):
        doms = [((255, 0, 0), 0.17), ((255, 255, 0), 0.17), ((0, 255, 0), 0.17),
                ((0, 255, 255), 0.17), ((0, 0, 255), 0.16), ((255, 0, 255), 0.16)]
        self.assertTrue(mw.is_polychrome(doms))

    def test_focused_hue_not_polychrome(self):
        doms = [((10, 120, 10), 0.6), ((20, 140, 30), 0.4)]  # greens only
        self.assertFalse(mw.is_polychrome(doms))

    def test_neutral_not_polychrome(self):
        # near-grayscale: no chromatic sectors -> not flagged by this lever
        doms = [((20, 20, 20), 0.5), ((200, 200, 200), 0.5)]
        self.assertFalse(mw.is_polychrome(doms))


class TestStrictScore(unittest.TestCase):
    def test_worst_of_top_n(self):
        doms = [((0, 200, 0), 0.6), ((200, 0, 0), 0.4)]
        only_green = [mw.srgb_to_lab((0, 200, 0))]
        both = [mw.srgb_to_lab((0, 200, 0)), mw.srgb_to_lab((200, 0, 0))]
        s_green = mw.score_image_strict(doms, only_green, top_n=2)
        s_both = mw.score_image_strict(doms, both, top_n=2)
        red_to_green = mw.ciede2000(mw.srgb_to_lab((200, 0, 0)), only_green[0])
        # worst prominent color (red) governs the score against a green-only theme
        self.assertAlmostEqual(s_green, red_to_green, places=3)
        self.assertLess(s_both, 1.0)   # both prominent colors covered

    def test_tail_color_beyond_top_n_ignored(self):
        doms = [((0, 200, 0), 0.5), ((0, 190, 0), 0.45), ((200, 0, 0), 0.05)]
        only_green = [mw.srgb_to_lab((0, 200, 0))]
        s = mw.score_image_strict(doms, only_green, top_n=2)
        self.assertLess(s, 5.0)   # tiny-weight red excluded from top-2

    def test_empty_theme_is_inf(self):
        self.assertEqual(mw.score_image_strict([((0, 0, 0), 1.0)], [], top_n=3),
                         float("inf"))


class TestNeutralGate(unittest.TestCase):
    def test_image_mean_chroma(self):
        self.assertLess(mw.image_mean_chroma([((100, 100, 100), 1.0)]), 2.0)
        self.assertGreater(mw.image_mean_chroma([((255, 0, 0), 1.0)]), 50.0)

    def test_image_is_neutral(self):
        self.assertTrue(mw.image_is_neutral([((30, 30, 30), 0.5), ((200, 200, 200), 0.5)]))
        self.assertFalse(mw.image_is_neutral([((0, 200, 0), 1.0)]))

    def test_theme_is_neutral(self):
        gray_theme = [mw.srgb_to_lab((20, 20, 20)), mw.srgb_to_lab((200, 200, 200))]
        color_theme = [mw.srgb_to_lab((20, 20, 20)), mw.srgb_to_lab((0, 180, 0))]
        self.assertTrue(mw.theme_is_neutral(gray_theme))
        self.assertFalse(mw.theme_is_neutral(color_theme))

    def test_empty_theme_not_neutral(self):
        self.assertFalse(mw.theme_is_neutral([]))


class TestNeutralCurate(unittest.TestCase):
    def test_neutral_image_only_matches_neutral_theme(self):
        with tempfile.TemporaryDirectory() as src, \
             tempfile.TemporaryDirectory() as stock, \
             tempfile.TemporaryDirectory() as repo_bg, \
             tempfile.TemporaryDirectory() as cfg:
            Image.new("RGB", (160, 90), (128, 128, 128)).save(os.path.join(src, "gray.png"))
            # mono theme: grayscale palette only
            d = os.path.join(stock, "mono"); os.makedirs(d)
            with open(os.path.join(d, "colors.toml"), "w") as f:
                f.write('background = "#202020"\ncolor1 = "#c8c8c8"\n')
            # forest theme: chromatic palette
            d = os.path.join(stock, "forest"); os.makedirs(d)
            with open(os.path.join(d, "colors.toml"), "w") as f:
                f.write('background = "#202020"\ncolor1 = "#10c010"\n')

            mw.curate(source=src, stock_dir=stock, user_dir=os.path.join(stock, "none"),
                      repo_bg_dir=repo_bg, config_bg_dir=cfg, assume_yes=True)

            self.assertIn("gray.png", os.listdir(os.path.join(repo_bg, "mono")))
            self.assertFalse(os.path.isdir(os.path.join(repo_bg, "forest")))  # gated out


class TestCurate(unittest.TestCase):
    def _theme(self, root, slug, *hexes):
        d = os.path.join(root, slug); os.makedirs(d)
        body = "".join(f'color{i+1} = "{h}"\n' for i, h in enumerate(hexes))
        with open(os.path.join(d, "colors.toml"), "w") as f:
            f.write('background = "#202020"\n' + body)

    def test_end_to_end_assigns_by_color(self):
        with tempfile.TemporaryDirectory() as src, \
             tempfile.TemporaryDirectory() as stock, \
             tempfile.TemporaryDirectory() as repo_bg, \
             tempfile.TemporaryDirectory() as cfg:
            Image.new("RGB", (160, 90), (0, 200, 0)).save(os.path.join(src, "green.png"))
            Image.new("RGB", (160, 90), (200, 0, 0)).save(os.path.join(src, "red.png"))
            Image.new("RGB", (90, 160), (0, 200, 0)).save(os.path.join(src, "tall.png"))  # portrait -> dropped
            self._theme(stock, "forest", "#10c010", "#1faa1f")
            self._theme(stock, "ember", "#c01010", "#aa1f1f")

            mw.curate(source=src, stock_dir=stock, user_dir=os.path.join(stock, "none"),
                      repo_bg_dir=repo_bg, config_bg_dir=cfg,
                      min_ratio=1.0, threshold=18.0, k=5, assume_yes=True)

            forest = os.listdir(os.path.join(repo_bg, "forest"))
            ember = os.listdir(os.path.join(repo_bg, "ember"))
            self.assertIn("green.png", forest)
            self.assertNotIn("red.png", forest)
            self.assertIn("red.png", ember)
            self.assertNotIn("tall.png", forest + ember)        # portrait filtered
            self.assertTrue(os.path.islink(os.path.join(cfg, "forest")))  # relinked


if __name__ == "__main__":
    unittest.main()
