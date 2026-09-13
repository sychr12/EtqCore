"""Monta o conteúdo rastreável do QR e cria sua imagem para a prévia."""

from __future__ import annotations

import math

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from PIL import Image, ImageDraw

from .texto import qr_text
from .texto import quantity_x1000


def qr_payload(data: dict, identifier: str, branch: str = "04") -> str:
    """Organiza os campos no formato esperado pelo leitor da produção."""
    description = qr_text(data.get("descricao"))
    measurements = qr_text(data.get("medidas"))
    # As medidas fazem parte de (D), sem repetir as já escritas na descrição.
    if measurements and measurements not in description:
        description = " ".join(part for part in (description, measurements) if part)
    fields = (
        ("E", qr_text(data.get("filial", branch))),
        ("T", qr_text(data.get("tipo"))),
        ("P", qr_text(data.get("produto_codigo"))),
        ("D", description),
        ("S", qr_text(data.get("lote_controle"))),
        ("Q", quantity_x1000(data.get("quantidade"))),
        ("Y", qr_text(data.get("dpd"))),
        ("I", qr_text(identifier)),
        ("U", qr_text(data.get("unidade"))),
        ("L", qr_text(data.get("lote_base"))),
    )
    return "".join(f"({tag}){value}" for tag, value in fields)


def render_svg(text: str, size: int = 360) -> str:
    """Transforma o texto do QR em uma imagem vetorial nítida no navegador."""
    widget = QrCodeWidget(
        text,
        barBorder=1
    )

    bounds = widget.getBounds()

    drawing = Drawing(
        size,
        size,
        transform=[
            size / (bounds[2] - bounds[0]),
            0,
            0,
            size / (bounds[3] - bounds[1]),
            0,
            0,
        ],
    )

    drawing.add(widget)

    return renderSVG.drawToString(drawing)


def render_bitmap(text: str, size: int) -> Image.Image:
    """
    Cria o QR preenchendo praticamente toda a área disponível,
    ocupando a área quadrada pedida.
    """

    widget = QrCodeWidget(
        text,
        barLevel="L",
    )

    widget.qr.make()

    modules = widget.qr.modules

    # A área do QR já está reservada separadamente no layout da etiqueta. A
    # matriz é desenhada integralmente para que o tamanho solicitado seja
    # determinístico e não haja reamostragem irregular dos módulos.
    border = 0

    module_count = len(modules)
    count = module_count + (border * 2)

    if size < count * 2:
        raise ValueError(
            "O QR não cabe com boa definição. "
            "Aumente as dimensões da etiqueta."
        )

    # Calcula os limites para ocupar exatamente o tamanho disponível
    # Use limites superiores (ceil) para que cada pixel siga exatamente a
    # regra ``floor(pixel * módulos / tamanho)`` usada por leitores e pela
    # prévia. Arredondar para o mais próximo desloca alguns módulos em
    # tamanhos que não são múltiplos da matriz.
    edges = [
        math.ceil(index * size / count)
        for index in range(count + 1)
    ]

    bitmap = Image.new(
        "1",
        (size, size),
        1
    )

    draw = ImageDraw.Draw(bitmap)

    for row, cells in enumerate(modules):
        for col, dark in enumerate(cells):
            if dark:
                x1 = edges[col + border]
                y1 = edges[row + border]

                x2 = edges[col + border + 1] - 1
                y2 = edges[row + border + 1] - 1

                draw.rectangle(
                    (x1, y1, x2, y2),
                    fill=0
                )

    return bitmap
