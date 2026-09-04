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
from services.relatorio_excel import (
    caminho_relatorio,
    caminho_relatorio_anual,
    criar_relatorio_anual,
    criar_relatorio_mensal,
    escolher_pasta_windows,
    testar_pasta,
)
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


@api_bp.get("/relatorios/periodos")
def report_periods():
    """Lista os meses disponíveis para preencher os filtros da interface."""
    return jsonify(etiqueta_model.listar_periodos())


@api_bp.post("/relatorios/mensal")
def create_monthly_report():
    """Cria a planilha dentro de dados/relatorios/ANO/MÊS."""
    payload = request.get_json(silent=True) or {}
    try:
        ano, mes = int(payload.get("ano")), int(payload.get("mes"))
        etiquetas = etiqueta_model.listar_por_periodo(ano, mes)
        pasta = config_model.obter_todas().get("pasta_relatorios")
        testar_pasta(pasta)
        arquivo = criar_relatorio_mensal(ano, mes, etiquetas, pasta)
    except (OSError, TypeError, ValueError) as exc:
        return jsonify({"erro": str(exc) or "Ano ou mês inválido."}), 400
    return jsonify({
        "ok": True,
        "total": len(etiquetas),
        "arquivo": str(arquivo),
        "download": f"/api/relatorios/mensal/{ano:04d}/{mes:02d}",
    })


@api_bp.get("/relatorios/mensal/<int:ano>/<int:mes>")
def download_monthly_report(ano: int, mes: int):
    """Baixa uma planilha já criada, sem expor outros caminhos do computador."""
    try:
        arquivo = caminho_relatorio(ano, mes, config_model.obter_todas().get("pasta_relatorios"))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    if not arquivo.exists():
        return jsonify({"erro": "Gere a planilha deste período primeiro."}), 404
    return send_file(arquivo, as_attachment=True, download_name=arquivo.name)


@api_bp.post("/relatorios/anual")
def create_annual_report():
    """Cria o consolidado do ano com resumo e abas dos meses utilizados."""
    payload = request.get_json(silent=True) or {}
    try:
        ano = int(payload.get("ano"))
        if not 2000 <= ano <= 2100:
            raise ValueError("Ano inválido.")
        etiquetas = etiqueta_model.listar_por_ano(ano)
        pasta = config_model.obter_todas().get("pasta_relatorios")
        testar_pasta(pasta)
        arquivo = criar_relatorio_anual(ano, etiquetas, pasta)
    except (OSError, TypeError, ValueError) as exc:
        return jsonify({"erro": str(exc) or "Ano inválido."}), 400
    return jsonify({
        "ok": True,
        "total": len(etiquetas),
        "arquivo": str(arquivo),
        "download": f"/api/relatorios/anual/{ano:04d}",
    })


@api_bp.get("/relatorios/anual/<int:ano>")
def download_annual_report(ano: int):
    """Baixa o consolidado anual já criado."""
    try:
        arquivo = caminho_relatorio_anual(ano, config_model.obter_todas().get("pasta_relatorios"))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    if not arquivo.exists():
        return jsonify({"erro": "Gere a planilha anual primeiro."}), 404
    return send_file(arquivo, as_attachment=True, download_name=arquivo.name)


@api_bp.post("/relatorios/pasta/testar")
def test_reports_folder():
    """Testa uma pasta local ou compartilhada antes de salvar a configuração."""
    payload = request.get_json(silent=True) or {}
    try:
        pasta = str(payload.get("pasta") or "").strip()
        if not pasta:
            raise ValueError("Informe a pasta dos relatórios.")
        destino = testar_pasta(pasta)
        return jsonify({"ok": True, "pasta": str(destino)})
    except (OSError, ValueError) as exc:
        return jsonify({"erro": str(exc)}), 400


@api_bp.post("/relatorios/pasta/escolher")
def choose_reports_folder():
    """Abre o seletor de pastas do Windows e devolve a escolha para a tela."""
    payload = request.get_json(silent=True) or {}
    atual = str(payload.get("pasta_atual") or config_model.obter_todas().get("pasta_relatorios") or "")
    try:
        escolha = escolher_pasta_windows(atual)
        return jsonify({"ok": True, "cancelado": escolha is None, "pasta": escolha})
    except (OSError, RuntimeError) as exc:
        return jsonify({"erro": str(exc)}), 500


@api_bp.post("/relatorios/pasta/configurar")
def configure_reports_folder():
    """Testa e salva somente o destino dos relatórios, sem alterar a impressora."""
    payload = request.get_json(silent=True) or {}
    try:
        pasta = str(payload.get("pasta") or "").strip()
        if not pasta:
            raise ValueError("Escolha uma pasta para os relatórios.")
        destino = testar_pasta(pasta)
        config_model.salvar({"pasta_relatorios": str(destino)})
        return jsonify({"ok": True, "pasta": str(destino)})
    except (OSError, ValueError) as exc:
        return jsonify({"erro": str(exc)}), 400


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


@api_bp.post("/historico/<int:label_id>/desfazer")
def undo_last_history(label_id: int):
    """Remove somente a última etiqueta e restaura seu número no contador."""
    try:
        etiqueta_model.validar_desfazer_ultima(label_id)
        backup = etiqueta_model.gerar_backup()
        removida = etiqueta_model.desfazer_ultima(label_id)
        return jsonify({
            "ok": True,
            "identificador": removida["identificador"],
            "proximo_contador": removida["contador"],
            "backup": str(backup),
        })
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 409
    except (OSError, sqlite3.Error):
        return jsonify({"erro": "Não foi possível desfazer a etiqueta com segurança."}), 500


@api_bp.post("/historico/apagar-tudo")
def clear_history():
    """Cria um backup, apaga o histórico completo e reinicia o contador."""
    try:
        backup = etiqueta_model.gerar_backup()
        total = etiqueta_model.apagar_todo_historico()
        return jsonify({
            "ok": True,
            "registros_apagados": total,
            "proximo_contador": 1,
            "backup": str(backup),
        })
    except (OSError, sqlite3.Error):
        return jsonify({"erro": "Não foi possível apagar o histórico com segurança."}), 500


@api_bp.post("/historico/apagar-intervalo")
def clear_history_range():
    """Apaga contadores dentro de um intervalo e posiciona o contador exatamente."""
    try:
        data = request.get_json(silent=True) or {}
        inicio = int(data.get("inicio"))
        fim = int(data.get("fim"))
        proximo = int(data.get("proximo"))
        etiqueta_model.validar_exclusao_intervalo(inicio, fim, proximo)
        backup = etiqueta_model.gerar_backup()
        total = etiqueta_model.apagar_intervalo(inicio, fim, proximo)
        return jsonify({
            "ok": True,
            "registros_apagados": total,
            "inicio": inicio,
            "fim": fim,
            "proximo_contador": proximo,
            "backup": str(backup),
        })
    except (TypeError, ValueError) as exc:
        return jsonify({"erro": str(exc) or "Preencha todos os números."}), 400
    except (OSError, sqlite3.Error):
        return jsonify({"erro": "Não foi possível apagar o intervalo com segurança."}), 500


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
