"""Monta o conteúdo rastreável do QR e cria sua imagem para a prévia."""

from __future__ import annotations

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from PIL import Image, ImageDraw

from .texto import clean
from .texto import quantity_x1000


def qr_payload(data: dict, identifier: str, branch: str = "04") -> str:
    """Organiza os campos no formato esperado pelo leitor da produção."""
    description = clean(data.get("descricao"))
    measurements = clean(data.get("medidas"))
    # As medidas fazem parte de (D), sem repetir as já escritas na descrição.
    if measurements and measurements.casefold() not in description.casefold():
        description = " ".join(part for part in (description, measurements) if part)
    return (
        f"(E){clean(branch)}(T){clean(data.get('tipo'))}(P){clean(data.get('produto_codigo'))}"
        f"(D){description}(S){clean(data.get('lote_controle'))}"
        f"(Q){quantity_x1000(data.get('quantidade'))}(Y){clean(data.get('dpd'))}"
        f"(I){identifier}(U){clean(data.get('unidade'))}(L){clean(data.get('lote_base'))}"
    )


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
    mantendo apenas 1 módulo de margem branca.
    """

    widget = QrCodeWidget(
        text,
        barLevel="L",
    )

    widget.qr.make()

    modules = widget.qr.modules

    # Margem pequena de apenas 1 módulo
    border = 1

    module_count = len(modules)
    count = module_count + (border * 2)

    if size < count * 2:
        raise ValueError(
            "O QR não cabe com boa definição. "
            "Aumente as dimensões da etiqueta."
        )

    # Calcula os limites para ocupar exatamente o tamanho disponível
    edges = [
        round(index * size / count)
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
