"""Operações do histórico: inserir etiquetas, marcar resultado e fazer backup."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .database import db
from config import BACKUP_DIR


def obter_ultima() -> sqlite3.Row | None:
    """Busca os dados da etiqueta mais recente para restaurar o formulário."""
    with closing(db()) as con:
        return con.execute(
            "SELECT identificador, dados_json FROM etiquetas ORDER BY id DESC LIMIT 1"
        ).fetchone()


def inserir_lote(
    con: sqlite3.Connection,
    itens: list[dict],
    destino: str,
    dados_originais: dict,
) -> list[dict]:
    """Insere um lote de etiquetas dentro de uma transação já aberta (BEGIN
    IMMEDIATE feito pelo controller/service que orquestra a geração).
    `itens` é uma lista de {contador, identificador, qr, zpl}.
    Retorna a lista com o `id` de cada linha inserida."""
    criada_em = datetime.now().isoformat(timespec="seconds")
    serializado = json.dumps(dados_originais, ensure_ascii=False)
    resultado = []
    for item in itens:
        cur = con.execute(
            "INSERT INTO etiquetas(contador, identificador, criada_em, dados_json, qr_texto, zpl, destino, sucesso) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (item["contador"], item["identificador"], criada_em, serializado, item["qr"], item["zpl"], destino),
        )
        resultado.append({**item, "id": cur.lastrowid})
    return resultado


def marcar_resultado(itens: list[dict], sucesso: bool, erro: str | None) -> None:
    """Registra se o arquivo foi gerado/impresso ou se ocorreu algum erro."""
    with closing(db()) as con:
        con.executemany(
            "UPDATE etiquetas SET sucesso=?, erro=? WHERE id=?",
            ((1 if sucesso else 0, erro, item["id"]) for item in itens),
        )
        con.commit()


def listar_historico(limite: int = 200) -> list[dict]:
    """Devolve as últimas etiquetas em um formato pronto para a interface."""
    with closing(db()) as con:
        rows = con.execute(
            "SELECT id, contador, identificador, criada_em, dados_json, destino, sucesso, erro "
            "FROM etiquetas ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["dados"] = json.loads(item.pop("dados_json"))
        resultado.append(item)
    return resultado


def listar_por_periodo(ano: int, mes: int) -> list[dict]:
    """Busca todas as etiquetas de um mês, sem limitar a quantidade."""
    inicio = f"{ano:04d}-{mes:02d}-01"
    fim = f"{ano + 1:04d}-01-01" if mes == 12 else f"{ano:04d}-{mes + 1:02d}-01"
    with closing(db()) as con:
        rows = con.execute(
            "SELECT id, contador, identificador, criada_em, dados_json, destino, sucesso, erro "
            "FROM etiquetas WHERE criada_em >= ? AND criada_em < ? ORDER BY criada_em, id",
            (inicio, fim),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["dados"] = json.loads(item.pop("dados_json"))
        resultado.append(item)
    return resultado


def listar_por_ano(ano: int) -> list[dict]:
    """Busca todas as etiquetas registradas durante um ano."""
    with closing(db()) as con:
        rows = con.execute(
            "SELECT id, contador, identificador, criada_em, dados_json, destino, sucesso, erro "
            "FROM etiquetas WHERE criada_em >= ? AND criada_em < ? ORDER BY criada_em, id",
            (f"{ano:04d}-01-01", f"{ano + 1:04d}-01-01"),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["dados"] = json.loads(item.pop("dados_json"))
        resultado.append(item)
    return resultado


def listar_periodos() -> list[dict]:
    """Informa os anos e meses que possuem etiquetas no histórico."""
    with closing(db()) as con:
        rows = con.execute(
            "SELECT substr(criada_em,1,4) AS ano, substr(criada_em,6,2) AS mes, COUNT(*) AS total "
            "FROM etiquetas GROUP BY ano, mes ORDER BY ano DESC, mes DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def obter_zpl(label_id: int) -> sqlite3.Row | None:
    """Recupera o arquivo de impressão de uma etiqueta específica."""
    with closing(db()) as con:
        return con.execute(
            "SELECT identificador, zpl FROM etiquetas WHERE id=?", (label_id,)
        ).fetchone()


def gerar_backup() -> Path:
    """Copia o banco em uso para a pasta de backups sem corrompê-lo."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target: Path = BACKUP_DIR / f"etiquetas-{stamp}.db"
    with closing(db()) as source, closing(sqlite3.connect(target)) as dest:
        source.backup(dest)
    return target
