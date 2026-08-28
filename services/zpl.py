from __future__ import annotations

import textwrap

from reportlab.graphics.barcode.qr import QrCodeWidget

from .contador import visible_counter
from .texto import dots, zpl_text, display_date


def zpl_text_layout(
    fields: list[str], text_width: int, available_height: int, maximum_font: int, minimum_font: int
) -> tuple[int, list[int], int]:
    """Escolhe a maior fonte estimada que mantém todos os campos dentro da área."""
    minimum_font = max(6, minimum_font)
    maximum_font = max(minimum_font, maximum_font)
    for font_size in range(maximum_font, minimum_font - 1, -1):
        average_character_width = max(1, round(font_size * 0.62))
        characters_per_line = max(1, text_width // average_character_width)
        line_counts = [
            max(1, len(textwrap.wrap(field, characters_per_line, break_long_words=True, break_on_hyphens=False)))
            for field in fields
        ]
        line_height = max(1, round(font_size * 1.10))
        minimum_gap = max(2, round(font_size * 0.20))
        used_height = sum(count * line_height for count in line_counts) + minimum_gap * (len(fields) - 1)
        if used_height <= available_height:
            spare = available_height - sum(count * line_height for count in line_counts)
            gap = max(minimum_gap, min(round(font_size * 0.65), spare // max(1, len(fields) - 1)))
            return font_size, line_counts, gap
    # Em dimensões fisicamente impossíveis, ainda devolve a menor composição possível.
    font_size = minimum_font
    average_character_width = max(1, round(font_size * 0.62))
    characters_per_line = max(1, text_width // average_character_width)
    line_counts = [
        max(1, len(textwrap.wrap(field, characters_per_line, break_long_words=True, break_on_hyphens=False)))
        for field in fields
    ]
    return font_size, line_counts, 2


def make_zpl(data: dict, counter: int, identifier: str, qr: str, cfg: dict[str, str]) -> str:
    width_mm = float(cfg["largura_mm"])
    height_mm = float(cfg["comprimento_mm"])
    dpi = int(cfg["dpi"])
    width = dots(width_mm, dpi)
    height = dots(height_mm, dpi)
    growth = max(1.0, min(width_mm / 100.0, height_mm / 60.0))
    # Magnificação 7 em 203 dpi é o tamanho mínimo já utilizado. Só cresce.
    qr_mag = max(7, min(10, round(7 * (dpi / 203) * growth)))
    qr_widget = QrCodeWidget(qr)
    qr_widget.getBounds()  # Calcula automaticamente a versão/módulos pelo conteúdo.
    estimated_qr_size = (qr_widget.qr.moduleCount + 8) * qr_mag
    right_margin = dots(5, dpi)
    top_margin = dots(2, dpi)
    preferred_qr_top = dots(7, dpi)
    qr_x = max(dots(35, dpi), width - right_margin - estimated_qr_size)
    qr_y = max(top_margin, min(preferred_qr_top, height - estimated_qr_size - top_margin))

    text_left = dots(2.2, dpi)
    text_gap_to_qr = dots(3, dpi)
    text_width = max(dots(18, dpi), qr_x - text_gap_to_qr - text_left)
    text_top = dots(max(6.5, 1 + 5.2 * growth), dpi)
    text_bottom = dots(2.5, dpi)
    available_height = max(dots(10, dpi), height - text_top - text_bottom)
    fields = [
        f"CLIENTE: {zpl_text(data.get('cliente'))}",
        f"TIPO: {zpl_text(data.get('tipo'))}",
        f"CODIGO: {zpl_text(data.get('produto_codigo'))}",
        f"COD PROD: {zpl_text(data.get('cod_prod'))}",
        f"LOTE: {zpl_text(data.get('lote_controle'))}",
        f"PRODUTO: {zpl_text(data.get('descricao'))}",
        f"VALIDADE: {zpl_text(display_date(data.get('validade')))}",
        f"FABRICACAO: {zpl_text(display_date(data.get('fabricacao')))}",
        f"QUANTIDADE: {zpl_text(data.get('quantidade'))}",
        f"OPERADOR: {zpl_text(data.get('operador'))}",
        f"MEDIDAS: {zpl_text(data.get('medidas'))}",
    ]
    maximum_font = dots(5.2 * growth, dpi)
    minimum_font = dots(1.5, dpi)
    font, line_counts, field_gap = zpl_text_layout(fields, text_width, available_height, maximum_font, minimum_font)
    serial = visible_counter(counter)
    serial_font = min(dots(5.2 * growth, dpi), max(minimum_font, round(text_width / max(5, len(serial)) * 1.4)))
    lines = [
        "^XA", "^CI27", f"^PW{width}", f"^LL{height}", "^LH0,0", "^PON",
        f"^FO{text_left},{top_margin}^A0N,{serial_font},{serial_font}^FB{text_width},1,0,R,0^FD{serial}^FS",
    ]
    current_y = text_top
    line_height = max(1, round(font * 1.10))
    for field, line_count in zip(fields, line_counts):
        lines.append(f"^FO{text_left},{current_y}^A0N,{font},{font}^FB{text_width},{line_count},0,L,0^FD{field}^FS")
        current_y += line_count * line_height + field_gap
    lines.extend([f"^FO{qr_x},{qr_y}^BQN,2,{qr_mag}^FDLA,{qr}^FS", "^XZ"])
    return "\n".join(lines)