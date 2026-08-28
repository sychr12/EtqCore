from __future__ import annotations

import json
import sqlite3

from flask import Blueprint, Response, jsonify, request, send_file

from models import configuracao as config_model
from models import etiqueta as etiqueta_model
from services.contador import identifier_for_counter, visible_counter
from services.geracao import gerar_lote
from services.qrcode_service import qr_payload, render_svg
from services.texto import quantity_x1000
from services.validacao import validate_settings

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/estado")
def state():
    cfg = config_model.obter_todas()
    last = etiqueta_model.obter_ultima()
    counter = int(cfg["proximo_contador"])
    return jsonify({
        "config": cfg,
        "proximo_identificador": identifier_for_counter(counter, cfg["prefixo_contador"]),
        "proximo_numero": visible_counter(counter),
        "ultima_etiqueta": (
            {"identificador": last["identificador"], "dados": json.loads(last["dados_json"])} if last else None
        ),
    })


@api_bp.post("/config")
def save_config():
    try:
        values = validate_settings(request.get_json(force=True))
        config_model.salvar(values)
        return jsonify({"ok": True})
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.post("/preview")
def preview():
    try:
        body = request.get_json(force=True)
        cfg = config_model.obter_todas()
        counter = int(cfg["proximo_contador"])
        identifier = identifier_for_counter(counter, cfg["prefixo_contador"])
        qr = qr_payload(body, identifier, cfg["filial"])
        return jsonify({
            "identificador": identifier,
            "numero": visible_counter(counter),
            "qr": qr,
            "quantidade_qr": quantity_x1000(body.get("quantidade")),
        })
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.post("/qr.svg")
def qr_svg():
    text = request.get_data(as_text=True)
    svg = render_svg(text)
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})


@api_bp.post("/gerar")
def generate():
    body = request.get_json(force=True)
    destino = body.pop("destino", "download")
    try:
        try:
            quantidade = int(body.pop("quantidade_etiquetas", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Quantidade de etiquetas inválida.") from exc
        if not 1 <= quantidade <= 1000:
            raise ValueError("A quantidade de etiquetas deve ficar entre 1 e 1000.")

        resultado = gerar_lote(body, destino, quantidade)

        if resultado["error"]:
            return jsonify({
                "erro": resultado["error"],
                "identificador": resultado["first_identifier"],
                "ultimo_identificador": resultado["last_identifier"],
                "quantidade": quantidade,
                "consumido": True,
            }), 500

        return jsonify({
            "ok": True,
            "id": resultado["labels"][0]["id"],
            "identificador": resultado["first_identifier"],
            "ultimo_identificador": resultado["last_identifier"],
            "quantidade": quantidade,
            "zpl": resultado["combined_zpl"],
        })
    except (ValueError, sqlite3.Error) as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.get("/historico")
def history():
    return jsonify(etiqueta_model.listar_historico())


@api_bp.get("/etiqueta/<int:label_id>.zpl")
@api_bp.get("/etiqueta/<int:label_id>.prn")
def get_print_file(label_id: int):
    row = etiqueta_model.obter_zpl(label_id)
    if not row:
        return jsonify({"erro": "Etiqueta não encontrada."}), 404
    return Response(
        row["zpl"],
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={row['identificador']}.prn"},
    )


@api_bp.get("/backup")
def backup():
    target = etiqueta_model.gerar_backup()
    return send_file(target, as_attachment=True, download_name=target.name)
