import unittest

import pdf_ikkcu


class PDFIkkcuHelpersTest(unittest.TestCase):
    def test_ui_family_returns_platform_font_tuple(self):
        self.assertTrue(pdf_ikkcu.MG)
        self.assertTrue(all(isinstance(name, str) for name in pdf_ikkcu.MG))

    def test_display_scaling_target_is_positive(self):
        self.assertGreaterEqual(pdf_ikkcu._display_scaling_target(), 1.1)

    def test_base_font_size_is_readable(self):
        self.assertGreaterEqual(pdf_ikkcu.FS, 10)
        self.assertGreater(pdf_ikkcu.FS_TTL, pdf_ikkcu.FS)

    def test_button_text_color_returns_visible_color(self):
        self.assertNotEqual(pdf_ikkcu.button_text_color("white"), "")
        self.assertEqual(pdf_ikkcu.button_text_color("#111827"), "#111827")

    def test_close_handler_exists(self):
        self.assertTrue(callable(pdf_ikkcu.PDFIkkcu._on_close))

    def test_parse_ranges_accepts_single_pages_and_ranges(self):
        self.assertEqual(
            pdf_ikkcu.PDFIkkcu._parse_ranges("1-2, 4", 5),
            [[0, 1], [3]],
        )

    def test_parse_ranges_rejects_out_of_bounds(self):
        with self.assertRaises(ValueError):
            pdf_ikkcu.PDFIkkcu._parse_ranges("2-6", 5)


if __name__ == "__main__":
    unittest.main()
