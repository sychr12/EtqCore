from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def clean(value: object) -> str:
    return str(value or "").strip().replace("\r\n", " ").replace("\n", " ").replace("^", " ").replace("~", " ")


def zpl_text(value: object) -> str:
    # O ZPL é enviado em UTF-8 (^CI27, ver services/zpl.py e services/impressao.py),
    # então não há necessidade de restringir a um charset como cp850 aqui —
    # isso só arriscava trocar acentos válidos por "?". `clean` já remove
    # quebras de linha e os caracteres ^ e ~, que têm significado especial no ZPL.
    return clean(value)


def quantity_x1000(raw: object) -> str:
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
    if result != result.to_integral_value():
        raise ValueError("A quantidade × 1000 precisa resultar em um número inteiro.")
    return str(int(result))


def display_date(value: object) -> str:
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
    return max(1, round(mm * dpi / 25.4))