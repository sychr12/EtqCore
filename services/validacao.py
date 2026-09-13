"""Confere os dados antes de gerar QR, reservar contador ou imprimir."""

from __future__ import annotations

import math
import re

from config import REPORTS_DIR

from .texto import clean, qr_text


# Limites evitam textos enormes e trabalhos ZPL inválidos.
LABEL_LIMITS = {
    "filial": 10,
    "cliente": 80,
    "oc": 80,
    "tipo": 40,
    "produto_codigo": 80,
    "cod_prod": 80,
    "descricao": 300,
    "lote_controle": 80,
    "lote_base": 80,
    "quantidade": 40,
    "unidade": 30,
    "operador": 80,
    "medidas": 160,
    "fabricacao": 20,
    "validade": 20,
    "dpd": 160,
    "observacao": 300,
}

QR_LABEL_FIELDS = {
    "filial", "tipo", "produto_codigo", "descricao", "medidas",
    "lote_controle", "quantidade", "dpd", "unidade", "lote_base",
}

REQUIRED_LABEL_FIELDS = {
    "produto_codigo": "código do produto",
    "descricao": "descrição",
    "lote_controle": "lote de controle",
    "quantidade": "quantidade",
    "unidade": "unidade",
}


def integer_value(value: object, message: str) -> int:
    """Lê inteiros sem truncar decimais nem aceitar booleanos como números."""
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
        try:
            return int(value)
        except ValueError:
            pass
    raise ValueError(message)


def _scalar(value: object, field: str) -> object:
    if value is not None and type(value) not in (str, int, float):
        raise ValueError(f"O campo {field.replace('_', ' ')} deve conter texto ou um número.")
    return value


def validate_label(body: object) -> dict[str, str]:
    """Limpa os campos, confere obrigatórios e valida a quantidade."""
    if not isinstance(body, dict):
        raise ValueError("Envie os dados da etiqueta em formato JSON válido.")
    result = {}
    for key in LABEL_LIMITS:
        # Arquivos antigos usam a filial das configurações. Uma filial
        # explicitamente vazia, por outro lado, deve produzir o marcador (E).
        if key == "filial" and key not in body:
            continue
        try:
            result[key] = (qr_text if key in QR_LABEL_FIELDS else clean)(_scalar(body.get(key), key))
        except ValueError as exc:
            raise ValueError(f"Campo {key.replace('_', ' ')}: {exc}") from exc
    for key, label in REQUIRED_LABEL_FIELDS.items():
        if not result[key]:
            raise ValueError(f"Informe {label}.")
    for key, limit in LABEL_LIMITS.items():
        if len(result.get(key, "")) > limit:
            raise ValueError(f"O campo {key.replace('_', ' ')} aceita no máximo {limit} caracteres.")
    # Também valida a conversão usada no QR antes de reservar um contador.
    from .texto import quantity_x1000

    quantity_x1000(result["quantidade"])
    return result


def validate_settings(body: object) -> dict[str, str]:
    """Garante que as opções são compatíveis com a Zebra ZD220 de 203 DPI."""
    if not isinstance(body, dict):
        raise ValueError("Envie as configurações em formato JSON válido.")
    try:
        width = float(str(body.get("largura_mm", "")).replace(",", "."))
        height = float(str(body.get("comprimento_mm", "")).replace(",", "."))
        dpi = integer_value(body.get("dpi", 203), "DPI inválido.")
        speed = integer_value(body.get("velocidade_ips", 3), "Velocidade inválida.")
        darkness = integer_value(body.get("tonalidade", 10), "Tonalidade inválida.")
        offset_x = float(str(body.get("deslocamento_x_mm", 0)).replace(",", "."))
        offset_y = float(str(body.get("deslocamento_y_mm", 0)).replace(",", "."))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Dimensões ou DPI inválidos.") from exc
    if not math.isfinite(width) or not math.isfinite(height):
        raise ValueError("Dimensões ou DPI inválidos.")
    if not 25.4 <= width <= 104:
        raise ValueError("Na Zebra ZD220, a largura deve ficar entre 25,4 e 104 mm.")
    if not 25.4 <= height <= 991:
        raise ValueError("Na Zebra ZD220, o comprimento deve ficar entre 25,4 e 991 mm.")
    if dpi != 203:
        raise ValueError("A Zebra ZD220 trabalha em 203 dpi.")
    if speed not in (2, 3, 4):
        raise ValueError("A velocidade da ZD220 deve ser 2, 3 ou 4 ips.")
    if not 0 <= darkness <= 30:
        raise ValueError("A tonalidade deve ficar entre 0 e 30.")
    if not all(math.isfinite(value) and -10 <= value <= 10 for value in (offset_x, offset_y)):
        raise ValueError("Os deslocamentos devem ficar entre -10 e 10 mm.")
    branch = qr_text(_scalar(body.get("filial"), "filial"))
    if not branch or len(branch) > 10:
        raise ValueError("Informe uma filial com até 10 caracteres.")
    printer = clean(_scalar(body.get("impressora"), "impressora"))
    reports_folder = str(_scalar(body.get("pasta_relatorios"), "pasta_relatorios") or REPORTS_DIR).strip()
    prefix = qr_text(_scalar(body.get("prefixo_contador"), "prefixo_contador")) or "TB"
    if len(prefix) > 8:
        raise ValueError("O prefixo do contador aceita no máximo 8 caracteres.")
    if not re.fullmatch(r"[A-Za-z0-9]+", prefix):
        raise ValueError("O prefixo do contador deve conter somente letras e números.")
    if len(printer) > 260:
        raise ValueError("O nome da impressora aceita no máximo 260 caracteres.")
    if not reports_folder or len(reports_folder) > 500 or "\x00" in reports_folder:
        raise ValueError("Informe uma pasta válida para salvar os relatórios.")
    return {
        "largura_mm": f"{width:g}", "comprimento_mm": f"{height:g}",
        "dpi": str(dpi), "impressora": printer,
        "pasta_relatorios": reports_folder,
        "prefixo_contador": prefix,
        "filial": branch,
        "velocidade_ips": str(speed),
        "tonalidade": str(darkness),
        "deslocamento_x_mm": f"{offset_x:g}",
        "deslocamento_y_mm": f"{offset_y:g}",
    }
