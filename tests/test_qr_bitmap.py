from __future__ import annotations

import re
import unittest

from reportlab.graphics.barcode.qr import QrCodeWidget

from services.qrcode_service import qr_payload, render_bitmap
from services.zpl import make_zpl
from tests.test_zpl_layout import IDENTIFIER, LABEL, SETTINGS


class QrBitmapTests(unittest.TestCase):
    def test_bitmap_fills_the_entire_square(self) -> None:
        for text in ("TESTE", qr_payload(LABEL, IDENTIFIER), "AÇÃO ÇÃ " * 20):
            with self.subTest(text=text):
                bitmap = render_bitmap(text, 202)
                self.assertEqual(bitmap.size, (202, 202))
                self.assertEqual(bitmap.mode, "1")
                reference = QrCodeWidget(text, barLevel="L")
                reference.qr.make()
                modules = reference.qr.modules
                count = len(modules)
                cell = 202 / count
                for row in range(202):
                    for col in range(202):
                        module_row = min(count - 1, max(0, int(col / cell)))
                        module_col = min(count - 1, max(0, int(row / cell)))
                        expected_dark = modules[module_col][module_row]
                        self.assertEqual(bitmap.getpixel((col, row)) == 0, bool(expected_dark))

    def test_zpl_bitmap_preserves_pixels_and_fits_qr_square(self) -> None:
        text = qr_payload(LABEL, IDENTIFIER)
        zpl = make_zpl(LABEL, 3, IDENTIFIER, text, SETTINGS)
        graphic = re.search(
            r"\^FXQR\^FS\s*\^FO(\d+),(\d+)\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS", zpl,
        )
        self.assertIsNotNone(graphic)
        x, y, total, used, bytes_per_row = map(int, graphic.groups()[:5])
        pixels = bytes.fromhex(graphic.group(6))
        expected = render_bitmap(text, 202)
        self.assertEqual((x, y), (28, 28))
        self.assertEqual(total, used)
        self.assertEqual(len(pixels), total)
        self.assertEqual(total // bytes_per_row, 202)
        self.assertLessEqual(y + 202, 232)
        self.assertLessEqual(x + 202, 232)
        for row in range(202):
            for col in range(bytes_per_row * 8):
                actual_dark = bool(pixels[row * bytes_per_row + col // 8] & (1 << (7 - col % 8)))
                expected_dark = col < 202 and expected.getpixel((col, row)) == 0
                self.assertEqual(actual_dark, expected_dark)

    def test_too_small_area_is_rejected_before_an_unreadable_qr_is_created(self) -> None:
        with self.assertRaisesRegex(ValueError, "não cabe"):
            render_bitmap("TESTE", 9)


if __name__ == "__main__":
    unittest.main()
