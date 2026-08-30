"""Limpa textos, formata datas e converte milímetros para dots da Zebra."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import unicodedata


def clean(value: object) -> str:
    """Normaliza UTF-8 e remove caracteres que poderiam quebrar o ZPL."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFC", text)
    text = "".join(" " if unicodedata.category(char).startswith("C") else char for char in text)
    return text.strip().replace("^", " ").replace("~", " ")


def zpl_text(value: object) -> str:
    # O ZPL é enviado em UTF-8 (^CI28, ver services/zpl.py e services/impressao.py),
    # então não há necessidade de restringir a um charset como cp850 aqui —
    # isso só arriscava trocar acentos válidos por "?". `clean` já remove
    # quebras de linha e os caracteres ^ e ~, que têm significado especial no ZPL.
    return clean(value)


def quantity_x1000(raw: object) -> str:
    """Converte a quantidade para o valor inteiro exigido dentro do QR."""
    value = clean(raw).replace(" ", "")
    if not value:
        raise ValueError("Informe a quantidade.")
    # Aceita 95,5; 95.5; 1.234,5; e inteiros.
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    try:
        result = Decimal(value) * Decimal(1000)
    except InvalidOperation as exc:
        raise ValueError("Quantidade inválida.") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("A quantidade deve ser um número maior que zero.")
    if result != result.to_integral_value():
        raise ValueError("A quantidade × 1000 precisa resultar em um número inteiro.")
    return str(int(result))


def display_date(value: object) -> str:
    """Mostra uma data como dia/mês/ano; mantém o original se for inválida."""
    raw = clean(value)
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return raw


MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def display_month_year(value: object) -> str:
    """Formata AAAA-MM-DD como MES/AAAA (ex.: 2029-01-31 -> JAN/2029),
    igual ao campo VAL da pré-visualização web."""
    raw = clean(value)
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return raw
    return f"{MESES[parsed.month - 1]}/{parsed.year}"


def dots(mm: float, dpi: int) -> int:
    """Converte uma medida física em pontos que a cabeça térmica imprime."""
    # A cabeça de 203 dpi da ZD220 é endereçada nominalmente como 8 dots/mm.
    # Usar 203/25,4 produziria 799 dots para 100 mm, divergindo do firmware
    # e da especificação física de 800 x 480 dots.
    density = 8 if dpi == 203 else dpi / 25.4
    return max(1, round(mm * density))
