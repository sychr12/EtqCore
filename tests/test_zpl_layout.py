from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from unittest.mock import patch

from services.qrcode_service import qr_payload, render_bitmap
from services.zpl import make_zpl


SETTINGS = {
    "largura_mm": "100", "comprimento_mm": "60", "dpi": "203",
    "velocidade_ips": "3", "tonalidade": "10",
    "deslocamento_x_mm": "0", "deslocamento_y_mm": "0",
}
LABEL = {
    "tipo": "2", "produto_codigo": "2000000444", "cod_prod": "2000000444",
    "descricao": "TUBETE ADELBRAS 711", "lote_controle": "0812/2026",
    "lote_base": "4016/2026", "quantidade": "910", "unidade": "pcs",
    "operador": "252", "medidas": "76,5 x 2,5 x 18mm",
    "fabricacao": "2026-08-05", "validade": "2029-01-31", "dpd": "",
}
IDENTIFIER = "TB0000000003"


@dataclass(frozen=True)
class TextField:
    x: int
    y: int
    height: int
    width: int
    lines: int
    gap: int
    alignment: str
    value: str

    @property
    def bottom(self) -> int:
        return self.y + self.height * self.lines + self.gap * (self.lines - 1)


def raw_text_fields(zpl: str) -> list[TextField]:
    pattern = (
        r"\^FO(\d+),(\d+)\^A0N,(\d+),\d+"
        r"\^FB(\d+),(\d+),(-?\d+),([LCRJ]),0\^FD([^\^]*)\^FS"
    )
    return [
        TextField(*(int(value) for value in match[:6]), match[6], match[7])
        for match in re.findall(pattern, zpl)
    ]


def text_fields(zpl: str) -> list[TextField]:
    """Agrupa somente as sobreimpressões consecutivas do mesmo campo."""
    result: list[TextField] = []
    for field in raw_text_fields(zpl):
        if result:
            previous = result[-1]
            if (
                0 < field.x - previous.x <= 2
                and (field.y, field.height, field.width, field.lines, field.gap,
                     field.alignment, field.value)
                == (previous.y, previous.height, previous.width, previous.lines,
                    previous.gap, previous.alignment, previous.value)
            ):
                continue
        result.append(field)
    return result


def boxes(zpl: str) -> list[tuple[int, int, int, int, int]]:
    return [
        tuple(int(value) for value in match)
        for match in re.findall(r"\^FO(\d+),(\d+)\^GB(\d+),(\d+),(\d+),B,0\^FS", zpl)
    ]


