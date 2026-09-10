from __future__ import annotations

import re
import unittest

from services.qrcode_service import qr_payload
from services.zpl import _logo_gfa_data, make_zpl
from tests.test_zpl_layout import IDENTIFIER, LABEL, SETTINGS, boxes, text_fields


class ZebraFooterTests(unittest.TestCase):
    def variants(self):
        for client in ("", "AMAZONTAPE"):
            for observation in ("", "teste"):
                data = {**LABEL, "cliente": client, "observacao": observation}
                yield data, make_zpl(data, 3, IDENTIFIER, qr_payload(data, IDENTIFIER), SETTINGS)

    def test_logo_bitmap_has_exact_byte_length_for_non_byte_aligned_widths(self) -> None:
        for target_width in (78, 119):
            with self.subTest(width=target_width):
                width, height, bytes_per_row, hex_data = _logo_gfa_data(target_width)
                self.assertEqual(width, target_width)
                self.assertGreater(height, 0)
                self.assertEqual(bytes_per_row, (target_width + 7) // 8)
                self.assertEqual(len(hex_data), height * bytes_per_row * 2)
                pixels = bytes.fromhex(hex_data)
                unused_bits = bytes_per_row * 8 - target_width
                for row in range(height):
                    self.assertEqual(pixels[(row + 1) * bytes_per_row - 1] & ((1 << unused_bits) - 1), 0)

    def test_logo_fills_footer_height_and_stays_inside_its_cell(self) -> None:
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                graphics = re.findall(
                    r"\^FO(\d+),(\d+)\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS", zpl,
                )
                graphics = [graphic for graphic in graphics if int(graphic[1]) >= 368]
                self.assertEqual(len(graphics), 1)
                x, y, total, used, bytes_per_row = map(int, graphics[0][:5])
                pixels = bytes.fromhex(graphics[0][5])
                height = total // bytes_per_row
                self.assertEqual(total, used)
                self.assertEqual(len(pixels), total)
                self.assertGreaterEqual(height, 60)
                self.assertGreaterEqual(y, 372)
                self.assertLessEqual(y + height, 446)
                separators = sorted(
                    box[0] for box in boxes(zpl)
                    if box[1] == 368 and box[3] > box[2]
                )
                self.assertEqual(len(separators), 2 if data["observacao"] else 1)
                logo_left = separators[0] + 4
                content_right = 700 if data["cliente"] else 772
                logo_right = separators[1] if data["observacao"] else content_right
                self.assertGreaterEqual(x, logo_left)
                self.assertLessEqual(x + bytes_per_row * 8, logo_right)

    def test_measurements_are_larger_and_clear_of_footer_borders(self) -> None:
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                fields = text_fields(zpl)
                label = next(field for field in fields if field.value == "MEDIDAS:")
                value = next(field for field in fields if field.value == data["medidas"])
                self.assertGreaterEqual(value.height, 32 if data["observacao"] else 40)
                self.assertGreaterEqual(value.y - label.bottom, 4)
                self.assertLessEqual(value.bottom, 446)
                observation_labels = [field for field in fields if field.value == "OBSERVAÇÃO:"]
                self.assertEqual(len(observation_labels), 1 if data["observacao"] else 0)


if __name__ == "__main__":
    unittest.main()
