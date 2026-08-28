from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def clean(value: object) -> str:
    return str(value or "").strip().replace("\r\n", " ").replace("\n", " ").replace("^", " ").replace("~", " ")


def zpl_text(value: object) -> str:
    return clean(value).encode("cp850", errors="replace").decode("cp850")


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


def dots(mm: float, dpi: int) -> int:
    return max(1, round(mm * dpi / 25.4))