class ZebraLayoutTests(unittest.TestCase):
    def variants(self):
        for client in ("", "AMAZONTAPE"):
            for observation in ("", "teste"):
                data = {**LABEL, "cliente": client, "observacao": observation}
                yield data, make_zpl(data, 3, IDENTIFIER, qr_payload(data, IDENTIFIER), SETTINGS)

    def field(self, zpl: str, value: str) -> TextField:
        matches = [field for field in text_fields(zpl) if field.value == value]
        self.assertEqual(len(matches), 1, f"Campo esperado uma vez: {value}")
        return matches[0]

    def test_qr_has_a_complete_vertical_separator_in_every_layout(self) -> None:
        # Na etiqueta de 100 x 60 mm, o QR ocupa x28..232 / y28..232.
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                separators = [box for box in boxes(zpl) if box[0] == 232 and box[1] == 28]
                self.assertEqual(len(separators), 1)
                _, y, width, height, thickness = separators[0]
                self.assertEqual(y + height, 232)
                self.assertEqual(width, thickness)
                self.assertGreaterEqual(thickness, 3)

    def test_product_title_is_left_aligned_and_lowered_without_touching_rules(self) -> None:
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                title = self.field(zpl, data["descricao"])
                rules = {box[1]: box for box in boxes(zpl) if box[0] == 28 and box[2] > box[3]}
                upper, lower = rules[232], rules[292]
                self.assertGreaterEqual(title.y - (upper[1] + upper[3]), 8)
                self.assertGreaterEqual(lower[1] - title.bottom, 4)
                self.assertEqual(title.alignment, "L")
                self.assertLessEqual(title.x - upper[0], 20)
                self.assertGreaterEqual(title.height, 40)

    def test_codes_and_operator_keep_clearance_from_cell_borders(self) -> None:
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                fields = text_fields(zpl)
                codes = [field for field in fields if field.value == data["produto_codigo"]]
                self.assertEqual(len(codes), 2)
                for code in codes:
                    self.assertGreaterEqual(code.y - 296, 4)
                    self.assertGreaterEqual(368 - code.bottom, 4)
                    self.assertGreaterEqual(code.height, 43)
                operator = self.field(zpl, data["operador"])
                self.assertGreaterEqual(operator.y - 133, 4)
                self.assertGreaterEqual(232 - operator.bottom, 8)

    def test_quantity_and_operator_use_matching_vertical_alignment(self) -> None:
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                quantity_label = self.field(zpl, "QUANTIDADE")
                operator_label = self.field(zpl, "OPERADOR")
                quantity = self.field(zpl, "910 pcs")
                operator = self.field(zpl, "252")
                self.assertEqual(quantity_label.y, operator_label.y)
                # A quantidade pode precisar de fonte menor; as caixas ficam
                # centradas na mesma altura, com arredondamento de até um dot.
                self.assertLessEqual(
                    abs((quantity.y + quantity.bottom) - (operator.y + operator.bottom)), 1,
                )
                self.assertGreaterEqual(quantity.y - quantity_label.bottom, 4)
                self.assertGreaterEqual(operator.y - operator_label.bottom, 4)

    def test_requested_text_is_bold_without_creating_extra_values(self) -> None:
        for data, zpl in self.variants():
            with self.subTest(client=data["cliente"], observation=data["observacao"]):
                raw_fields = raw_text_fields(zpl)
                values = {
                    data["descricao"], data["produto_codigo"], data["cod_prod"],
                    "COD:", "COD PROD:", "MEDIDAS:", data["medidas"],
                }
                for field in text_fields(zpl):
                    if field.value not in values:
                        continue
                    copies = [
                        candidate for candidate in raw_fields
                        if candidate.value == field.value and candidate.y == field.y
                        and field.x <= candidate.x <= field.x + 2
                    ]
                    self.assertEqual([copy.x - field.x for copy in copies], [0, 1, 2])
                    self.assertTrue(all(copy.height == field.height for copy in copies))

    def test_brand_reads_from_bottom_to_top_inside_its_strip(self) -> None:
        data = {**LABEL, "cliente": "AMAZONTAPE"}
        zpl = make_zpl(data, 3, IDENTIFIER, qr_payload(data, IDENTIFIER), SETTINGS)
        fields = re.findall(r"\^FO(\d+),(\d+)\^FR\^A0B,(\d+),(\d+)\^FDAMAZONTAPE\^FS", zpl)
        self.assertTrue(fields, "A marca deve usar a rotação inferior-para-superior (^A0B).")
        for x, y, height, width in fields:
            self.assertGreaterEqual(int(x), 700)
            self.assertLessEqual(int(x) + int(height), 772)
            self.assertGreaterEqual(int(y), 28)
            self.assertLessEqual(int(y), 452)
        self.assertNotIn("^A0R,", zpl)

    def test_layout_changes_preserve_the_exact_requested_qr_payload(self) -> None:
        expected = (
            "(E)04(T)2(P)2000000110(D)TUBETE ADELBRAS 48MMX3X2,5MM"
            "(S)0812/2026(Q)476000(Y)(I)TB0000000003(U)UN(L)"
        )
        for observation in ("", "teste", "Separar para inspeção"):
            with self.subTest(observation=observation):
                data = {
                    **LABEL, "produto_codigo": "2000000110",
                    "descricao": "TUBETE ADELBRAS 48MMX3X2,5MM", "quantidade": "476",
                    "unidade": "UN", "lote_base": "", "observacao": observation,
                }
                payload = qr_payload(data, IDENTIFIER)
                self.assertEqual(payload, expected)
                with patch("services.zpl.render_bitmap", wraps=render_bitmap) as renderer:
                    zpl = make_zpl(data, 3, IDENTIFIER, payload, SETTINGS)
                renderer.assert_called_once_with(expected, 202)
                self.assertIn("^FXQR^FS", zpl)


if __name__ == "__main__":
    unittest.main()
