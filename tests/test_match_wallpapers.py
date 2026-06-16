# tests/test_match_wallpapers.py
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


if __name__ == "__main__":
    unittest.main()
