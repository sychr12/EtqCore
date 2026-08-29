from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.graphics.barcode.qr import QrCodeWidget

from .texto import dots, zpl_text, display_date, display_month_year

# ---------------------------------------------------------------------------
# Este arquivo desenha a etiqueta em ZPL reproduzindo, com comandos gráficos
# (^GB para linhas/caixas, ^FO/^FD/^FB para texto), o mesmo layout mostrado
# na pré-visualização web (index.html/style.css): moldura preta, QR à
# esquerda, coluna preta com TIPO/LOTE, tabela 2x2 com LOTE DE FABRICAÇÃO,
# DATA/VAL, QUANTIDADE e OPERADOR, título com a descrição, linha com COD /
# COD PROD, linha com MEDIDAS + logo, e a faixa preta vertical com o nome
# do cliente na lateral direita.
# ---------------------------------------------------------------------------


def _logo_gfa_data(target_w: int) -> tuple[int, int, int, str] | tuple[None, None, None, None]:
    """Converte a logo local em dados monocromáticos ^GFA, redimensionada
    para caber em `target_w` dots de largura. Retorna (largura, altura,
    bytes_por_linha, dados_hex)."""
    logo_path = Path(__file__).resolve().parent.parent / "logo" / "logo.png"
    if not logo_path.exists() or target_w < 4:
        return None, None, None, None

    img = Image.open(logo_path).convert("L")
    target_w = max(4, int(target_w))
    target_h = max(1, int(img.height * target_w / img.width))
    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    img = img.point(lambda px: 0 if px < 180 else 255, mode="1")

    rows: list[str] = []
    for y in range(img.height):
        byte = 0
        bits = 0
        row = []
        for x in range(img.width):
            pixel = 1 if img.getpixel((x, y)) == 0 else 0
            if pixel:
                byte |= 1 << (7 - bits)
            bits += 1
            if bits == 8:
                row.append(f"{byte:02X}")
                byte = 0
                bits = 0
        if bits:
            row.append(f"{(byte << (8 - bits)):02X}")
        rows.append("".join(row))

    bytes_per_row = len(rows[0]) // 2
    data = "".join(rows)
    return target_w, img.height, bytes_per_row, data


def _fit_font(text: str, max_width: int, max_height: int, max_font: int, min_font: int) -> int:
    """Escolhe o maior tamanho de fonte (em dots) que faz `text` caber, em
    uma única linha, dentro de max_width x max_height."""
    min_font = max(10, min_font)
    max_font = max(min_font, max_font)
    if not text:
        return max_font
    for font_size in range(max_font, min_font - 1, -1):
        estimated_width = len(text) * font_size * 0.61
        if estimated_width <= max_width and font_size <= max_height:
            return font_size
    return min_font


