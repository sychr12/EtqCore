"""API usada pela tela para visualizar, salvar, imprimir e consultar etiquetas."""

from __future__ import annotations

import json
import sqlite3

from flask import Blueprint, Response, jsonify, request, send_file

from models import configuracao as config_model
from models import etiqueta as etiqueta_model
from services.contador import identifier_for_counter, visible_counter
from services.geracao import gerar_lote
from services.impressao import installed_printers, recommended_zebra
from services.qrcode_service import qr_payload, render_svg
from services.texto import quantity_x1000
from services.texto import dots
from services.validacao import validate_label, validate_settings

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/estado")
def state():
    """Retorna configurações, próximo número e a última etiqueta salva."""
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
    """Valida e grava as configurações informadas na tela."""
    try:
        values = validate_settings(request.get_json(silent=True))
        config_model.salvar(values)
        return jsonify({"ok": True})
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.post("/preview")
def preview():
    """Monta os dados da prova sem consumir o contador."""
    try:
        body = validate_label(request.get_json(silent=True))
        cfg = config_model.obter_todas()
        counter = int(cfg["proximo_contador"])
        identifier = identifier_for_counter(counter, cfg["prefixo_contador"])
        qr = qr_payload(body, identifier, cfg["filial"])
        return jsonify({
            "identificador": identifier,
            "numero": visible_counter(counter),
            "qr": qr,
            "quantidade_qr": quantity_x1000(body.get("quantidade")),
            "impressao": {
                "largura_mm": float(cfg["largura_mm"]),
                "comprimento_mm": float(cfg["comprimento_mm"]),
                "dpi": int(cfg["dpi"]),
                "largura_dots": dots(float(cfg["largura_mm"]), int(cfg["dpi"])),
                "comprimento_dots": dots(float(cfg["comprimento_mm"]), int(cfg["dpi"])),
            },
        })
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.post("/qr.svg")
def qr_svg():
    """Gera o QR em SVG usado somente pela pré-visualização web."""
    try:
        text = request.get_data(as_text=True)
        if not text or len(text) > 4096:
            raise ValueError("O conteúdo do QR deve ter entre 1 e 4096 caracteres.")
        svg = render_svg(text)
        return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "no-store"})
    except (UnicodeError, ValueError) as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.post("/gerar")
def generate():
    """Gera PRN ou envia um lote diretamente para a Zebra."""
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValueError("Envie os dados da etiqueta em formato JSON válido.")
        body = dict(payload)
        destino = body.pop("destino", "download")
        if destino not in {"download", "imprimir"}:
            raise ValueError("Destino de geração inválido.")
        try:
            quantidade = int(body.pop("quantidade_etiquetas", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Quantidade de etiquetas inválida.") from exc
        if not 1 <= quantidade <= 1000:
            raise ValueError("A quantidade de etiquetas deve ficar entre 1 e 1000.")

        body = validate_label(body)

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
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except RuntimeError as exc:
        # Falha de pré-verificação da impressora acontece antes de reservar o contador.
        return jsonify({"erro": str(exc), "consumido": False}), 409
    except sqlite3.Error:
        return jsonify({"erro": "Não foi possível registrar a etiqueta no banco de dados."}), 500


@api_bp.get("/impressoras")
def printers():
    """Lista as impressoras que o Windows disponibiliza ao programa."""
    available = installed_printers()
    return jsonify({"impressoras": available, "recomendada": recommended_zebra(available)})


@api_bp.get("/historico")
def history():
    """Retorna as etiquetas registradas, da mais nova para a mais antiga."""
    return jsonify(etiqueta_model.listar_historico())


@api_bp.get("/etiqueta/<int:label_id>.zpl")
@api_bp.get("/etiqueta/<int:label_id>.prn")
def get_print_file(label_id: int):
    """Baixa novamente o ZPL/PRN de uma etiqueta do histórico."""
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
    """Cria e baixa uma cópia segura do banco e do contador."""
    target = etiqueta_model.gerar_backup()
    return send_file(target, as_attachment=True, download_name=target.name)
