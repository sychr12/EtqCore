"""Monta o conteúdo rastreável do QR e cria sua imagem para a prévia."""

from __future__ import annotations

from PIL import Image, ImageDraw
from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

from .texto import clean, quantity_x1000


QR_BORDER = 1
QR_ERROR_LEVEL = "L"


def qr_payload(data: dict, identifier: str, branch: str = "04") -> str:
    """Organiza os campos no formato esperado pelo leitor da produção."""
    return (
        f"(E){clean(branch)}"
        f"(T){clean(data.get('tipo'))}"
        f"(P){clean(data.get('produto_codigo'))}"
        f"(D){clean(data.get('descricao'))}"
        f"(S){clean(data.get('lote_controle'))}"
        f"(Q){quantity_x1000(data.get('quantidade'))}"
        f"(Y){clean(data.get('dpd'))}"
        f"(I){clean(identifier)}"
        f"(U){clean(data.get('unidade'))}"
        f"(L){clean(data.get('lote_base'))}"
    )


def render_svg(text: str, size: int = 360) -> str:
    """Cria a prévia vetorial do QR com apenas 1 módulo de margem."""
    if not text:
        raise ValueError("O conteúdo do QR não pode estar vazio.")

    if size <= 0:
        raise ValueError("O tamanho do QR deve ser maior que zero.")

    widget = QrCodeWidget(
        text,
        barLevel=QR_ERROR_LEVEL,
        barBorder=QR_BORDER,
    )

    x1, y1, x2, y2 = widget.getBounds()
    width = x2 - x1
    height = y2 - y1

    scale = min(size / width, size / height)

    drawing = Drawing(size, size)

    # Centraliza o QR dentro da área sem distorcer.
    offset_x = (size - (width * scale)) / 2
    offset_y = (size - (height * scale)) / 2

    widget.transform = [
        scale,
        0,
        0,
        scale,
        offset_x - (x1 * scale),
        offset_y - (y1 * scale),
    ]

    drawing.add(widget)

    return renderSVG.drawToString(drawing)


def render_bitmap(text: str, size: int) -> Image.Image:
    """
    Cria o QR em bitmap ocupando praticamente toda a área disponível,
    mantendo apenas 1 módulo de margem branca.
    """
    if not text:
        raise ValueError("O conteúdo do QR não pode estar vazio.")

    if size <= 0:
        raise ValueError("O tamanho do QR deve ser maior que zero.")

    widget = QrCodeWidget(
        text,
        barLevel=QR_ERROR_LEVEL,
        barBorder=0,
    )

    # Força a criação da matriz do QR.
    widget.qr.make()

    modules = widget.qr.modules
    module_count = len(modules)

    if module_count == 0:
        raise ValueError("Não foi possível gerar a matriz do QR.")

    count = module_count + (QR_BORDER * 2)

    # Mantém no mínimo 2 pixels por módulo para evitar perda de definição.
    if size < count * 2:
        raise ValueError(
            "O QR não cabe com boa definição no tamanho informado. "
            "Aumente a área do QR ou reduza a quantidade de dados."
        )

    # Distribui os módulos por toda a área disponível.
    # Assim não sobra margem extra além do QR_BORDER definido.
    edges = [
        round(index * size / count)
        for index in range(count + 1)
    ]

    bitmap = Image.new("1", (size, size), 1)
    draw = ImageDraw.Draw(bitmap)

    for row, cells in enumerate(modules):
        for col, dark in enumerate(cells):
            if not dark:
                continue

            x1 = edges[col + QR_BORDER]
            y1 = edges[row + QR_BORDER]
            x2 = edges[col + QR_BORDER + 1] - 1
            y2 = edges[row + QR_BORDER + 1] - 1

            draw.rectangle(
                (x1, y1, x2, y2),
                fill=0,
            )

    return bitmap