class _Zpl:
    """Pequeno acumulador de comandos ZPL para deixar o layout abaixo mais legível."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def raw(self, cmd: str) -> None:
        self.lines.append(cmd)

    def box_border(self, x: int, y: int, w: int, h: int, thickness: int) -> None:
        """Retângulo apenas com borda (sem preenchimento)."""
        self.lines.append(f"^FO{x},{y}^GB{w},{h},{thickness},B,0^FS")

    def box_filled(self, x: int, y: int, w: int, h: int) -> None:
        """Retângulo preenchido de preto."""
        thickness = max(1, min(w, h))
        self.lines.append(f"^FO{x},{y}^GB{w},{h},{thickness},B,0^FS")

    def line_h(self, x: int, y: int, w: int, thickness: int, color: str = "B") -> None:
        self.lines.append(f"^FO{x},{y}^GB{w},{thickness},{thickness},{color},0^FS")

    def line_v(self, x: int, y: int, h: int, thickness: int, color: str = "B") -> None:
        self.lines.append(f"^FO{x},{y}^GB{thickness},{h},{thickness},{color},0^FS")

    def text(
        self,
        x: int, y: int, w: int, h: int,
        text: str, max_font: int, min_font: int,
        align: str = "L", reverse: bool = False,
    ) -> None:
        """Escreve `text` em uma linha, centralizado verticalmente dentro
        da caixa (x,y,w,h), com a fonte encolhendo até caber."""
        font = _fit_font(text, w, h, max_font, min_font)
        ty = y + max(0, (h - font) // 2)
        reverse_cmd = "^FR" if reverse else ""
        self.lines.append(
            f"^FO{x},{ty}{reverse_cmd}^A0N,{font},{font}^FB{max(1, w)},1,0,{align},0^FD{zpl_text(text)}^FS"
        )

    def render(self) -> str:
        return "\n".join(self.lines)


def _stat_cell(
    z: _Zpl,
    x: int,
    y: int,
    w: int,
    h: int,
    pad: int,
    label: str,
    value: str,
    value_align: str = "L",
    label_font: int = 18,
    value_font: int = 38,
) -> None:
    """Célula com margem de segurança e fonte ajustada à largura/altura."""
    w = max(1, int(w))
    h = max(1, int(h))
    pad = max(6, int(pad))

    inner_w = max(1, w - 2 * pad)
    label_h = max(16, int(h * 0.31))
    value_y = y + label_h
    value_h = max(12, h - label_h - pad // 2)

    z.text(
        x + pad,
        y + pad // 2,
        inner_w,
        label_h,
        label,
        max_font=min(label_font, label_h - 2),
        min_font=10,
        align="L",
    )

    z.text(
        x + pad,
        value_y,
        inner_w,
        value_h,
        value,
        max_font=min(value_font, value_h - 2),
        min_font=12,
        align=value_align,
    )


def _inline_pair(
    z: _Zpl,
    x: int,
    y: int,
    w: int,
    h: int,
    label: str,
    value: str,
    label_ratio: float = 0.34,
    value_align: str = "L",
    value_font: int = 34,
) -> None:
    """Rótulo + valor com área interna protegida contra as bordas."""
    w = max(1, int(w))
    h = max(1, int(h))

    gap = max(5, int(w * 0.014))
    label_w = max(1, int(w * label_ratio))
    value_x = x + label_w + gap
    value_w = max(1, w - label_w - gap)

    z.text(
        x,
        y,
        label_w,
        h,
        label,
        max_font=min(h, 22),
        min_font=10,
        align="L",
    )

    z.text(
        value_x,
        y,
        value_w,
        h,
        value,
        max_font=min(h, value_font),
        min_font=12,
        align=value_align,
    )

def make_zpl(data: dict, counter: int, identifier: str, qr: str, cfg: dict[str, str]) -> str:
    width_mm = float(cfg["largura_mm"])
    height_mm = float(cfg["comprimento_mm"])
    dpi = int(cfg["dpi"])
    W = dots(width_mm, dpi)
    H = dots(height_mm, dpi)

    def mmw(pct: float) -> int:
        return dots(width_mm * pct, dpi)

    def mmh(pct: float) -> int:
        return dots(height_mm * pct, dpi)

    # Margem interna de segurança: aproximadamente 2,5 mm.
    # Isso evita que textos encostem na moldura ou nas linhas.
    pad = max(18, mmw(0.025))

    # Moldura externa (equivalente ao .frame do CSS: inset 3cqh/2.4cqw, borda ~0.55cqw)
    # Margem da etiqueta até a moldura: aproximadamente 3 mm.
    outer_x = mmw(0.03)
    outer_y = mmh(0.03)
    border = max(4, mmw(0.005))
    fx0, fy0 = outer_x, outer_y
    fx1, fy1 = W - outer_x, H - outer_y
    fw, fh = fx1 - fx0, fy1 - fy0

    # Faixa preta lateral com o nome do cliente (.brandBand: 9cqw)
    brand_w = mmw(0.09)
    cx0, cy0 = fx0 + border, fy0 + border
    cx1 = fx1 - border - brand_w
    cy1 = fy1 - border
    cw, ch = cx1 - cx0, cy1 - cy0
    brand_x0 = cx1

    # Linhas do conteúdo (equivalentes a topRow 34cqh / titleText / codRow / bottomRow)
    top_h = mmh(0.34)
    title_h = mmh(0.14)
    cod_h = mmh(0.12)
    bottom_h = max(mmh(0.10), ch - top_h - title_h - cod_h)

    z = _Zpl()
    z.raw("^XA")
    z.raw("^CI27")
    z.raw(f"^PW{W}")
    z.raw(f"^LL{H}")
    z.raw("^LH0,0")
    z.raw("^PON")

    # Moldura externa
    z.box_border(fx0, fy0, fw, fh, border)

    # Faixa preta lateral (cliente/marca), texto girado lendo de cima para baixo
    z.box_filled(brand_x0, cy0, brand_w, ch)
    cliente = zpl_text(data.get("cliente") or "")
    if cliente:
        brand_font = _fit_font(cliente, ch, brand_w - 4, max_font=min(mmw(0.05), brand_w - 4), min_font=14)
        text_len = len(cliente) * brand_font * 0.62
        by = cy0 + max(0, int((ch - text_len) / 2))
        bx = brand_x0 + max(0, int((brand_w - brand_font) / 2))
        z.raw(f"^FO{bx},{by}^FR^A0R,{brand_font},{brand_font}^FD{cliente}^FS")

    # --- Linha superior: QR + coluna preta (TIPO/LOTE) + tabela 2x2 -----------------
    qr_w = min(top_h, int(cw * 0.4))
    badge_w = mmw(0.15)
    table_x0 = cx0 + qr_w + badge_w
    table_w = cw - qr_w - badge_w

    # QR code nativo da Zebra, centralizado dentro do quadrado qr_w x top_h,
    # com folga (pad) em todos os lados para nunca encostar/invadir a coluna
    # preta ao lado nem a moldura acima.
    qr_widget = QrCodeWidget(qr)
    qr_widget.getBounds()
    module_count = qr_widget.qr.moduleCount
    qr_area = max(10, min(qr_w, top_h) - pad)
    qr_mag = max(2, min(20, qr_area // max(1, module_count + 8)))
    qr_size = qr_mag * (module_count + 8)
    qr_x = cx0 + max(0, (qr_w - qr_size) // 2)
    qr_y = cy0 + max(0, (top_h - qr_size) // 2)
    z.raw(f"^FO{qr_x},{qr_y}^BQN,2,{qr_mag}^FDLA,{qr}^FS")

    # Coluna preta com TIPO (ex.: "2") em cima e LOTE_CONTROLE (ex.: "BC") embaixo
    badge_x0 = cx0 + qr_w
    z.box_filled(badge_x0, cy0, badge_w, top_h)
    half = top_h // 2
    z.line_h(badge_x0, cy0 + half, badge_w, max(2, mmw(0.0028)), color="W")
    tipo = str(data.get("tipo") or "")
    lote_controle = str(data.get("lote_controle") or "")
    z.text(badge_x0, cy0, badge_w, half, tipo, max_font=min(half, mmw(0.05)), min_font=16, align="C", reverse=True)
    z.text(badge_x0 + 0, cy0 + half, badge_w, top_h - half, lote_controle,
           max_font=min(top_h - half, mmw(0.06)), min_font=16, align="C", reverse=True)

    # Tabela 2x2: LOTE DE FABRICAÇÃO | DATA/VAL // QUANTIDADE | OPERADOR
    col_w = table_w // 2
    row_h = top_h // 2
    grid_thickness = max(2, mmw(0.0028))
    z.line_v(table_x0 + col_w, cy0, top_h, grid_thickness)
    z.line_h(table_x0, cy0 + row_h, table_w, grid_thickness)

    _stat_cell(z, table_x0, cy0, col_w, row_h, pad,
               "LOTE DE FABRICAÇÃO", str(data.get("lote_base") or ""))

    date_col_x = table_x0 + col_w
    sub_h = row_h // 2
    _inline_pair(z, date_col_x + pad, cy0 + pad // 2, col_w - 2 * pad, sub_h - pad // 2,
                 "DATA ", display_date(data.get("fabricacao")))
    z.line_h(date_col_x + pad, cy0 + sub_h, col_w - 2 * pad, max(1, mmw(0.0018)))
    _inline_pair(z, date_col_x + pad, cy0 + sub_h, col_w - 2 * pad, sub_h - pad // 2,
                 "VAL: ", display_month_year(data.get("validade")))

    qty_text = f"{str(data.get('quantidade') or '')} {str(data.get('unidade') or '')}".strip()
    _stat_cell(z, table_x0, cy0 + row_h, col_w, top_h - row_h, pad, "QUANTIDADE", qty_text)
    _stat_cell(z, date_col_x, cy0 + row_h, col_w, top_h - row_h, pad,
               "OPERADOR", str(data.get("operador") or ""))

    # Separador entre a linha superior e o título
    z.line_h(cx0, cy0 + top_h, cw, border)

    # --- Título (descrição do produto) -----------------------------------------------
    title_y = cy0 + top_h
    z.text(cx0 + pad, title_y, cw - 2 * pad, title_h, str(data.get("descricao") or ""),
           max_font=min(mmw(0.066), mmh(0.125)), min_font=20, align="L")
    z.line_h(cx0, title_y + title_h, cw, border)

    # --- Linha COD / COD PROD -----------------------------------------------------
    cod_y = title_y + title_h
    cod_main_w = min(mmw(0.42), int(cw * 0.55))
    _inline_pair(z, cx0 + pad, cod_y, cod_main_w - pad, cod_h,
                 "COD: ", str(data.get("produto_codigo") or ""), label_ratio=0.30)
    z.line_v(cx0 + cod_main_w, cod_y, cod_h, border)
    _stat_cell(z, cx0 + cod_main_w, cod_y, cw - cod_main_w, cod_h, pad,
               "COD PROD:", str(data.get("cod_prod") or ""))
    z.line_h(cx0, cod_y + cod_h, cw, border)

    # --- Linha inferior: MEDIDAS + logo -----------------------------------------------
    bottom_y = cod_y + cod_h
    logo_w = mmw(0.34)
    medidas_w = cw - logo_w
    _inline_pair(z, cx0 + pad, bottom_y, medidas_w - 2 * pad, bottom_h,
                 "MEDIDAS: ", str(data.get("medidas") or ""), label_ratio=0.36)
    z.line_v(cx0 + medidas_w, bottom_y, bottom_h, border)

    logo_x0 = cx0 + medidas_w
    logo_target_w = max(10, logo_w - 2 * max(8, pad))
    logo_w_px, logo_h_px, logo_bpr, logo_data = _logo_gfa_data(logo_target_w)
    if logo_w_px and logo_h_px and logo_h_px > bottom_h - 2 * pad:
        scale = (bottom_h - 2 * pad) / logo_h_px
        logo_w_px, logo_h_px, logo_bpr, logo_data = _logo_gfa_data(max(10, int(logo_target_w * scale)))
    if logo_w_px and logo_data:
        logo_x = logo_x0 + max(0, (logo_w - logo_w_px) // 2)
        logo_y = bottom_y + max(0, (bottom_h - logo_h_px) // 2)
        total_bytes = logo_bpr * logo_h_px
        z.raw(f"^FO{logo_x},{logo_y}^GFA,{total_bytes},{total_bytes},{logo_bpr},{logo_data}^FS")

    z.raw("^XZ")
    return z.render()