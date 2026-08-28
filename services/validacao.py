from __future__ import annotations

from .texto import clean


def validate_settings(body: dict) -> dict[str, str]:
    try:
        width = float(str(body.get("largura_mm", "")).replace(",", "."))
        height = float(str(body.get("comprimento_mm", "")).replace(",", "."))
        dpi = int(body.get("dpi", 203))
    except ValueError as exc:
        raise ValueError("Dimensões ou DPI inválidos.") from exc
    if not 20 <= width <= 300 or not 20 <= height <= 300:
        raise ValueError("Largura e comprimento devem estar entre 20 e 300 mm.")
    if dpi not in (203, 300, 600):
        raise ValueError("Selecione um DPI válido.")
    branch = clean(body.get("filial"))
    if not branch or len(branch) > 10:
        raise ValueError("Informe uma filial com até 10 caracteres.")
    return {
        "largura_mm": f"{width:g}", "comprimento_mm": f"{height:g}",
        "dpi": str(dpi), "impressora": clean(body.get("impressora")),
        "prefixo_contador": clean(body.get("prefixo_contador")) or "TB",
        "filial": branch,
    }
