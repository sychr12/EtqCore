from __future__ import annotations

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing

from .texto import clean
from .texto import quantity_x1000


def qr_payload(data: dict, identifier: str, branch: str = "04") -> str:
    return (
        f"(E){clean(branch)}(T){clean(data.get('tipo'))}(P){clean(data.get('produto_codigo'))}"
        f"(D){clean(data.get('descricao'))}(S){clean(data.get('lote_controle'))}"
        f"(Q){quantity_x1000(data.get('quantidade'))}(Y){clean(data.get('dpd'))}"
        f"(I){identifier}(U){clean(data.get('unidade'))}(L){clean(data.get('lote_base'))}"
    )


def render_svg(text: str, size: int = 360) -> str:
    widget = QrCodeWidget(text)
    bounds = widget.getBounds()
    drawing = Drawing(
        size,
        size,
        transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0],
    )
    drawing.add(widget)
    return renderSVG.drawToString(drawing)