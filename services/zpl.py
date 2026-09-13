"""Desenha a etiqueta em comandos ZPL nas medidas exatas da Zebra ZD220."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from .texto import dots, zpl_text, display_date
from .qrcode_service import render_bitmap

# ---------------------------------------------------------------------------
# Este arquivo desenha a etiqueta em ZPL reproduzindo, com comandos gráficos
# (^GB para linhas/caixas, ^FO/^FD/^FB para texto), o mesmo layout mostrado
# na pré-visualização web (index.html/style.css): moldura preta, QR à
# esquerda, tabela 2x2 com LOTE DE FABRICAÇÃO, DATA/VAL, QUANTIDADE e
# OPERADOR, título com a descrição, linha com OC /
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

    with Image.open(logo_path) as source:
        img = source.convert("L")
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
            # Os pixels já estão nos bits altos; deslocar novamente corrompe
            # a última coluna de bytes quando a largura não é múltipla de 8.
            row.append(f"{byte:02X}")
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

    def bitmap(self, x: int, y: int, image: Image.Image) -> None:
        packed = ImageOps.invert(image.convert("L")).convert("1").tobytes()
        bytes_per_row = (image.width + 7) // 8
        self.raw(f"^FO{x},{y}^GFA,{len(packed)},{len(packed)},{bytes_per_row},{packed.hex().upper()}^FS")

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
        width_ratio: float = 1.0,
        bold: bool = False,
    ) -> None:
        """Escreve `text` em uma linha, centralizado verticalmente dentro
        da caixa (x,y,w,h), com a fonte encolhendo até caber."""
        stroke = 2 if bold and not reverse else 0
        inner_w = max(1, w - stroke)
        font = _fit_font(text, int(inner_w / width_ratio), h, max_font, min_font)
        font_width = max(1, int(font * width_ratio))
        ty = y + max(0, (h - font) // 2)
        reverse_cmd = "^FR" if reverse else ""
        # Reforça somente os textos solicitados, sem alterar a tonalidade
        # da impressora ou os módulos do QR. Reserva a largura da sobreposição.
        for offset in range(stroke + 1):
            self.lines.append(
                f"^FO{x + offset},{ty}{reverse_cmd}^A0N,{font},{font_width}^FB{inner_w},1,0,{align},0^FD{zpl_text(text)}^FS"
            )

    def text_wrapped(
        self, x: int, y: int, w: int, h: int, text: str,
        max_font: int, min_font: int, align: str = "C",
    ) -> None:
        """Escreve em uma ou duas linhas, quebrando somente quando necessário."""
        one_line_font = _fit_font(text, w, h, max_font, min_font)
        if len(text) * one_line_font * 0.61 <= w:
            self.text(x, y, w, h, text, max_font, min_font, align=align)
            return
        font = _fit_font(text, w * 2, max(12, h // 2), max_font, min_font)
        line_gap = 2
        block_h = min(h, font * 2 + line_gap)
        ty = y + max(0, (h - block_h) // 2)
        self.lines.append(
            f"^FO{x},{ty}^A0N,{font},{font}^FB{max(1, w)},2,{line_gap},{align},0^FD{zpl_text(text)}^FS"
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
    label_align: str = "L",
    label_font: int = 18,
    value_font: int = 38,
    label_offset: int = 0,
    value_offset: int = 0,
    secondary_value: str = "",
    secondary_font: int = 24,
    primary_ratio: float = 0.62,
    wrap_value: bool = False,
    label_ratio: float = 0.31,
    bold: bool = False,
) -> None:
    """Célula com margem de segurança e fonte ajustada à largura/altura."""
    w = max(1, int(w))
    h = max(1, int(h))
    pad = max(6, int(pad))

    inner_w = max(1, w - 2 * pad)
    label_h = max(16, int(h * label_ratio))
    label_offset = max(0, int(label_offset))
    value_offset = max(0, int(value_offset))
    label_y = y + pad // 2 + label_offset
    value_y = max(y + label_h + value_offset, label_y + label_h + pad // 6 - 2)
    # O deslocamento consome espaço: mantém a margem inferior mesmo quando
    # um valor é baixado para ficar alinhado aos campos vizinhos.
    value_h = max(12, y + h - max(3, pad // 4) - value_y)

    z.text(
        x + pad,
        label_y,
        inner_w,
        label_h,
        label,
        max_font=min(label_font, label_h - 2),
        min_font=10,
        align=label_align,
        bold=bold,
    )

    if secondary_value:
        primary_h = max(12, int(value_h * primary_ratio))
        secondary_h = max(10, value_h - primary_h)
        z.text(
            x + pad, value_y, inner_w, primary_h, value,
            max_font=min(value_font, primary_h - 2), min_font=12,
            align=value_align,
            bold=bold,
        )
        z.text(
            x + pad, value_y + primary_h, inner_w, secondary_h,
            secondary_value,
            max_font=min(secondary_font, secondary_h - 1), min_font=10,
            align=value_align,
        )
    elif wrap_value:
        z.text_wrapped(
            x + pad, value_y, inner_w, value_h, value,
            max_font=min(value_font, value_h - 2), min_font=12,
            align=value_align,
        )
    else:
        z.text(
            x + pad,
            value_y,
            inner_w,
            value_h,
            value,
            max_font=min(value_font, value_h - 2),
            min_font=12,
            align=value_align,
            bold=bold,
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
    label_font: int = 22,
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
        max_font=min(h, label_font),
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
    if dpi != 203:
        raise ValueError("A Zebra ZD220 requer resolução de 203 dpi.")
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
    # Margens da referência técnica: 24 dots nas laterais e 28 dots até
    # o conteúdo no topo/rodapé (24 de margem + 4 da borda em 203 dpi).
    outer_x = mmw(0.03)
    outer_y = mmh(0.05)
    border = max(4, mmw(0.005))
    fx0, fy0 = outer_x, outer_y
    fx1, fy1 = W - outer_x, H - outer_y
    fw, fh = fx1 - fx0, fy1 - fy0

    # A faixa preta lateral só ocupa espaço quando Marca/Cliente foi informado.
    cliente = zpl_text(data.get("cliente") or "")
    brand_w = mmw(0.09) if cliente else 0
    cx0, cy0 = fx0 + border, fy0 + border
    cx1 = fx1 - border - brand_w
    cy1 = fy1 - border
    cw, ch = cx1 - cx0, cy1 - cy0
    brand_x0 = cx1

    # Distribuição dos 424 dots úteis. O topo maior permite usar módulo 4
    # no QR da ZD220, mantendo as demais faixas legíveis e dentro da moldura.
    height_scale = H / 480
    top_h = round(204 * height_scale)
    title_h = round(60 * height_scale)
    cod_h = round(76 * height_scale)
    bottom_h = ch - top_h - title_h - cod_h
    if bottom_h < 1:
        raise ValueError("A altura configurada não comporta o layout da etiqueta.")

    z = _Zpl()
    z.raw("^XA")
    # ^CI28 é Unicode/UTF-8. ^CI27 é Windows-1252 e corrompia os bytes UTF-8.
    z.raw("^CI28")
    # Perfil da Zebra ZD220: mídia com detecção automática, origem zerada e
    # parâmetros explícitos para o driver não reaproveitar valores de outro trabalho.
    z.raw("^MNA")
    z.raw(f"^PR{int(cfg.get('velocidade_ips', '3'))}")
    z.raw(f"~SD{int(cfg.get('tonalidade', '10'))}")
    z.raw(f"^PW{W}")
    z.raw(f"^LL{H}")
    z.raw("^LH0,0")
    density = 8 if dpi == 203 else dpi / 25.4
    offset_x = round(float(cfg.get("deslocamento_x_mm", "0")) * density)
    offset_y = round(float(cfg.get("deslocamento_y_mm", "0")) * density)
    z.raw(f"^LS{offset_x}")
    z.raw(f"^LT{offset_y}")
    z.raw("^PON")

    # Moldura externa
    z.box_border(fx0, fy0, fw, fh, border)

    # Faixa preta lateral: leitura de baixo para cima, como na prévia.
    if cliente:
        z.box_filled(brand_x0, cy0, brand_w, ch)
        brand_font = _fit_font(cliente, ch, brand_w - 4, max_font=min(mmw(0.05), brand_w - 4), min_font=14)
        text_len = len(cliente) * brand_font * 0.62
        by = cy0 + max(0, int((ch - text_len) / 2))
        bx = brand_x0 + max(0, int((brand_w - brand_font) / 2))
        z.raw(f"^FO{bx},{by}^FR^A0B,{brand_font},{brand_font}^FD{cliente}^FS")

    # --- Linha superior: QR + tabela 2x2 --------------------------------------------
    # Tipo e lote de controle pertencem somente ao conteúdo do QR Code.
    qr_w = min(top_h, int(cw * 0.4))
    table_x0 = cx0 + qr_w
    table_w = cw - qr_w

    # O QR ocupa o quadrado de 202 dots aprovado para a etiqueta de 100 mm.
    # A matriz é gerada diretamente nesse tamanho, sem recorte ou reescala
    # posterior que possa deformar os módulos.
    qr_area = min(qr_w, top_h)
    qr_size = max(1, qr_area - 2)
    qr_x = cx0
    qr_y = cy0

    qr_img = render_bitmap(qr, qr_size).convert("L")

    z.raw("^FXQR^FS")
    z.bitmap(qr_x, qr_y, qr_img)

    # Tabela 2x2: LOTE DE FABRICAÇÃO | DATA/VAL // QUANTIDADE | OPERADOR
    col_w = table_w // 2
    row_h = top_h // 2
    grid_thickness = max(3, mmw(0.0028))
    z.line_v(table_x0, cy0, top_h, grid_thickness)
    z.line_v(table_x0 + col_w, cy0, top_h, grid_thickness)
    z.line_h(table_x0, cy0 + row_h, table_w, grid_thickness)

    lot_top = str(data.get("lote_base") or "")
    _stat_cell(z, table_x0, cy0, col_w, row_h, pad,
               "LOTE DE FABRICAÇÃO", lot_top,
               label_font=20, value_font=42,
               label_align="C", value_align="C")

    date_col_x = table_x0 + col_w
    sub_h = row_h // 2
    date_y_offset = max(2, sub_h // 12)
    _inline_pair(z, date_col_x + pad, cy0 + pad // 2 + date_y_offset,
                 col_w - 2 * pad, sub_h - pad // 2,
                 "DATA ", display_date(data.get("fabricacao")),
                 label_font=27, value_font=33, label_ratio=0.40)
    z.line_h(date_col_x + pad, cy0 + sub_h, col_w - 2 * pad, grid_thickness)
    _inline_pair(z, date_col_x + pad, cy0 + sub_h, col_w - 2 * pad, sub_h - pad // 2,
                 "VAL: ", display_date(data.get("validade")),
                 label_font=27, value_font=33, label_ratio=0.40)

    qty_text = str(data.get("quantidade") or "")
    qty_unit = str(data.get("unidade") or "")
    _stat_cell(z, table_x0, cy0 + row_h, col_w, top_h - row_h, pad,
               "QUANTIDADE", f"{qty_text} {qty_unit}".strip(), value_font=50, label_font=23,
               label_align="C", value_align="C")
    _stat_cell(z, date_col_x, cy0 + row_h, col_w, top_h - row_h, pad,
               "OPERADOR", str(data.get("operador") or ""), value_font=50, label_font=23,
               label_align="C", value_align="C",
               wrap_value=True)

    # Separador entre a linha superior e o título
    z.line_h(cx0, cy0 + top_h, cw, border)

    # --- Título (descrição do produto) -----------------------------------------------
    title_y = cy0 + top_h
    # Aproveita praticamente toda a altura da faixa para a descrição.
    # Mantém apenas uma pequena folga das linhas superior e inferior.
    title_gap = max(2, mmh(0.004))
    # Desce a descrição só um pouco para afastá-la da linha superior.
    title_drop = max(6, mmh(0.012))
    title_inner_y = title_y + border + title_gap + title_drop
    # Mantém altura suficiente para a fonte ficar grande mesmo com o pequeno deslocamento.
    title_inner_h = max(1, title_h - border - title_gap - title_drop - 4)
    # Descrição do produto (ex.: TUBETE ALTEBRAS):
    # usa a maior fonte possível dentro da faixa e fica centralizada.
    title_pad = max(4, mmw(0.005))
    z.text(cx0 + title_pad, title_inner_y, cw - 2 * title_pad, title_inner_h, str(data.get("descricao") or ""),
           max_font=max(1, title_inner_h - 4), min_font=min(22, title_inner_h), align="L", bold=True)
    z.line_h(cx0, title_y + title_h, cw, border)

    # --- Linha OC / COD PROD ------------------------------------------------------
    cod_y = title_y + title_h
    cod_main_w = int(cw * 0.48)
    # Recuo horizontal maior para afastar OC/COD PROD da linha vertical esquerda.
    # Não altera o tamanho da fonte.
    code_pad = max(10, mmw(0.012))
    _stat_cell(z, cx0, cod_y, cod_main_w, cod_h, code_pad,
               "OC:", str(data.get("oc") or ""),
               label_font=38, value_font=78, label_ratio=0.24,
               label_offset=4, value_offset=3, bold=True)
    z.line_v(cx0 + cod_main_w, cod_y, cod_h, border)
    _stat_cell(z, cx0 + cod_main_w, cod_y, cw - cod_main_w, cod_h, code_pad,
               "COD PROD:", str(data.get("cod_prod") or ""),
               label_font=38, value_font=78, label_ratio=0.24,
               label_offset=4, value_offset=3, bold=True)
    z.line_h(cx0, cod_y + cod_h, cw, border)

    # --- Linha inferior: MEDIDAS/OBSERVAÇÃO + logo -----------------------------------
    bottom_y = cod_y + cod_h
    observacao = str(data.get("observacao") or "").strip()
    logo_w = int(cw * (0.26 if observacao else 0.44))
    medidas_w = int(cw * 0.39) if observacao else cw - logo_w
    obs_x = cx0 + medidas_w + logo_w
    obs_w = cw - medidas_w - logo_w
    # O rodapé usa margens menores que as células grandes do topo, para
    # aproveitar sua altura sem diminuir excessivamente as medidas e a logo.
    footer_pad_x = max(6, mmw(0.01))
    footer_pad_y = max(4, mmh(0.0125))
    footer_top = bottom_y + border + footer_pad_y
    footer_bottom = bottom_y + bottom_h - footer_pad_y
    measures_label_h = max(16, int(bottom_h * 0.25))
    measures_value_y = footer_top + measures_label_h + 4
    measures_inner_w = medidas_w - border - 2 * footer_pad_x
    # Ícone simples de "tubete" à esquerda, como na referência.
    icon_w = max(10, mmw(0.016))
    icon_h = max(18, int((footer_bottom - footer_top) * 0.36))
    icon_x = cx0 + footer_pad_x
    icon_y = footer_top + max(0, (footer_bottom - footer_top - icon_h) // 2)
    icon_th = max(2, border // 2)

    # Corpo do ícone e pequena aba lateral.
    z.box_border(icon_x + 4, icon_y, icon_w, icon_h, icon_th)
    z.line_v(icon_x, icon_y + max(2, icon_h // 5),
             max(4, icon_h - 2 * max(2, icon_h // 5)), icon_th)

    measures_text_x = icon_x + icon_w + max(12, mmw(0.018))
    measures_text_w = max(1, cx0 + medidas_w - footer_pad_x - measures_text_x)

    z.text(measures_text_x, footer_top, measures_text_w, measures_label_h,
           "MEDIDAS:", max_font=24, min_font=12, bold=True)

    z.text(measures_text_x, measures_value_y, measures_text_w,
           max(12, footer_bottom - measures_value_y), str(data.get("medidas") or ""),
           max_font=42, min_font=14, width_ratio=0.62, bold=True)
    z.line_v(cx0 + medidas_w, bottom_y, bottom_h, border)
    if observacao:
        z.line_v(obs_x, bottom_y, bottom_h, border)

        # Aproxima o texto da observação do título "OBSERVAÇÃO:".
        obs_pad = max(8, pad // 2)
        # Deixa o conteúdo da observação logo abaixo do título,
        # evitando que fique centralizado muito para baixo no campo.
        # Dá uma margem maior da linha superior e aproxima o conteúdo do título.
        obs_top_margin = max(8, mmh(0.012))
        obs_label_h = max(18, int(bottom_h * 0.22))
        obs_label_y = bottom_y + border + obs_top_margin
        obs_value_y = obs_label_y + max(12, obs_label_h - 5)
        obs_bottom_margin = max(4, obs_pad // 2)

        z.text(
            obs_x + obs_pad, obs_label_y,
            max(1, obs_w - 2 * obs_pad), obs_label_h,
            "OBSERVAÇÃO:",
            max_font=18, min_font=13,
            align="L"
        )

        # Mantém o texto da observação colado ao título, sem centralizar
        # verticalmente em toda a altura restante do campo.
        obs_value_h = min(
            max(28, bottom_y + bottom_h - obs_bottom_margin - obs_value_y),
            48
        )

        z.text_wrapped(
            obs_x + obs_pad, obs_value_y,
            max(1, obs_w - 2 * obs_pad),
            obs_value_h,
            observacao,
            max_font=22, min_font=15,
            align="L"
        )
    logo_x0 = cx0 + medidas_w
    logo_target_w = max(10, logo_w - border - 2 * footer_pad_x)
    logo_target_h = max(1, footer_bottom - footer_top)
    logo_w_px, logo_h_px, logo_bpr, logo_data = _logo_gfa_data(logo_target_w)
    if logo_w_px and logo_h_px and logo_h_px > logo_target_h:
        scale = logo_target_h / logo_h_px
        logo_w_px, logo_h_px, logo_bpr, logo_data = _logo_gfa_data(max(10, int(logo_target_w * scale)))
    if logo_w_px and logo_data:
        logo_x = logo_x0 + max(0, (logo_w - logo_w_px) // 2)
        logo_y = footer_top + max(0, (logo_target_h - logo_h_px) // 2)
        total_bytes = logo_bpr * logo_h_px
        z.raw(f"^FO{logo_x},{logo_y}^GFA,{total_bytes},{total_bytes},{logo_bpr},{logo_data}^FS")

    z.raw("^XZ")
    return z.render()
