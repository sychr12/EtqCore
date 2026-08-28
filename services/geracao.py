from __future__ import annotations

from contextlib import closing

from models.database import db
from models import configuracao as config_model
from models import etiqueta as etiqueta_model

from .contador import identifier_for_counter
from .impressao import raw_print
from .qrcode_service import qr_payload
from .zpl import make_zpl


def gerar_lote(body: dict, destino: str, quantidade_etiquetas: int) -> dict:
    """Reserva o lote de contadores, grava no banco, opcionalmente imprime, e
    devolve um resumo pronto para virar JSON de resposta."""
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        cfg = config_model.obter_todas(con)
        first_counter = int(cfg["proximo_contador"])
        itens = []
        for counter in range(first_counter, first_counter + quantidade_etiquetas):
            identifier = identifier_for_counter(counter, cfg["prefixo_contador"])
            qr = qr_payload(body, identifier, cfg["filial"])
            zpl = make_zpl(body, counter, identifier, qr, cfg)
            itens.append({"contador": counter, "identificador": identifier, "qr": qr, "zpl": zpl})
        labels = etiqueta_model.inserir_lote(con, itens, destino, body)
        config_model.atualizar_proximo_contador(con, first_counter + quantidade_etiquetas)
        con.commit()

    combined_zpl = "\n".join(label["zpl"] for label in labels)
    error = None
    if destino == "imprimir":
        try:
            raw_print(cfg["impressora"], combined_zpl)
        except Exception as exc:
            error = str(exc)

    etiqueta_model.marcar_resultado(labels, sucesso=error is None, erro=error)

    return {
        "labels": labels,
        "combined_zpl": combined_zpl,
        "error": error,
        "first_identifier": labels[0]["identificador"],
        "last_identifier": labels[-1]["identificador"],
    }
